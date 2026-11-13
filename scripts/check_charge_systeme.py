"""System load pre-check before model launch (CPU / GPU / RAM / Commit / VRAM).

To run BEFORE any heavy generation (audio.cpp, sd-cli, trellis.cpp…) so as not
to launch during a heavy load (see RTF skewed by GPU contention on 2026-09-08)
or near Windows Commit Charge exhaustion (caught on 2026-11-13).

Zero dependency: everything goes through PowerShell/WMI (GPU counters
"GPUPerformanceCounters", insensitive to the Windows language, unlike Get-Counter).

Usage:
    uv run python scripts/check_charge_systeme.py
    uv run python scripts/check_charge_systeme.py --cpu-threshold 40 --duration 5

Return codes: 0 = machine available (can launch) • 1 = load too heavy
(wait for a free slot) • 2 = measurement error.
"""

import argparse
import statistics
import subprocess
import sys

SEUILS_DEFAUT: dict[str, float] = {
    "cpu": 60.0,
    "ram": 90.0,
    "commit": 85.0,
    "gpu": 40.0,
    "vram": 80.0,
}

# Force stdout/stderr to UTF-8: on Windows, as soon as this script is invoked other
# than from a real console (captured subprocess, scheduled task, output
# redirected to a file), Python falls back to the system encoding (cp1252 here)
# instead of UTF-8 — and cp1252 cannot encode the emojis used below
# (🔍 ✅ ⛔ ⚠️), which makes the script crash before its first print.
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

# Single PowerShell script: 3 spaced samples + 2 process snapshots (CPU delta)
# + VRAM capacity (registry, the uint32 AdapterRAM class caps at 4 GiB).
#
# GPU: GPUEngine exposes one counter instance PER PROCESS AND PER ENGINE TYPE
# (3D, Copy, VideoDecode, VideoEncode, VideoProcessing…). Summing UtilizationPercentage
# over ALL instances (like before) is not a valid GPU occupancy: each
# engine can reach 100 % independently, so an idle GPU can display 200-400 %
# with just DWM/explorer/Windows Update/the indexer running in the background
# (typical in the minutes following a reboot). Fix: we group by engine type
# (regex on Name, e.g. "...engtype_3D"), we sum WITHIN each group (several
# processes can legitimately share the same engine), then we take the MAX across
# groups — not the sum, the engines run in parallel on distinct hardware
# blocks. The result reflects the busiest engine, typically 0-5 % at rest.
_PS_SCRIPT = r"""
$ErrorActionPreference = 'Continue'
$num = 3
$intervalMs = __INTERVAL_MS__
for ($i = 0; $i -lt $num; $i++) {
  if ($i -gt 0) { Start-Sleep -Milliseconds $intervalMs }
  $cpu = $null; $ram = $null; $commit = $null; $commitUsedGb = $null; $commitLimGb = $null; $gpu = $null; $vramDed = $null
  try { $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Average -Property LoadPercentage).Average } catch {}
  try {
    $os = Get-CimInstance Win32_OperatingSystem
    if ($os.TotalVisibleMemorySize -gt 0) { $ram = 100.0 * (1.0 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize) }
    if ($os.TotalVirtualMemorySize -gt 0) {
      $commit = 100.0 * (1.0 - $os.FreeVirtualMemory / $os.TotalVirtualMemorySize)
      $commitUsedGb = ($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1048576.0
      $commitLimGb = $os.TotalVirtualMemorySize / 1048576.0
    }
  } catch {}
  try {
    $gpu = (Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine |
            Group-Object { if ($_.Name -match 'engtype_(\w+)') { $matches[1] } else { 'Autre' } } |
            ForEach-Object { ($_.Group | Measure-Object -Sum -Property UtilizationPercentage).Sum } |
            Measure-Object -Maximum).Maximum
  } catch {}
  try {
    $adapters = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory
    $vramDed = ($adapters | Measure-Object -Sum -Property DedicatedUsage).Sum
  } catch {}
  "SAMPLE;$cpu;$ram;$gpu;$vramDed;$commit;$commitUsedGb;$commitLimGb"
}
$p1 = Get-CimInstance Win32_Process | Select-Object ProcessId,Name,WorkingSetSize,@{n='t';e={$_.UserModeTime + $_.KernelModeTime}}
foreach ($p in $p1) { "PROC1;$($p.ProcessId);$($p.Name);$($p.WorkingSetSize);$($p.t)" }
Start-Sleep -Milliseconds $intervalMs
$p2 = Get-CimInstance Win32_Process | Select-Object ProcessId,Name,WorkingSetSize,@{n='t';e={$_.UserModeTime + $_.KernelModeTime}}
foreach ($p in $p2) { "PROC2;$($p.ProcessId);$($p.Name);$($p.WorkingSetSize);$($p.t)" }
try {
  $cap = 0
  $cle = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
  foreach ($k in (Get-ChildItem $cle -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^\d{4}$' })) {
    $v = (Get-ItemProperty $k.PSPath -Name 'HardwareInformation.qwMemorySize' -ErrorAction SilentlyContinue).'HardwareInformation.qwMemorySize'
    if ($v) { $cap += [long]$v }
  }
  "VRAMCAP;$cap"
} catch { "VRAMCAP;0" }
$nproc = (Get-CimInstance Win32_Processor | Measure-Object -Sum -Property NumberOfLogicalProcessors).Sum
"NPROC;$nproc"
"""


def _measure(duration_s: float) -> dict:
    """Runs the PowerShell script and returns the parsed metrics."""
    interval_ms = int(duration_s * 1000 / 3)
    ps = _PS_SCRIPT.replace("__INTERVAL_MS__", str(interval_ms))
    res = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, timeout=120,
    )
    if res.returncode != 0:
        raise RuntimeError(f"PowerShell failed (exit {res.returncode}): {res.stderr.strip()[:300]}")

    data = {"samples": [], "vram_cap": 0, "nproc": 1, "proc1": {}, "proc2": {}, "interval_ms": interval_ms}
    for ligne in res.stdout.splitlines():
        ligne = ligne.strip()
        if ligne.startswith("SAMPLE;"):
            morceaux = ligne.split(";")
            if len(morceaux) < 5:
                continue

            def _f(v: str):
                v = v.replace(",", ".")
                try:
                    return float(v)
                except ValueError:
                    return None  # empty if the counter failed on this sample

            champs = ("cpu", "ram", "gpu", "vram", "commit", "commit_used_gib", "commit_lim_gib")
            echantillon = {k: None for k in champs}
            for k, v in zip(champs, morceaux[1:8]):
                echantillon[k] = _f(v)
            data["samples"].append(echantillon)
        elif ligne.startswith(("PROC1;", "PROC2;")):
            _, pid, nom, wss, t = ligne.split(";", 4)
            try:
                data["proc1" if ligne.startswith("PROC1;") else "proc2"][int(pid)] = (nom, int(wss), int(t))
            except ValueError:
                pass
        elif ligne.startswith("VRAMCAP;"):
            data["vram_cap"] = int(ligne.split(";", 1)[1] or 0)
        elif ligne.startswith("NPROC;"):
            data["nproc"] = max(1, int(ligne.split(";", 1)[1] or 1))
    if not data["samples"]:
        raise RuntimeError("No usable sample received from PowerShell")
    return data


def _top_processes(data: dict) -> list[tuple[str, float, int]]:
    """Top processes by % CPU (kernel+user time delta between the 2 snapshots)."""
    tops = []
    for pid, (nom, wss, t1) in data["proc1"].items():
        if nom == "System Idle Process":
            continue
        if pid in data["proc2"] and data["proc2"][pid][0] == nom:
            dt_s = (data["proc2"][pid][2] - t1) / 1e7  # 100 ns → s
            pct = 100.0 * dt_s / (data["interval_ms"] / 1000.0) / data["nproc"]
            tops.append((nom, pct, wss))
    tops.sort(key=lambda x: -x[1])
    return tops[:5]


def evaluer_seuils(
    mesures: dict[str, float | None],
    seuils: dict[str, float] | None = None,
) -> list[str]:
    """Returns the metric keys whose measured percentage meets or exceeds their threshold."""
    cibles = seuils or SEUILS_DEFAUT
    return [
        cle
        for cle, seuil in cibles.items()
        if mesures.get(cle) is not None and mesures[cle] >= seuil  # type: ignore[operator]
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="Load pre-check before generation")
    ap.add_argument("--cpu-threshold", type=float, default=SEUILS_DEFAUT["cpu"], help="CPU threshold %% (default 60)")
    ap.add_argument("--gpu-threshold", type=float, default=SEUILS_DEFAUT["gpu"], help="GPU threshold %% (default 40)")
    ap.add_argument("--ram-threshold", type=float, default=SEUILS_DEFAUT["ram"], help="RAM threshold %% (default 90)")
    ap.add_argument(
        "--commit-threshold",
        type=float,
        default=SEUILS_DEFAUT["commit"],
        help="Windows Commit Charge threshold %% (default 85)",
    )
    ap.add_argument("--vram-threshold", type=float, default=SEUILS_DEFAUT["vram"], help="VRAM threshold %% (default 80)")
    ap.add_argument("--duration", type=float, default=3.0, help="sampling duration in s (default 3)")
    args = ap.parse_args()

    try:
        data = _measure(args.duration)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"❌ Measurement error: {exc}")
        return 2

    def _moy(cle: str, cap: float | None = None) -> float | None:
        vals = [s[cle] for s in data["samples"] if s[cle] is not None]
        if not vals:
            return None
        # Cap EVERY sample before the mean (not only the final result):
        # more honest if an isolated sample spikes, and consistent with the
        # GPU per-engine aggregation fix (max of the groups, already bounded
        # at ~100 in practice, but we keep the safety net).
        if cap is not None:
            vals = [min(v, cap) for v in vals]
        return statistics.mean(vals)

    cpu, ram, gpu, vram_octets = _moy("cpu"), _moy("ram"), _moy("gpu", 100.0), _moy("vram")
    commit = _moy("commit")
    commit_used = _moy("commit_used_gib")
    commit_lim = _moy("commit_lim_gib")
    vram_pct = (
        100.0 * vram_octets / data["vram_cap"]
        if vram_octets is not None and data["vram_cap"] > 0
        else None
    )

    seuils = {
        "cpu": args.cpu_threshold,
        "ram": args.ram_threshold,
        "commit": args.commit_threshold,
        "gpu": args.gpu_threshold,
        "vram": args.vram_threshold,
    }
    mesures = {
        "cpu": cpu,
        "ram": ram,
        "commit": commit,
        "gpu": gpu,
        "vram": vram_pct,
    }
    depasses = evaluer_seuils(mesures, seuils)
    depasses_set = set(depasses)
    labels = {"cpu": "CPU ", "ram": "RAM ", "commit": "Commit", "gpu": "GPU ", "vram": "VRAM"}

    def _afficher(cle: str, suffix: str = "%") -> None:
        label = labels[cle]
        val = mesures[cle]
        threshold = seuils[cle]
        if val is None:
            print(f"⚠️  {label}: measurement unavailable (ignored)")
            return
        bloque = cle in depasses_set
        etat = "HIGH" if bloque else "OK"
        print(f"{'⛔' if bloque else '✅'} {label}: {val:.1f}{suffix} (threshold {threshold:g}{suffix}) — {etat}")

    print(f"🔍 System load ({len(data['samples'])} samples over {args.duration:g} s):")
    _afficher("cpu")
    _afficher("ram")
    if commit_used is not None and commit_lim is not None:
        print(f"   Commit Charge: {commit_used:.1f} / {commit_lim:.1f} GiB")
    _afficher("commit")
    _afficher("gpu")
    if vram_octets is not None:
        vram_gio = vram_octets / 2**30
        if data["vram_cap"] > 0:
            print(f"   Dedicated VRAM: {vram_gio:.1f} / {data['vram_cap'] / 2**30:.0f} GiB")
            _afficher("vram")
        else:
            print(f"⚠️  VRAM: {vram_gio:.1f} GiB dedicated (unknown capacity, threshold ignored)")

    tops = _top_processes(data)
    if tops:
        detail = " | ".join(f"{n} {p:.0f}% ({w / 2**30:.1f} GiB)" for n, p, w in tops if p > 1)
        if detail:
            print(f"🔎 Top CPU processes: {detail}")

    if depasses:
        depasses_labels = [labels[k] for k in depasses]
        print(f"\n⛔ VERDICT: machine busy ({', '.join(depasses_labels)}) — DO NOT launch a generation now.")
        return 1
    print("\n✅ VERDICT: machine available — launch possible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
