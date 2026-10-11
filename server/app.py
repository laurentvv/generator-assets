"""FastAPI application assembling the web UI: pages (Jinja2/HTMX), JSON+HTMX
API, SSE stream, uploads and guarded file serving.

Run:  uv run python -m server   (http://127.0.0.1:8765 — localhost only)
"""

import asyncio
import json
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from server import assets, db, introspection, paths
from server import jobs as jobs_mod
from server.argv import ArgvError
from server.events import hub

STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

KIND_ICONS = {"image": "🖼️", "video": "🎬", "audio": "🔊", "model": "🧊", "doc": "📄"}
STATUS_COLORS = {
    "pending": "text-info", "running": "text-accent", "complete": "text-ok",
    "error": "text-err", "canceled": "text-ink-faint", "interrupted": "text-warn",
    "blocked_load": "text-warn",
}
UPLOAD_ALLOWED_EXT = {
    "png", "jpg", "jpeg", "webp", "gif", "bmp", "wav", "mp3", "ogg", "flac",
    "m4a", "webm", "mp4", "mov", "json", "txt", "md", "glb",
}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def create_app() -> FastAPI:
    paths.ensure_dirs()
    db.init()

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    env.globals["catalog"] = introspection.catalog()
    env.globals["outputs_for_job"] = db.outputs_for_job

    def render(name: str, **context: Any) -> str:
        return env.get_template(name).render(**{**globals_for_templates(), **context})

    state: Dict[str, Any] = {"manager": None}

    def manager() -> jobs_mod.JobManager:
        assert state["manager"] is not None
        return state["manager"]

    def page(name: str, request: Request, **context: Any) -> HTMLResponse:
        context.setdefault("active", "")
        context.setdefault("request", request)
        return HTMLResponse(render(name, **context))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state["manager"] = jobs_mod.JobManager(render=render)
        await state["manager"].start()
        yield
        await state["manager"].stop()

    app = FastAPI(title="generator-assets console", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    # ---------------------------------------------------------------- pages

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        await assets.refresh()
        return page("index.html", request, active="home",
                    snapshot=manager().snapshot(),
                    recent_jobs=db.list_jobs(limit=8),
                    recent_outputs=db.search_outputs(limit=12),
                    engines=engines_presence())

    @app.get("/w/{workflow}", response_class=HTMLResponse)
    async def workflow_page(request: Request, workflow: str) -> HTMLResponse:
        entry = introspection.get(workflow)
        if entry is None:
            return HTMLResponse(f"unknown workflow {workflow}", status_code=404)
        snapshot = manager().snapshot()
        presets_json = json.dumps(entry["presets"])
        prefill = dict(request.query_params)
        return page("workflow.html", request, active=workflow, wf=entry,
                    presets_json=presets_json, snapshot=snapshot, prefill=prefill)

    @app.get("/models", response_class=HTMLResponse)
    async def models_page(request: Request, inventory: str = "") -> HTMLResponse:
        from server import models as models_mod

        expected = await asyncio.to_thread(models_mod.expected_models)
        deps = models_mod.workflow_dependencies()
        overrides = models_mod.active_env_overrides()
        loras = await asyncio.to_thread(models_mod.loras)
        upscalers = await asyncio.to_thread(models_mod.upscalers)
        disk = await asyncio.to_thread(models_mod.inventory) if inventory else None
        present = sum(1 for section in expected for item in section["items"] if item["present"])
        total = sum(1 for section in expected for item in section["items"])
        return page("models.html", request, active="models",
                    snapshot=manager().snapshot(),
                    sections=expected, deps=deps, overrides=overrides,
                    loras=loras, upscalers=upscalers, disk=disk,
                    present_count=present, total_count=total,
                    show_inventory=bool(inventory))

    @app.get("/library", response_class=HTMLResponse)
    async def library(request: Request, kind: str = "", workflow: str = "",
                      q: str = "", page_n: int = 1, detail: str = "") -> HTMLResponse:
        await assets.refresh()
        page_n = max(1, min(page_n, 500))
        per_page = 60
        items = db.search_outputs(kind=kind or None, workflow=workflow or None, query=q,
                                  limit=per_page, offset=(page_n - 1) * per_page)
        total = db.count_outputs(kind=kind or None, query=q)
        return page("library.html", request, active="library", items=items, total=total,
                    kind=kind, workflow=workflow, q=q, page_n=page_n, per_page=per_page,
                    detail=detail, snapshot=manager().snapshot(),
                    workflow_names=introspection.workflow_names())

    @app.get("/search", response_class=HTMLResponse)
    async def search(request: Request, q: str = "") -> HTMLResponse:
        needle = q.strip().lower()
        matches = [
            wf for wf in introspection.catalog()["workflows"].values()
            if not needle or needle in wf["name"] or needle in wf["description"].lower()
        ][:12]
        return HTMLResponse(render("partials/search_results.html", matches=matches))

    # ------------------------------------------------------------- partials

    @app.get("/partials/file-picker", response_class=HTMLResponse)
    async def file_picker(field: str = "input", kind: str = "image") -> HTMLResponse:
        groups = picker_groups(kind)
        return HTMLResponse(render("partials/file_picker.html", groups=groups, field=field, kind=kind))

    @app.get("/partials/asset-detail", response_class=HTMLResponse)
    async def asset_detail(path: str) -> HTMLResponse:
        try:
            resolved = paths.resolve_allowed(path)
        except paths.UnsafePath:
            return HTMLResponse("forbidden", status_code=403)
        rows: List[Any] = []
        job = None
        if resolved.exists():
            await assets.refresh()
            rows = db._query("SELECT * FROM outputs WHERE path = ?", (path,))  # noqa: SLF001
            if rows and rows[0]["job_id"]:
                job = db.get_job(rows[0]["job_id"])
        return HTMLResponse(render("partials/asset_detail.html", path=path,
                                   item=dict(rows[0]) if rows else None,
                                   resolved=resolved, job=job))

    @app.get("/partials/system-check", response_class=HTMLResponse)
    async def system_check() -> HTMLResponse:
        allowed, output = await run_load_gate()
        return HTMLResponse(render("partials/system_check.html", allowed=allowed, output=output.strip()))

    @app.get("/partials/job-log/{job_id}", response_class=HTMLResponse)
    async def job_log(job_id: str) -> HTMLResponse:
        job = db.get_job(job_id)
        if job is None:
            return HTMLResponse("unknown job", status_code=404)
        lines = jobs_mod.read_log_tail(job, lines=400)
        return HTMLResponse(render("partials/log_tail.html", lines=lines))

    # ------------------------------------------------------------------ api

    @app.post("/api/jobs")
    async def create_job(request: Request) -> Response:
        form = await request.form()
        workflow = str(form.get("workflow") or "")
        entry = introspection.get(workflow)
        if entry is None:
            return HTMLResponse(f"unknown workflow {workflow}", status_code=400)
        params = {key: str(value) for key, value in form.items()
                  if key != "workflow" and value not in (None, "") and key in entry["params"]}
        try:
            job = await manager().enqueue(workflow, params)
        except ArgvError as exc:
            snapshot = manager().snapshot()
            return HTMLResponse(render("partials/job_panel.html", job=None, snapshot=snapshot,
                                       form_error=str(exc)), status_code=400)
        return HTMLResponse(render("partials/job_panel.html", job=job,
                                   snapshot=manager().snapshot(), form_error=None))

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> JSONResponse:
        done = await manager().cancel(job_id)
        return JSONResponse({"ok": done})

    @app.post("/api/jobs/{job_id}/retry")
    async def retry_job(job_id: str) -> JSONResponse:
        done = await manager().retry(job_id)
        return JSONResponse({"ok": done})

    @app.get("/api/jobs")
    async def list_jobs_api() -> JSONResponse:
        return JSONResponse({"jobs": db.list_jobs(limit=50)})

    @app.post("/api/uploads")
    async def upload(request: Request, file: UploadFile = Form(...)) -> Response:  # noqa: B008
        via_htmx = request.headers.get("hx-request") == "true"
        suffix = Path(file.filename or "upload.bin").suffix.lower().lstrip(".")
        if suffix not in UPLOAD_ALLOWED_EXT:
            message = f"extension .{suffix} not allowed"
            return (HTMLResponse(f'<span class="text-err">{message}</span>', status_code=400)
                    if via_htmx else JSONResponse({"ok": False, "error": message}, status_code=400))
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(file.filename or "upload.bin").stem)[:60]
        dest = paths.UPLOAD_DIR / f"{int(time.time())}_{safe}.{suffix}"
        size = 0
        with dest.open("wb") as handle:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    handle.close()
                    dest.unlink(missing_ok=True)
                    message = "file too large"
                    return (HTMLResponse(f'<span class="text-err">{message}</span>', status_code=413)
                            if via_htmx else JSONResponse({"ok": False, "error": message}, status_code=413))
                handle.write(chunk)
        rel = paths.relpath_for(dest)
        if via_htmx:
            return HTMLResponse(
                f'<span class="text-ok">✓ uploaded</span> '
                f'<button type="button" class="btn px-2 py-0.5 text-[10px]" '
                f'@click="$dispatch(\'ga-pick\', {{field: picker.field, path: \'{rel}\'}})">use it</button>'
            )
        return JSONResponse({"ok": True, "path": rel, "url": f"/files?p={rel}"})

    @app.get("/files")
    async def files(request: Request, p: str = "") -> Response:
        try:
            resolved = paths.resolve_allowed(p)
        except paths.UnsafePath:
            return Response("forbidden", status_code=403)
        if not resolved.is_file():
            return Response("not found", status_code=404)
        size = resolved.stat().st_size
        range_header = request.headers.get("range")
        if range_header:
            span = assets.parse_range(range_header, size)
            if span is None:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
            start, end = span
            chunk = await asyncio.to_thread(assets.read_range, resolved, start, end)
            return Response(chunk, status_code=206, media_type=assets.mime_for(resolved), headers={
                "Content-Range": f"bytes {start}-{end}/{size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(chunk)),
                "Cache-Control": "private, max-age=60",
            })
        return FileResponse(resolved, media_type=assets.mime_for(resolved), headers={
            "Accept-Ranges": "bytes", "Cache-Control": "private, max-age=60",
        })

    @app.get("/thumbs/{name}")
    async def thumbs(name: str) -> Response:
        if "/" in name or "\\" in name or ".." in name:
            return Response("forbidden", status_code=403)
        target = paths.THUMB_DIR / name
        if not target.is_file():
            return Response("not found", status_code=404)
        media = "image/png" if name.endswith(".png") else "image/webp"
        return FileResponse(target, media_type=media,
                            headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/api/system")
    async def system_api() -> JSONResponse:
        return JSONResponse({
            "engines": engines_presence(),
            "queue": manager().snapshot()["pending_count"],
            "machine": machine_snapshot(),
        })

    @app.get("/api/events")
    async def events(request: Request) -> Response:
        from sse_starlette.sse import EventSourceResponse

        mgr = manager()

        async def stream():
            queue = hub().subscribe()
            try:
                snapshot = mgr.snapshot()
                current = snapshot["current"]
                yield {"event": "queue_status", "data": render("partials/queue_bar.html", snapshot=snapshot)}
                yield {"event": "job_state", "data": render("partials/job_panel.html", job=current,
                                                            snapshot=snapshot, form_error=None)}
                if current:
                    lines = jobs_mod.read_log_tail(current)
                    yield {"event": "job_log", "data": render("partials/log_tail.html", lines=lines)}
                    yield {"event": "job_progress", "data": render("partials/progress.html",
                                                                   job=current, progress=current.get("progress") or 0)}
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=10.0)
                    except asyncio.TimeoutError:
                        continue
                    yield item
            finally:
                hub().unsubscribe(queue)

        return EventSourceResponse(stream())

    # ---------------------------------------------------------------- static
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


# ----------------------------------------------------------------- helpers --

def globals_for_templates() -> Dict[str, Any]:
    return {
        "file_url": lambda rel: f"/files?p={rel}",
        "thumb_of": _thumb_of,
        "wave_of": _wave_of,
        "kind_icon": lambda kind: KIND_ICONS.get(kind, "📁"),
        "status_color": lambda status: STATUS_COLORS.get(status, "text-ink-dim"),
        "fmt_size": _fmt_size,
        "fmt_ts": _fmt_ts,
        "fmt_dur": _fmt_dur,
        "basename": lambda rel: rel.rsplit("/", 1)[-1] if rel else "",
        "dirname": lambda rel: rel.rsplit("/", 1)[0] if "/" in rel else "",
        "now": time.time,
    }


def _thumb_of(rel: str) -> Optional[str]:
    try:
        return assets.thumbnail(paths.REPO_ROOT / rel)
    except (OSError, ValueError):
        return None


def _wave_of(rel: str) -> Optional[str]:
    try:
        return assets.waveform(paths.REPO_ROOT / rel)
    except (OSError, ValueError):
        return None


def _fmt_size(size: Optional[int]) -> str:
    if not size:
        return "—"
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _fmt_ts(ts: Optional[float]) -> str:
    if not ts:
        return "—"
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


def _fmt_dur(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"


def engines_presence() -> Dict[str, bool]:
    from core import config as engine_config

    probes = {
        "sd-cli": "DEFAULT_SD_CLI",
        "sd-cli (LTX pin)": "DEFAULT_SD_CLI_LTX",
        "llama-cli": "DEFAULT_LLAMA_CLI",
        "audio.cpp": "DEFAULT_AUDIOCPP_CLI",
        "ffmpeg": "DEFAULT_FFMPEG",
    }
    return {
        label: Path(str(getattr(engine_config, key))).exists()
        for label, key in probes.items()
        if getattr(engine_config, key, None)
    }


def machine_snapshot() -> Dict[str, Any]:
    import psutil

    disk = psutil.disk_usage(str(paths.REPO_ROOT))
    memory = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": memory.percent,
        "disk_free_gb": round(disk.free / (1 << 30), 1),
    }


async def run_load_gate() -> tuple:
    """Standalone gate run for the dashboard card (same semantics as jobs)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(paths.SCRIPT_CHECK_CHARGE),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=330)
    except (OSError, asyncio.TimeoutError) as exc:
        return True, f"gate unavailable: {exc}"
    return proc.returncode != 1, raw.decode("utf-8", errors="replace")


def picker_groups(kind: str) -> List[Dict[str, Any]]:
    """File groups for the input picker dialog (uploads, inputs, outputs)."""
    groups: List[Dict[str, Any]] = []
    wanted = {kind} if kind not in ("file", "folder") else set(assets.EXTENSIONS)
    if kind == "file":
        wanted |= {"doc"}

    def collect(label: str, roots: List[Path], limit: int) -> None:
        items: List[Dict[str, Any]] = []
        for root in roots:
            if not root.exists():
                continue
            if kind == "folder":
                items.extend({"path": paths.relpath_for(directory), "name": directory.name, "thumb": None}
                             for directory in root.rglob("*") if directory.is_dir())
            else:
                for file in root.rglob("*"):
                    if len(items) >= limit:
                        break
                    if file.is_file() and assets.classify(file) in wanted:
                        rel = paths.relpath_for(file)
                        if rel.startswith("output/_webui/"):
                            continue
                        items.append({"path": rel, "name": file.name,
                                      "thumb": assets.thumbnail(file) if kind == "image" else None})
            if len(items) >= limit:
                break
        if items:
            items.sort(key=lambda item: item["path"])
            groups.append({"label": label, "items": items[:limit]})

    collect("Uploads", [paths.UPLOAD_DIR], 24)
    collect("Validated inputs (godot_assets/)", [paths.REPO_ROOT / "godot_assets"], 40)
    collect("Generated (output/)", [paths.REPO_ROOT / "output"], 40)
    return groups
