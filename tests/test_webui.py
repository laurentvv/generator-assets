"""Web UI test suite — no engine, no GPU required (fake subprocess / tmp dirs).

Covers: introspected catalog completeness, frozen argv building, progress
parsing, path traversal guard, SQLite round-trip, serialized job lifecycle
against a fake main.py, and page rendering through the FastAPI TestClient.
"""

import asyncio
import hashlib
import importlib.util
import json
import logging
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cli.parser import construire_parseur  # noqa: E402
from server import argv as argv_mod  # noqa: E402
from server import db, introspection, jobs, paths, schema_ui  # noqa: E402

ACTIVE = ("pending", "running")
TERMINAL = ("complete", "error", "canceled", "interrupted", "blocked_load")


# ---------------------------------------------------------------- fixtures --

@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Redirect every writable location of the web UI to a tmp dir."""
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    monkeypatch.setattr(paths, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(paths, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(paths, "THUMB_DIR", tmp_path / "thumbs")
    monkeypatch.setattr(paths, "ALLOWED_ROOTS", (tmp_path / "output", tmp_path / "godot_assets"))
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "godot_assets").mkdir(exist_ok=True)
    db.reset_for_tests(tmp_path / "factory.db")
    yield tmp_path
    db.close_for_tests()


@pytest.fixture
def fake_factory(tmp_state, monkeypatch):
    """A fake REPO_ROOT whose main.py is a tiny deterministic generator."""
    factory = tmp_state / "factory"
    factory.mkdir()
    (factory / "main.py").write_text(
        "import sys, time\n"
        "print('render step 1/4')\n"
        "time.sleep(0.15)\n"
        "print('render step 4/4 done')\n"
        "out = __import__('pathlib').Path('output') / 'made_by_fake.txt'\n"
        "out.parent.mkdir(exist_ok=True)\n"
        "out.write_text('asset')\n"
    )
    monkeypatch.setattr(paths, "REPO_ROOT", factory)
    monkeypatch.setattr(paths, "ALLOWED_ROOTS", (factory / "output", tmp_state / "godot_assets"))
    (factory / "output").mkdir(exist_ok=True)
    return factory


# ------------------------------------------------------------ introspection --

def test_catalog_covers_the_whole_registry():
    from workflows.base import WorkflowRegistry

    catalog = introspection.catalog()
    assert set(catalog["workflows"]) == set(WorkflowRegistry._workflows)
    assert sum(len(f["workflows"]) for f in catalog["families"]) == len(WorkflowRegistry._workflows)
    for entry in catalog["workflows"].values():
        assert entry["family"] in {"images", "textures3d", "characters", "video", "voice", "music", "utils"}
        assert entry["params"]["prompt"]["widget"] == "prompt"
        assert entry["params"]["output"]["widget"] == "text"


def test_catalog_no_curated_drift(caplog):
    """Every curated dest must be renderable — curation must not rot silently."""
    introspection.catalog.cache_clear()
    with caplog.at_level(logging.WARNING, logger="server.introspection"):
        introspection.catalog()
    drifted = [r.getMessage() for r in caplog.records if "webui:" in r.getMessage()]
    assert not drifted, f"curated schema drifted from the live registry: {drifted}"


def test_curated_families_cover_every_workflow():
    """Curated families == registry entries owned by the workflows package
    (subclasses like character3d included; test fakes filtered out)."""
    from workflows.base import WorkflowRegistry

    real = {
        name for name, cls in WorkflowRegistry._workflows.items()
        if cls.__module__.startswith("workflows")
    }
    assert set(schema_ui.WORKFLOW_FAMILY) == real


# --------------------------------------------------------------------- argv --

def test_argv_golden_qwen_turbo():
    flags, prompt = argv_mod.build_argv("qwen_image", {
        "prompt": "potion bottle with gold text",
        "seed": "42",
        "qwen_turbo": "1",
        "negative_prompt": "blurry",
        "width": "1152",
    })
    assert prompt == "potion bottle with gold text"
    # Dest iteration is sorted — argv is deterministic regardless of form order.
    assert flags == ["--negative-prompt", "blurry", "--qwen-turbo", "--seed", "42", "--width", "1152"]


def test_argv_skips_empty_values():
    flags, prompt = argv_mod.build_argv("generate", {"prompt": "sword", "steps": "", "seed": None})
    assert prompt == "sword"
    assert flags == []


def test_argv_loras_repetition():
    flags, _ = argv_mod.build_argv("generate", {"prompt": "x", "loras": ["pixel_art:0.8", "ink:1.0"]})
    assert flags == ["--lora", "pixel_art:0.8", "--lora", "ink:1.0"]
    flags, _ = argv_mod.build_argv("generate", {"prompt": "x", "loras": "a:0.5, b:1"})
    assert flags == ["--lora", "a:0.5", "--lora", "b:1"]


def test_argv_rejects_bad_values():
    with pytest.raises(argv_mod.ArgvError):
        argv_mod.build_argv("generate", {"prompt": "x", "unknown_flag_zzz": "1"})
    with pytest.raises(argv_mod.ArgvError):
        argv_mod.build_argv("mesh3d", {"prompt": "x", "shape": "hexagon"})
    with pytest.raises(argv_mod.ArgvError):
        argv_mod.build_argv("generate", {"prompt": "x", "steps": "many"})


def test_argv_flags_exist_in_the_real_surface():
    surface_flags = {
        flag
        for action in construire_parseur()._actions
        for flag in action.option_strings
    }
    for name, entry in introspection.catalog()["workflows"].items():
        for dest, param in entry["params"].items():
            if param["flag"]:
                assert param["flag"] in surface_flags, f"{name}.{dest} flag not in CLI surface"


# ----------------------------------------------------------------- progress --

@pytest.mark.parametrize("line,expected", [
    ("render step 5/40", 0.125),
    ("iter 23/33 it/s", 23 / 33),
    ("progress 67%", 0.67),
    ("plain line", None),
    ("saved 1024x768", None),
])
def test_parse_progress(line, expected):
    result = jobs.parse_progress(line)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, rel=1e-6)


# -------------------------------------------------------------------- paths --

def test_resolve_allowed_guards_traversal(tmp_state):
    ok = paths.resolve_allowed("output/thing.png")
    assert ok.is_relative_to(tmp_state)
    with pytest.raises(paths.UnsafePath):
        paths.resolve_allowed("../secrets.txt")
    # Absolute path outside the roots (platform-neutral: not a Windows-only
    # drive form — backslash paths are merely relative on POSIX).
    with pytest.raises(paths.UnsafePath):
        paths.resolve_allowed(str(tmp_state.parent / "outside_secrets.txt"))
    with pytest.raises(paths.UnsafePath):
        paths.resolve_allowed("")


# ----------------------------------------------------------------------- db --

def test_job_roundtrip(tmp_state):
    db.insert_job({"id": "abc", "workflow": "pixelart", "prompt": "p",
                   "params": {"prompt": "p"}, "argv": ["-w", "pixelart", "p"], "heavy": False})
    job = db.get_job("abc")
    assert job["status"] == "pending" and job["heavy"] == 0
    db.set_job_status("abc", "running", started_at=1.0)
    db.update_job("abc", progress=0.5)
    assert db.get_job("abc")["progress"] == 0.5
    db.upsert_output("output/a.png", "image", 1.0, 10)
    db.upsert_output("output/a.png", "image", 2.0, 20, job_id="abc", workflow="pixelart")
    db.link_recent_outputs("abc", "pixelart", since=1.5)
    assert db.outputs_for_job("abc")[0]["path"] == "output/a.png"
    db.mark_orphans_interrupted()
    assert db.get_job("abc")["status"] == "interrupted"


# ------------------------------------------------------------ job lifecycle --

def _run_scenario(coro_factory, timeout=20.0):
    async def with_deadline():
        return await asyncio.wait_for(coro_factory(), timeout=timeout)
    return asyncio.run(with_deadline())


async def _drain(manager, job_ids):
    while any(db.get_job(job_id)["status"] in ACTIVE for job_id in job_ids):
        await asyncio.sleep(0.05)
    manager._worker.cancel()
    try:
        await manager._worker
    except asyncio.CancelledError:
        pass


def test_job_lifecycle_serialized_complete(tmp_state, fake_factory):
    async def scenario():
        manager = jobs.JobManager(render=lambda name, **ctx: "")
        manager._command_prefix = lambda: [sys.executable]
        await manager.start()
        first = await manager.enqueue("pixelart", {"prompt": "first", "seed": "1"})
        second = await manager.enqueue("flowmap", {"prompt": "second"})
        await _drain(manager, [first["id"], second["id"]])
        return db.get_job(first["id"]), db.get_job(second["id"])

    job_a, job_b = _run_scenario(scenario)
    assert job_a["status"] == "complete" and job_a["exit_code"] == 0
    assert job_b["status"] == "complete"
    assert job_b["started_at"] >= job_a["ended_at"]  # serialized, one at a time
    assert job_a["progress"] == 1.0  # parsed from "step 4/4"
    assert any("step 4/4" in line for line in jobs.read_log_tail(job_a))
    assert db.outputs_for_job(job_a["id"])[0]["path"].endswith("made_by_fake.txt")


def test_job_light_skips_load_gate(tmp_state, fake_factory, monkeypatch):
    """pixelart is curated light → the gate script must never spawn."""
    async def scenario():
        real_create = asyncio.create_subprocess_exec
        gate_calls = []

        async def spy(*args, **kwargs):
            if len(args) > 1 and "check_charge" in str(args[1]):
                gate_calls.append(args)
            return await real_create(*args, **kwargs)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spy)
        manager = jobs.JobManager(render=lambda name, **ctx: "")
        manager._command_prefix = lambda: [sys.executable]
        await manager.start()
        job = await manager.enqueue("pixelart", {"prompt": "gate check"})
        await _drain(manager, [job["id"]])
        return job["id"], gate_calls

    job_id, gate_calls = _run_scenario(scenario)
    assert db.get_job(job_id)["status"] == "complete"
    assert gate_calls == []


# --------------------------------------------------------------- app/pages --

@pytest.fixture
def client(tmp_state, fake_factory):
    from server.app import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_pages_render(client):
    home = client.get("/")
    assert home.status_code == 200 and "Factory console" in home.text
    wf = client.get("/w/generate")
    assert wf.status_code == 200 and 'name="prompt"' in wf.text and "Run generate" in wf.text
    assert client.get("/library").status_code == 200
    assert client.get("/w/does_not_exist").status_code == 404


# ------------------------------------------------------------------- models --

def test_expected_models_reports_missing_and_custom(tmp_state, monkeypatch):
    from core import config as engine_config
    from server import models as models_mod

    monkeypatch.setattr(engine_config, "DEFAULT_MODEL_DIR", str(tmp_state / "models"))
    monkeypatch.setattr(engine_config, "DEFAULT_SD_MODEL", str(tmp_state / "models" / "flux.gguf"))
    (tmp_state / "models").mkdir(parents=True, exist_ok=True)
    (tmp_state / "models" / "flux.gguf").write_bytes(b"x")
    # A constant outside MODEL_DIR must be flagged "custom".
    monkeypatch.setattr(engine_config, "DEFAULT_QWEN_IMAGE21_TURBO_MODEL",
                        str(tmp_state / "elsewhere" / "turbo.gguf"))

    sections = models_mod.expected_models()
    flat = {item["constant"]: item for section in sections for item in section["items"]}
    assert flat["DEFAULT_SD_MODEL"]["present"] and flat["DEFAULT_SD_MODEL"]["size"] == 1
    assert not flat["DEFAULT_SD_MODEL"]["custom"]
    assert not flat["DEFAULT_QWEN_IMAGE21_TURBO_MODEL"]["present"]
    assert flat["DEFAULT_QWEN_IMAGE21_TURBO_MODEL"]["custom"]


def test_workflow_dependencies_cover_core_workflows():
    from server import models as models_mod

    rows = {row["workflow"]: row for row in models_mod.workflow_dependencies()}
    assert {"generate", "qwen_image", "video", "music_bg"} <= set(rows)
    assert rows["qwen_image"]["in_ui"] is True
    assert any(m["constant"] == "DEFAULT_QWEN_IMAGE21_TURBO_MODEL" for m in rows["qwen_image"]["models"])


def test_active_env_overrides_detects_set_var(tmp_state, monkeypatch):
    from core import config as engine_config
    from server import models as models_mod

    source_names = {match for match in
                    __import__("re").findall(r"os\.getenv\(\s*\"([A-Z0-9_]+)\"",
                                             Path(engine_config.__file__).read_text(encoding="utf-8"))}
    assert "SD_MODEL_PATH" in source_names  # sanity: the parse target exists
    monkeypatch.setenv("SD_MODEL_PATH", str(tmp_state / "custom_flux.gguf"))
    overrides = {item["env"]: item for item in models_mod.active_env_overrides()}
    assert overrides["SD_MODEL_PATH"]["constant"] == "DEFAULT_SD_MODEL"


def test_active_env_overrides_match_multiline_getenv(monkeypatch):
    """Regression pin (Kilo review false CRITICAL): the override regex must
    match the multi-line parenthesized os.getenv( form used by config.py —
    e.g. DEFAULT_QWEN_IMAGE21_TURBO_MODEL spans three lines."""
    from server import models as models_mod

    monkeypatch.setenv("QWEN_IMAGE21_TURBO_MODEL_PATH", r"C:\Modeles_LLM\Qwen-Image-2.1-Turbo-Q8_0.gguf")
    overrides = {item["env"]: item for item in models_mod.active_env_overrides()}
    assert overrides["QWEN_IMAGE21_TURBO_MODEL_PATH"]["constant"] == "DEFAULT_QWEN_IMAGE21_TURBO_MODEL"


def test_models_page_renders(client, tmp_state, monkeypatch):
    from core import config as engine_config

    monkeypatch.setattr(engine_config, "DEFAULT_MODEL_DIR", str(tmp_state / "models"))
    response = client.get("/models")
    assert response.status_code == 200
    assert "Workflow dependencies" in response.text and "LoRAs" in response.text
    full = client.get("/models", params={"inventory": "1"})
    assert full.status_code == 200 and "files ·" in full.text


# ------------------------------------------------------------------- veille --

@pytest.fixture
def veille_files(tmp_state, monkeypatch):
    """Fake veille artifacts (module paths are module-level → patchable)."""
    from server import veille as veille_mod

    monkeypatch.setattr(veille_mod, "PENDING_PATH", tmp_state / "maj.json")
    monkeypatch.setattr(veille_mod, "STATE_PATH", tmp_state / "etat.json")
    monkeypatch.setattr(veille_mod, "JOURNAL_PATH", tmp_state / "journal.md")
    notes_dir = tmp_state / "notes"
    notes_dir.mkdir()
    monkeypatch.setattr(veille_mod, "NOTES_DIR", notes_dir)
    return veille_mod


def test_veille_pending_and_state(veille_files, tmp_state):
    mod = veille_files
    tmp_state.joinpath("maj.json").write_text(json.dumps({
        "detecte_le": "2026-10-11 12:42",
        "items": [{"composant": "sd-cli", "installee": "945", "nouvelle": "956"}],
    }), encoding="utf-8")
    tmp_state.joinpath("etat.json").write_text(json.dumps({
        "audio.cpp": {"installee": "v0.9.1", "derniere_vue": "v0.9.1"},
        "sd_cli": {"installe": "a1ded76", "derniere_vue": "1b0ba10"},
        "paquets_python": {"obsolete": ["numpy"]},
        "org_audio_cpp": {"repos": {"x": 1}},  # inventory-only → skipped
    }), encoding="utf-8")

    pend = mod.pending()
    assert pend["count"] == 1 and pend["items"][0]["composant"] == "sd-cli"
    rows = {row["name"]: row for row in mod.state()["rows"]}
    assert rows["audio.cpp"]["upstream_newer"] is False
    assert rows["sd_cli"]["upstream_newer"] is True
    assert rows["paquets_python"]["obsolete"] == ["numpy"]
    assert "org_audio_cpp" not in rows


def test_veille_journal_parsing(veille_files, tmp_state):
    mod = veille_files
    tmp_state.joinpath("journal.md").write_text(
        "# Watch Journal\n\n"
        "- **2026-10-11 (~12:4x, user \"merge\") • PR #11 MERGED** — body one with [link](https://x).\n"
        "  continuation line ignored (bullets are single-line by format).\n"
        "- **2026-10-10 • EARLIER ENTRY** — body two.\n",
        encoding="utf-8")
    entries = mod.journal_entries()
    assert len(entries) == 2
    assert entries[0]["date"] == "2026-10-11"
    assert entries[0]["title"].startswith("2026-10-11")
    assert entries[0]["body"].startswith("body one")


def test_veille_page_and_dashboard_badge(client, veille_files, tmp_state):
    tmp_state.joinpath("maj.json").write_text(json.dumps({
        "detecte_le": "2026-10-11 12:42",
        "items": [{"composant": "sd-cli"}],
    }), encoding="utf-8")
    page = client.get("/veille")
    assert page.status_code == 200
    assert "Pending updates" in page.text and "sd-cli" in page.text
    assert "never automatic update" in page.text
    dashboard = client.get("/")
    assert "pending update" in dashboard.text  # amber banner when items exist


def test_jobs_page_renders_with_actions(client):
    client.post("/api/jobs", data={"workflow": "pixelart", "prompt": "hist", "seed": "7"})
    page = client.get("/jobs")
    assert page.status_code == 200 and "pixelart" in page.text
    filtered = client.get("/jobs", params={"status": "pending"})
    assert filtered.status_code == 200


def test_workflow_form_covers_every_catalog_entry(client):
    for name in introspection.workflow_names():
        response = client.get(f"/w/{name}")
        assert response.status_code == 200, name
        assert f'name="workflow" value="{name}"' in response.text


def test_files_endpoint_guards_traversal(client):
    target = paths.ALLOWED_ROOTS[0] / "x.png"
    target.write_bytes(b"png")
    ok = client.get("/files", params={"p": "output/x.png"})
    assert ok.status_code == 200 and ok.content == b"png"
    assert client.get("/files", params={"p": "../pyproject.toml"}).status_code == 403
    assert client.get("/files", params={"p": "output/missing.png"}).status_code == 404
    ranged = client.get("/files", params={"p": "output/x.png"}, headers={"Range": "bytes=0-1"})
    assert ranged.status_code == 206 and ranged.content == b"pn"


def test_upload_and_picker(client):
    upload = client.post("/api/uploads", files={"file": ("ref.png", b"\x89PNG", "image/png")})
    assert upload.status_code == 200
    body = upload.json()
    assert body["ok"]
    uploaded = Path(body["path"])
    if not uploaded.is_absolute():
        uploaded = paths.REPO_ROOT / uploaded
    assert uploaded.exists()
    picker = client.get("/partials/file-picker", params={"field": "input", "kind": "image"})
    assert picker.status_code == 200 and "ga-pick" in picker.text


def test_create_job_via_form(client):
    response = client.post("/api/jobs", data={"workflow": "pixelart", "prompt": "tiny sprite", "seed": "42"})
    assert response.status_code == 200
    assert "pixelart" in response.text
    listed = client.get("/api/jobs").json()
    assert any(job["workflow"] == "pixelart" for job in listed["jobs"])


# ------------------------------------------------------------------ vendor --

def test_vendored_assets_match_pins():
    spec_module = importlib.util.spec_from_file_location(
        "vendor_webui_assets", REPO_ROOT / "scripts" / "vendor_webui_assets.py")
    vendor = importlib.util.module_from_spec(spec_module)
    spec_module.loader.exec_module(vendor)
    for name, spec in vendor.PINNED.items():
        if not spec["sha256"]:
            continue
        path: Path = spec["dest"]
        assert path.exists(), f"vendored asset missing: {path}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == spec["sha256"], f"{name} sha256 drifted"
