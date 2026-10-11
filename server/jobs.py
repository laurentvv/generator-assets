"""Serialized job queue driving the factory CLI (single worker, one GPU job).

Enforced operating rules (AGENTS.md): one heavy job at a time (RTF 3.3x
incident), scripts/check_charge_systeme.py gate before heavy launches (exit 1
= refuse, exit 2 = measurement error, allowed — mirrors workflows/qwen_image),
subprocess invocation from the repository root (frozen consumer contract).

The worker publishes pre-rendered HTML fragments (queue bar, run panel,
progress, log tail) through the EventHub; the SSE endpoint streams them to
every tab. No engine ever runs inside the server process.
"""

import asyncio
import logging
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import psutil

from server import argv as argv_mod
from server import db, introspection, paths
from server.events import hub

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = ("blocked_load", "error", "canceled", "interrupted")

_STEP_RE = re.compile(r"step\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_ITER_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*it\b", re.IGNORECASE)
_PCT_RE = re.compile(r"(\d{1,3})\s*%")


def parse_progress(line: str) -> Optional[float]:
    """Fraction 0..1 from a raw engine line, else None."""
    match = _STEP_RE.search(line) or _ITER_RE.search(line)
    if match:
        done, total = int(match.group(1)), int(match.group(2))
        if total > 0 and done <= total:
            return done / total
    match = _PCT_RE.search(line)
    if match:
        return min(int(match.group(1)), 100) / 100
    return None


class JobManager:
    """Single-worker queue; owns the subprocess lifecycle of the current job."""

    def __init__(self, render: Callable[..., str]) -> None:
        self.render = render  # (template_name, **ctx) -> html fragment
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.current_id: Optional[str] = None
        self._procs: Dict[str, asyncio.subprocess.Process] = {}
        self._cancel_requested: set = set()
        self._worker: Optional[asyncio.Task] = None
        self._cmd_prefix: Optional[List[str]] = None

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        db.mark_orphans_interrupted()
        for job in db.pending_jobs():  # survived a server restart
            await self.queue.put(job["id"])
        self._worker = asyncio.create_task(self._worker_loop())
        if self.queue.qsize():
            self._publish_queue()

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker = None
        proc = self._procs.get(self.current_id or "")
        if proc is not None and proc.returncode is None:
            await self._kill_tree(proc.pid)

    # ------------------------------------------------------------ public API

    async def enqueue(self, workflow: str, params: Dict[str, Any]) -> Dict[str, Any]:
        entry = introspection.get(workflow)
        if entry is None:
            raise argv_mod.ArgvError(f"unknown workflow: {workflow}")
        flags_argv, prompt = argv_mod.build_argv(workflow, params)
        job_id = uuid.uuid4().hex[:10]
        full_argv = ["-w", workflow] + ([prompt] if prompt else []) + flags_argv
        db.insert_job({
            "id": job_id, "workflow": workflow, "prompt": prompt,
            "params": params, "argv": full_argv, "heavy": entry["heavy"],
        })
        await self.queue.put(job_id)
        self._publish_queue()
        return db.get_job(job_id)  # type: ignore[return-value]

    async def retry(self, job_id: str) -> bool:
        job = db.get_job(job_id)
        if not job or job["status"] not in RETRYABLE_STATUSES:
            return False
        db.set_job_status(job_id, "pending", error=None, progress=0, started_at=None, ended_at=None)
        await self.queue.put(job_id)
        self._publish_queue()
        return True

    async def cancel(self, job_id: str) -> bool:
        job = db.get_job(job_id)
        if not job:
            return False
        if job["status"] == "pending":
            db.set_job_status(job_id, "canceled", ended_at=time.time())
            self._emit_state(job_id, notify_kind=None)
            self._publish_queue()
            return True
        if job["status"] == "running":
            self._cancel_requested.add(job_id)
            proc = self._procs.get(job_id)
            if proc is not None and proc.returncode is None:
                await self._kill_tree(proc.pid)
            return True
        return False

    def snapshot(self) -> Dict[str, Any]:
        current = db.get_job(self.current_id) if self.current_id else None
        pending = db.pending_jobs()
        return {"current": current, "pending": pending, "pending_count": len(pending)}

    def current_job(self) -> Optional[Dict[str, Any]]:
        return db.get_job(self.current_id) if self.current_id else None

    # -------------------------------------------------------------- worker

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await self._run_job(job_id)
            except Exception:  # noqa: BLE001 — a failed job must not kill the worker
                logger.exception("webui: job %s crashed the worker loop", job_id)
                db.set_job_status(job_id, "error", error="internal worker error — see server log", ended_at=time.time())
                self._emit_state(job_id, notify_kind="error")
            finally:
                self.queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        job = db.get_job(job_id)
        if not job or job["status"] != "pending":
            return  # canceled while queued

        log_path = paths.LOG_DIR / f"{job_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        db.set_job_status(job_id, "running", started_at=time.time(), progress=0,
                          log_path=str(log_path), error=None)

        if job["heavy"]:
            allowed, gate_output = await self._load_gate()
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(gate_output if gate_output.endswith("\n") else gate_output + "\n")
            if not allowed:
                db.set_job_status(
                    job_id, "blocked_load", ended_at=time.time(),
                    error="System load too high (check_charge_systeme exit 1) — retry when the machine is free.",
                )
                self._emit_state(job_id, notify_kind="error")
                self._publish_queue()
                return

        cmd = self._command_prefix() + ["main.py", *db.job_argv(job)]
        logger.info("webui: job %s launching: %s", job_id, " ".join(cmd[2:]))
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n$ {' '.join(cmd)}\n")

        self.current_id = job_id
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=str(paths.REPO_ROOT),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
        except OSError as exc:
            db.set_job_status(job_id, "error", ended_at=time.time(), error=f"spawn failed: {exc}")
            self.current_id = None
            self._emit_state(job_id, notify_kind="error")
            self._publish_queue()
            return

        self._procs[job_id] = proc
        self._emit_state(job_id, notify_kind=None)
        self._publish_queue()

        tail: List[str] = []
        progress = 0.0
        last_emit = 0.0
        with log_path.open("a", encoding="utf-8", errors="replace") as handle:
            assert proc.stdout is not None
            buffer = b""
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk
                # Engines emit both plain lines (\n) and carriage-return
                # progress bars (\r) — split on both without blocking.
                parts = buffer.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")
                buffer = parts.pop()  # incomplete tail stays buffered
                for raw in parts:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    handle.write(line + "\n")
                    handle.flush()
                    tail.append(line)
                    if len(tail) > 400:
                        del tail[: len(tail) - 400]
                    found = parse_progress(line)
                    if found is not None:
                        progress = max(progress, found)
                now = time.time()
                if now - last_emit > 0.6 and parts:
                    last_emit = now
                    db.update_job(job_id, progress=round(progress, 3))
                    hub().publish("job_log", self.render("partials/log_tail.html", lines=tail[-120:]))
                    hub().publish("job_progress", self.render("partials/progress.html", job=db.get_job(job_id), progress=progress))

        exit_code = await proc.wait()
        self._procs.pop(job_id, None)
        self.current_id = None

        canceled = job_id in self._cancel_requested
        self._cancel_requested.discard(job_id)

        # Attribute freshly written files to this job (indexer keeps kind/mtime).
        try:
            from server import assets  # late import: assets imports db too
            await assets.refresh(force=True)  # bypass the 30 s throttle: files are seconds old
            db.link_recent_outputs(job_id, job["workflow"], job["started_at"] or time.time())
        except Exception:  # noqa: BLE001 — indexing failure must not mask the job result
            logger.exception("webui: output indexing failed for job %s", job_id)

        if canceled:
            status, error = "canceled", None
        elif exit_code == 0:
            status, error = "complete", None
        else:
            status = "error"
            error = f"exit code {exit_code} — last log lines below"
        db.set_job_status(job_id, status, ended_at=time.time(), exit_code=exit_code,
                          error=error, progress=1.0 if status == "complete" else progress)
        self._emit_state(job_id, notify_kind=None if canceled else ("complete" if status == "complete" else "error"))
        self._publish_queue()

    # ----------------------------------------------------------- internals

    def _command_prefix(self) -> List[str]:
        if self._cmd_prefix is None:
            uv = shutil.which("uv")
            self._cmd_prefix = [uv, "run", "python"] if uv else [sys.executable]
        return list(self._cmd_prefix)

    async def _load_gate(self) -> tuple:
        """(allowed, output) — blocked only on exit 1 (see module docstring)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(paths.SCRIPT_CHECK_CHARGE),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            raw, _ = await asyncio.wait_for(proc.communicate(), timeout=330)
        except (OSError, asyncio.TimeoutError) as exc:
            logger.warning("webui: load gate failed to run (%s) — allowing job", exc)
            return True, f"load gate unavailable: {exc}\n"
        output = raw.decode("utf-8", errors="replace")
        if proc.returncode == 1:
            logger.warning("webui: load gate refused the launch (exit 1)")
        return proc.returncode != 1, output

    async def _kill_tree(self, pid: int) -> None:
        def _sync_kill() -> None:
            try:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for process in [parent, *children]:
                    try:
                        process.terminate()
                    except psutil.Error:
                        pass
                _dead, alive = psutil.wait_procs([parent, *children], timeout=3)
                for process in alive:
                    try:
                        process.kill()
                    except psutil.Error:
                        pass
            except psutil.NoSuchProcess:
                pass

        await asyncio.get_running_loop().run_in_executor(None, _sync_kill)

    def _emit_state(self, job_id: str, notify_kind: Optional[str]) -> None:
        job = db.get_job(job_id)
        if job is None:
            return
        if notify_kind in ("complete", "error"):
            hub().publish("notify", {"kind": notify_kind, "workflow": job["workflow"], "id": job_id})
        snapshot = self.snapshot()
        hub().publish("job_state", self.render(
            "partials/job_panel.html", job=job, snapshot=snapshot, notify=notify_kind,
        ))

    def _publish_queue(self) -> None:
        snapshot = self.snapshot()
        hub().publish("queue_status", self.render("partials/queue_bar.html", snapshot=snapshot))


def read_log_tail(job: Dict[str, Any], lines: int = 120) -> List[str]:
    """Last lines of a finished job's log (worker streams live ones itself)."""
    log_path: Optional[Path] = Path(job["log_path"]) if job.get("log_path") else None
    if not log_path or not log_path.exists():
        return []
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return content[-lines:]
