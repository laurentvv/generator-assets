#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for bugs fixed during the /revue audit."""

import asyncio
import json
import struct
import sys
import wave
from pathlib import Path
from subprocess import CompletedProcess

import numpy as np
from PIL import Image

from core import audio_ops, config, diffusion, process, voix_indextts
from server import assets, db, events, jobs, paths


def test_db_search_and_count_outputs_workflow_precedence(tmp_path, monkeypatch):
    """(workflow = ? OR path LIKE ?) must be parenthesized so kind/query filters hold."""
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    db.reset_for_tests(tmp_path / "factory.db")
    try:
        db.upsert_output("output/music_bg/track.wav", "audio", 1.0, 100, workflow="music_bg")
        db.upsert_output("output/music_bg/cover.png", "image", 2.0, 200, workflow="music_bg")
        db.upsert_output("output/generate/sword.png", "image", 3.0, 300, workflow="generate")

        items = db.search_outputs(kind="image", workflow="music_bg")
        assert [i["path"] for i in items] == ["output/music_bg/cover.png"]
        assert db.count_outputs(kind="image", workflow="music_bg") == 1
        assert db.count_outputs(workflow="music_bg") == 2
        assert db.count_outputs(workflow="generate") == 1
    finally:
        db.close_for_tests()


def test_waveform_decodes_signed_16bit_pcm(tmp_path, monkeypatch):
    """Quiet negative 16-bit PCM (-1 == 0xFFFF) must NOT saturate bars to full height."""
    monkeypatch.setattr(paths, "THUMB_DIR", tmp_path / "thumbs")
    (tmp_path / "thumbs").mkdir()
    wav_path = tmp_path / "signed_test.wav"

    # First half: very quiet negative samples (-2); second half: loud peak (+28000)
    samples = [-2] * 4000 + [28000, -28000] * 2000
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    url = assets.waveform(wav_path, bars=40, width=160, height=80, create=True)
    assert url is not None
    png = paths.THUMB_DIR / Path(url).name
    with Image.open(png) as img:
        arr = np.array(img)
    # Count amber bar pixels (R > 100) in left half (quiet) vs right half (loud)
    amber = arr[:, :, 0] > 100
    quiet_pixels = int(amber[:, :70].sum())
    loud_pixels = int(amber[:, 90:].sum())
    assert loud_pixels > quiet_pixels * 5


def test_event_hub_serializes_dict_as_valid_json():
    """SSE dict events must be valid JSON strings, not Python reprs."""
    hub = events.EventHub()
    q = hub.subscribe()
    hub.publish("notify", {"kind": "complete", "workflow": "pixelart", "id": "abc"})
    item = q.get_nowait()
    assert item["event"] == "notify"
    assert isinstance(item["data"], str)
    parsed = json.loads(item["data"])
    assert parsed == {"kind": "complete", "workflow": "pixelart", "id": "abc"}


def test_job_manager_flushes_trailing_stdout_without_newline(tmp_path, monkeypatch):
    """A subprocess exiting without a trailing newline must still have its last line logged."""
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    monkeypatch.setattr(paths, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(paths, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(paths, "THUMB_DIR", tmp_path / "thumbs")
    factory = tmp_path / "factory"
    factory.mkdir()
    (factory / "output").mkdir()
    (factory / "main.py").write_text(
        "import sys\nsys.stdout.write('step 2/4 final_no_newline')\nsys.stdout.flush()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "REPO_ROOT", factory)
    monkeypatch.setattr(paths, "ALLOWED_ROOTS", (factory / "output",))
    db.reset_for_tests(tmp_path / "factory.db")

    async def scenario():
        mgr = jobs.JobManager(render=lambda name, **ctx: "")
        mgr._command_prefix = lambda: [sys.executable]
        await mgr.start()
        job = await mgr.enqueue("pixelart", {"prompt": "trail"})
        while db.get_job(job["id"])["status"] in ("pending", "running"):
            await asyncio.sleep(0.05)
        await mgr.stop()
        return db.get_job(job["id"])

    try:
        done = asyncio.run(asyncio.wait_for(scenario(), timeout=15.0))
        lines = jobs.read_log_tail(done)
        assert any("final_no_newline" in line for line in lines)
    finally:
        db.close_for_tests()


def test_generer_image_vulkan_chroma_omits_clip_l_and_vae_tiling(tmp_path, monkeypatch):
    """Chroma1-HD (§1.37) is T5-only (no --clip_l) and full-frame decode (no --vae-tiling)."""
    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(list(cmd))
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (4, 4), (10, 20, 30)).save(out, "PNG")
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(process.subprocess, "run", fake_run)

    diffusion.generer_image_vulkan(
        "gothic abbey",
        sd_cli="fake-sd-cli",
        sd_model=str(tmp_path / "Chroma1-HD-Q8_0.gguf"),
    )
    chroma_cmd = captured[-1]
    assert "--clip_l" not in chroma_cmd
    assert "--vae-tiling" not in chroma_cmd
    assert "--t5xxl" in chroma_cmd
    assert "--vae" in chroma_cmd

    diffusion.generer_image_vulkan(
        "gothic abbey",
        sd_cli="fake-sd-cli",
        sd_model=str(tmp_path / "flux1-dev-Q6_K.gguf"),
    )
    flux_cmd = captured[-1]
    assert "--clip_l" in flux_cmd
    assert "--vae-tiling" in flux_cmd


def test_resoudre_sd_model_searches_secondary_model_dirs(tmp_path, monkeypatch):
    """--sd-model chroma must find checkpoints stored on the cold secondary dir (D:)."""
    hot = tmp_path / "hot"
    cold = tmp_path / "cold"
    hot.mkdir()
    cold.mkdir()
    chroma = cold / "Chroma1-HD-Q8_0.gguf"
    chroma.write_bytes(b"gguf")

    monkeypatch.setattr(config, "DEFAULT_MODEL_DIR", str(hot))
    monkeypatch.setattr(config, "MODEL_DIRS", [str(hot), str(cold)])
    assert config.resoudre_sd_model("chroma") == str(chroma)


def test_exporter_ambiance_godot_uses_ffmpeg_ogg(tmp_path, monkeypatch):
    """exporter_ambiance_godot must encode OGG through convertir_ogg (ffmpeg), never libsndfile."""
    from core import music_ai

    calls = []

    def fake_convertir_ogg(wav_in, ogg_out, **kwargs):
        calls.append((wav_in, ogg_out))
        Path(ogg_out).write_bytes(b"OggS")
        return ogg_out

    monkeypatch.setattr(music_ai, "convertir_ogg", fake_convertir_ogg)
    stereo = np.zeros((4410, 2), dtype=np.float32)
    wav_p, ogg_p, bus_p = audio_ops.exporter_ambiance_godot("cave", str(tmp_path), stereo, sr=44100)
    assert len(calls) == 1
    assert Path(wav_p).exists() and Path(ogg_p).exists() and Path(bus_p).exists()


def test_voix_indextts_uses_resolved_ffmpeg(tmp_path, monkeypatch):
    """mesurer_lufs and normaliser_reference must use resoudre_ffmpeg(), not bare 'ffmpeg'."""
    wav = tmp_path / "quiet.wav"
    wav.write_bytes(b"RIFF")
    seen_bins = []

    def fake_run(cmd, **kwargs):
        seen_bins.append(cmd[0])
        if "ebur128" in " ".join(cmd):
            return CompletedProcess(cmd, 0, stdout="", stderr="I: -35.0 LUFS\n")
        Path(cmd[-1]).write_bytes(b"RIFF")
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(voix_indextts, "resoudre_ffmpeg", lambda: r"C:\custom\ffmpeg.exe")
    monkeypatch.setattr(voix_indextts, "run_engine", fake_run)

    out = voix_indextts.normaliser_reference(str(wav))
    assert out.endswith("_ttsnorm.wav")
    assert seen_bins == [r"C:\custom\ffmpeg.exe", r"C:\custom\ffmpeg.exe"]


def test_music_bg_accepts_force_bpm_and_sanitizes_output_path(tmp_path, monkeypatch):
    """--force-bpm (dest=force_bpm) must reach ACE-Step, and -o path/name must not crash."""
    from workflows import music_bg

    captured = {}

    def fake_acestep(**kwargs):
        captured["bpm"] = kwargs["bpm"]
        Path(kwargs["chemin_sortie"]).write_bytes(b"wav")
        return kwargs["chemin_sortie"], "vulkan"

    monkeypatch.setattr(music_bg, "resoudre_audiocpp", lambda: str(tmp_path / "audiocpp.exe"))
    (tmp_path / "audiocpp.exe").write_bytes(b"exe")
    monkeypatch.setattr(music_bg, "generer_musique_acestep", fake_acestep)
    monkeypatch.setattr(music_bg, "empreinte_fichier", lambda p: "abc")
    monkeypatch.setattr(music_bg, "charger_audio", lambda p: (np.zeros((4800, 2), dtype=np.float32), 48000))
    monkeypatch.setattr(music_bg, "fabriquer_boucle", lambda a, sr, **kw: (a, {"bpm": 83.0, "duree": 12.0, "strategie": "percussive"}))
    monkeypatch.setattr(music_bg, "post_traiter_lit_voix", lambda a, sr: a)
    monkeypatch.setattr(music_bg, "ressampler", lambda a, sr, target: (a, target))
    monkeypatch.setattr(music_bg, "normaliser_pic", lambda a, db: a)
    monkeypatch.setattr(music_bg, "verifier_boucle", lambda p: {"propre": True, "ecart_couture_db": 0.5, "pic_dbfs": -1.0})
    monkeypatch.setattr(music_bg, "mesurer_lufs", lambda p: {"I": -14.0, "TP": -1.0})
    monkeypatch.setattr(music_bg, "declick_fichier_wav", lambda p: p)
    monkeypatch.setattr(music_bg, "exporter_bed_lufs", lambda src, dst, lufs: (Path(dst).write_bytes(b"bed"), {"I": lufs, "TP": -1.0})[1])
    monkeypatch.setattr(music_bg, "convertir_ogg", lambda src, dst: (Path(dst).write_bytes(b"ogg"), dst)[1])
    monkeypatch.setattr(music_bg, "convertir_mp3", lambda src, dst: (Path(dst).write_bytes(b"mp3"), dst)[1])

    wf = music_bg.MusicBgWorkflow({})
    res = wf.run({
        "prompt": "gothic rock",
        "force_bpm": 83,
        "candidats": 1,
        "output": "nested/dir/my_track.wav",
        "output_dir": str(tmp_path / "out"),
    })
    assert captured["bpm"] == 83
    assert Path(res["wav_full"]).name == "my_track_full.wav"
    assert Path(res["wav_full"]).exists()


def test_nvme_staging_shared_used_by_moss_and_lfm3(tmp_path, monkeypatch):
    """Cold D: weights for MOSS-Image and LFM3-TTS are staged to NVMe and cleaned up."""
    from types import SimpleNamespace
    from core import nvme_staging, voix_lfm3

    cold = tmp_path / "cold"
    nvme = tmp_path / "nvme"
    cold.mkdir()
    nvme.mkdir()
    for name in ("moss.gguf", "llm.gguf", "vae.safetensors", "tok.json", "lfm3.gguf", "mmproj.gguf"):
        (cold / name).write_bytes(b"DATA" * 64)
    fake_exe = tmp_path / "fake.exe"
    fake_exe.write_bytes(b"EXE")

    cold_prefix = str(cold.resolve()).lower()
    nvme_prefix = str(nvme.resolve()).lower()

    def fake_splitdrive(p: str):
        norm = str(Path(p).resolve()).lower()
        if norm.startswith(cold_prefix):
            return ("D:", p[len(str(cold)):])
        if norm.startswith(nvme_prefix):
            return ("C:", p[len(str(nvme)):])
        return ("C:", p)

    monkeypatch.setattr(nvme_staging.os.path, "splitdrive", fake_splitdrive)
    monkeypatch.setattr(nvme_staging.shutil, "disk_usage", lambda _p: SimpleNamespace(total=10**11, used=0, free=10**11))
    monkeypatch.setattr(nvme_staging, "DEFAULT_MODEL_DIR", str(nvme))
    # Default parameter binding on stager_vers_nvme_temporaire uses DEFAULT_MODEL_DIR at def time;
    # wrap to point nvme_root to tmp nvme.
    real_stager = nvme_staging.stager_vers_nvme_temporaire
    monkeypatch.setattr(diffusion, "stager_vers_nvme_temporaire", lambda paths, **kw: real_stager(paths, nvme_root=str(nvme), min_free_margin_bytes=0, **kw))
    monkeypatch.setattr(voix_lfm3, "stager_vers_nvme_temporaire", lambda paths, **kw: real_stager(paths, nvme_root=str(nvme), min_free_margin_bytes=0, **kw))

    seen_cmds = []

    def fake_run(cmd, **kwargs):
        seen_cmds.append(list(cmd))
        out = cmd[cmd.index("-o") + 1]
        if out.endswith(".png"):
            Image.new("RGB", (4, 4), (50, 100, 150)).save(out, "PNG")
        else:
            Path(out).write_bytes(b"RIFF")
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(process.subprocess, "run", fake_run)

    diffusion.generer_image_moss(
        "test poster",
        sd_cli=str(fake_exe),
        model=str(cold / "moss.gguf"),
        llm=str(cold / "llm.gguf"),
        vae=str(cold / "vae.safetensors"),
        tokenizer=str(cold / "tok.json"),
        output_path=str(tmp_path / "moss_out.png"),
    )
    moss_model_arg = seen_cmds[-1][seen_cmds[-1].index("--diffusion-model") + 1]
    assert str(nvme) in moss_model_arg and "_tmp_moss_" in moss_model_arg
    assert not list(nvme.glob("_tmp_moss_*"))

    voix_lfm3.generer_voix_lfm3(
        "bonjour",
        sortie=str(tmp_path / "lfm3.wav"),
        llama_tts=str(fake_exe),
        modele=str(cold / "lfm3.gguf"),
        mmproj=str(cold / "mmproj.gguf"),
    )
    lfm3_model_arg = seen_cmds[-1][seen_cmds[-1].index("-m") + 1]
    assert str(nvme) in lfm3_model_arg and "_tmp_lfm3_" in lfm3_model_arg
    assert not list(nvme.glob("_tmp_lfm3_*"))


def test_chroma_img2img_luminance_guard_warns_on_white_collapse(tmp_path, monkeypatch, capsys):
    """Chroma1-HD img2img post-render guard flags mean > 240 & std < 10 (§1.37)."""
    white = Image.new("RGB", (32, 32), (255, 255, 255))
    healthy = Image.fromarray(np.tile(np.arange(0, 256, 8, dtype=np.uint8), (32, 1)))
    assert diffusion.verifier_luminosite_image(white)["white_collapse"] is True
    assert diffusion.verifier_luminosite_image(white)["healthy"] is False
    assert diffusion.verifier_luminosite_image(healthy)["healthy"] is True

    init_img = tmp_path / "init.png"
    healthy.save(init_img, "PNG")

    def fake_run(cmd, **kwargs):
        out = cmd[cmd.index("-o") + 1]
        white.save(out, "PNG")
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    diffusion.generer_image_vulkan(
        "refine scene",
        sd_cli="fake-sd-cli",
        sd_model=str(tmp_path / "Chroma1-HD-Q8_0.gguf"),
        init_img=str(init_img),
        strength=0.35,
    )
    captured = capsys.readouterr().out
    assert "Chroma1-HD img2img guard" in captured and "white collapse" in captured


def test_cpu_utility_workflows_marked_light_in_webui_catalog():
    """Pure CPU utility workflows must skip the GPU load gate in WebUI."""
    from server import introspection

    introspection.catalog.cache_clear()
    cat = introspection.catalog()["workflows"]
    for wf in ("alpha_qa", "beat_sync", "gif_export", "icon_lottie", "doc_texte", "son_convertir", "miniature"):
        assert cat[wf]["heavy"] is False, f"{wf} should be marked light (heavy=False)"
    assert cat["sous_titres"]["heavy"] is True
    assert "st_mode" in {p["dest"] for p in cat["sous_titres"]["primary"]}


def test_consumer_presets_apply_defaults_without_overriding_explicit_flags():
    """Consumer presets fill unset/sentinel values, respect explicit flags, and check commercial tier."""
    from cli.parser import construire_params, construire_parseur, dests_explicites
    from core.presets import appliquer_preset

    parser = construire_parseur()
    argv = ["-w", "music_bg", "ambient bed", "--preset", "doc2video", "--lufs", "-24"]
    args = parser.parse_args(argv)
    params = construire_params(args, "ambient bed")
    explicites = dests_explicites(parser, argv)
    assert "lufs" in explicites and "loop_mode" not in explicites

    logs = []
    merged = appliquer_preset("music_bg", params, "doc2video", explicites=explicites, log_fn=logs.append)
    assert merged["lufs"] == -24.0  # explicit flag preserved
    assert merged["loop_mode"] == "ambient"  # doc2video preset applied over sentinel 'percussive'
    assert not any("Commercial clearance warning" in line for line in logs)

    # Non-commercial workflow with --preset doc2video emits a warning
    warn_logs = []
    appliquer_preset("qwen_image", {"prompt": "poster"}, "doc2video", log_fn=warn_logs.append)
    assert any("Commercial clearance warning" in line for line in warn_logs)

    # Godot preset applies mesh_ia decimation target
    godot_mesh = appliquer_preset("mesh_ia", {"prompt": "shield", "res": 512}, "godot", log_fn=lambda _: None)
    assert godot_mesh["faces_cible"] == 15000


def test_verifier_prerequis_workflow_targeted_check(tmp_path, monkeypatch):
    """verifier_prerequis_workflow checks only the target workflow's assets/binaries."""
    # Pure CPU workflow passes with zero heavy model prerequisites
    cpu_res = config.verifier_prerequis_workflow("alpha_qa", {})
    assert cpu_res["ok"] is True
    assert cpu_res["checked"] == []

    # Targeted workflow reports missing and present assets accurately
    fake_exe = tmp_path / "audiocpp.exe"
    fake_model = tmp_path / "indextts.gguf"
    fake_ff = tmp_path / "ffmpeg.exe"
    fake_exe.write_bytes(b"e")
    fake_ff.write_bytes(b"f")

    monkeypatch.setattr(config, "DEFAULT_AUDIOCPP_CLI", str(fake_exe))
    monkeypatch.setattr(config, "DEFAULT_INDEXTTS25_MODEL", str(fake_model))
    monkeypatch.setattr(config, "DEFAULT_FFMPEG", str(fake_ff))

    res_missing = config.verifier_prerequis_workflow("indextts25_tts", {})
    assert res_missing["ok"] is False
    assert any("IndexTTS2.5 model" in m for m in res_missing["missing"])

    fake_model.write_bytes(b"m")
    res_ok = config.verifier_prerequis_workflow("indextts25_tts", {})
    assert res_ok["ok"] is True
    assert res_ok["missing"] == []

