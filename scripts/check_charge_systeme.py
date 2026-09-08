"""Pré-vérification de charge système avant lancement de modèle (CPU / GPU / RAM / VRAM).

À exécuter AVANT toute génération lourde (audio.cpp, sd-cli, trellis.cpp…) pour ne pas
lancer pendant une charge importante (cf. RTF faussé par contention GPU le 2026-09-08).

Zéro dépendance : tout passe par PowerShell/WMI (compteurs GPU « GPUPerformanceCounters »,
non sensibles à la langue de Windows, contrairement à Get-Counter).

Usage :
    uv run python scripts/check_charge_systeme.py
    uv run python scripts/check_charge_systeme.py --seuil-cpu 40 --duree 5

Codes retour : 0 = machine disponible (on peut lancer) • 1 = charge trop importante
(attendre un créneau) • 2 = erreur de mesure.
"""

import argparse
import statistics
import subprocess
import sys

# Script PowerShell unique : 3 échantillons espacés + 2 snapshots process (delta CPU)
# + capacité VRAM (registre, la classe AdapterRAM uint32 plafonne à 4 Gio).
_PS_SCRIPT = r"""
$ErrorActionPreference = 'Continue'
$num = 3
$intervalMs = __INTERVAL_MS__
for ($i = 0; $i -lt $num; $i++) {
  if ($i -gt 0) { Start-Sleep -Milliseconds $intervalMs }
  $cpu = $null; $ram = $null; $gpu = $null; $vramDed = $null
  try { $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Average -Property LoadPercentage).Average } catch {}
  try {
    $os = Get-CimInstance Win32_OperatingSystem
    if ($os.TotalVisibleMemorySize -gt 0) { $ram = 100.0 * (1.0 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize) }
  } catch {}
  try {
    $gpu = (Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine |
            Measure-Object -Sum -Property UtilizationPercentage).Sum
  } catch {}
  try {
    $adapters = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory
    $vramDed = ($adapters | Measure-Object -Sum -Property DedicatedUsage).Sum
  } catch {}
  "SAMPLE;$cpu;$ram;$gpu;$vramDed"
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


def _mesurer(duree_s: float) -> dict:
    """Exécute le script PowerShell et retourne les métriques parsées."""
    interval_ms = int(duree_s * 1000 / 3)
    ps = _PS_SCRIPT.replace("__INTERVAL_MS__", str(interval_ms))
    res = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, timeout=120,
    )
    if res.returncode != 0:
        raise RuntimeError(f"PowerShell a échoué (exit {res.returncode}) : {res.stderr.strip()[:300]}")

    met = {"samples": [], "vram_cap": 0, "nproc": 1, "proc1": {}, "proc2": {}, "interval_ms": interval_ms}
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
                    return None  # vide si le compteur a échoué sur cet échantillon

            met["samples"].append({k: _f(v) for k, v in zip(("cpu", "ram", "gpu", "vram"), morceaux[1:5])})
        elif ligne.startswith(("PROC1;", "PROC2;")):
            _, pid, nom, wss, t = ligne.split(";", 4)
            try:
                met["proc1" if ligne.startswith("PROC1;") else "proc2"][int(pid)] = (nom, int(wss), int(t))
            except ValueError:
                pass
        elif ligne.startswith("VRAMCAP;"):
            met["vram_cap"] = int(ligne.split(";", 1)[1] or 0)
        elif ligne.startswith("NPROC;"):
            met["nproc"] = max(1, int(ligne.split(";", 1)[1] or 1))
    if not met["samples"]:
        raise RuntimeError("Aucun échantillon exploitable reçu de PowerShell")
    return met


def _top_processus(met: dict) -> list[tuple[str, float, int]]:
    """Top process par % CPU (delta temps noyau+user entre les 2 snapshots)."""
    tops = []
    for pid, (nom, wss, t1) in met["proc1"].items():
        if nom == "System Idle Process":
            continue
        if pid in met["proc2"] and met["proc2"][pid][0] == nom:
            dt_s = (met["proc2"][pid][2] - t1) / 1e7  # 100 ns → s
            pct = 100.0 * dt_s / (met["interval_ms"] / 1000.0) / met["nproc"]
            tops.append((nom, pct, wss))
    tops.sort(key=lambda x: -x[1])
    return tops[:5]


def main() -> int:
    ap = argparse.ArgumentParser(description="Pré-vérification de charge avant génération")
    ap.add_argument("--seuil-cpu", type=float, default=60.0, help="seuil CPU %% (défaut 60)")
    ap.add_argument("--seuil-gpu", type=float, default=40.0, help="seuil GPU %% (défaut 40)")
    ap.add_argument("--seuil-ram", type=float, default=90.0, help="seuil RAM %% (défaut 90)")
    ap.add_argument("--seuil-vram", type=float, default=80.0, help="seuil VRAM %% (défaut 80)")
    ap.add_argument("--duree", type=float, default=3.0, help="durée d'échantillonnage en s (défaut 3)")
    args = ap.parse_args()

    try:
        met = _mesurer(args.duree)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"❌ Erreur de mesure : {exc}")
        return 2

    def _moy(cle: str, cap: float | None = None) -> float | None:
        vals = [s[cle] for s in met["samples"] if s[cle] is not None]
        if not vals:
            return None
        v = statistics.mean(vals)
        return min(v, cap) if cap is not None else v

    cpu, ram, gpu, vram_octets = _moy("cpu"), _moy("ram"), _moy("gpu", 100.0), _moy("vram")
    depassements = []

    def _verdict(nom: str, val: float | None, seuil: float, suffixe: str = "%"):
        if val is None:
            print(f"⚠️  {nom} : mesure indisponible (ignorée)")
            return
        etat = "OK" if val < seuil else "ÉLEVÉ"
        print(f"{'✅' if val < seuil else '⛔'} {nom} : {val:.1f}{suffixe} (seuil {seuil:g}{suffixe}) — {etat}")
        if val >= seuil:
            depassements.append(nom)

    print(f"🔍 Charge système ({len(met['samples'])} échantillons sur {args.duree:g} s) :")
    _verdict("CPU ", cpu, args.seuil_cpu)
    _verdict("RAM ", ram, args.seuil_ram)
    _verdict("GPU ", gpu, args.seuil_gpu)
    if vram_octets is not None:
        vram_gio = vram_octets / 2**30
        if met["vram_cap"] > 0:
            print(f"   VRAM dédiée : {vram_gio:.1f} / {met['vram_cap'] / 2**30:.0f} Gio")
            _verdict("VRAM", 100.0 * vram_octets / met["vram_cap"], args.seuil_vram)
        else:
            print(f"⚠️  VRAM : {vram_gio:.1f} Gio dédiés (capacité inconnue, seuil ignoré)")

    tops = _top_processus(met)
    if tops:
        detail = " | ".join(f"{n} {p:.0f}% ({w / 2**30:.1f} Gio)" for n, p, w in tops if p > 1)
        if detail:
            print(f"🔎 Top process CPU : {detail}")

    if depassements:
        print(f"\n⛔ VERDICT : machine occupée ({', '.join(depassements)}) — NE PAS lancer de génération maintenant.")
        return 1
    print("\n✅ VERDICT : machine disponible — lancement possible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
