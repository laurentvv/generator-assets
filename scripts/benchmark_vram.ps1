# benchmark_vram.ps1
# Test de charge et profilage VRAM en conditions réelles sur AMD Radeon RX 6950 XT (16 Go)

$SD_CLI = "C:\SD\sd-cli.exe"
$DIFF_MODEL = "C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf"
$VAE = "C:\Modeles_LLM\wan_2.1_vae.safetensors"
$T5 = "C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"
$PROMPT = "A golden dragon soaring in clouds, cinematic lighting, 8k"
$TEST_OUT = "C:\GIT\generator-assets\output\vram_test.webm"

$TOTAL_VRAM_MO = 16384 # 16 Go

function Get-DedicatedVramMB {
    try {
        $val = (Get-Counter "\GPU Adapter Memory(*)\Dedicated Usage" -ErrorAction SilentlyContinue).CounterSamples | 
               Measure-Object -Property CookedValue -Maximum | 
               Select-Object -ExpandProperty Maximum
        return [math]::Round($val / 1MB, 1)
    } catch {
        return 0
    }
}

function Profile-Config {
    param(
        [int]$Width,
        [int]$Height,
        [int]$Frames,
        [string]$Label
    )

    Write-Host "`n=======================================================" -ForegroundColor Cyan
    Write-Host "🔍 TEST VRAM : $Label ($Width x $Height, $Frames trames)" -ForegroundColor Cyan
    Write-Host "======================================================="

    $vram_repos = Get-DedicatedVramMB
    Write-Host "   VRAM au repos avant lancement : $vram_repos Mo ($([math]::Round($vram_repos/1024, 2)) Go)"

    # Préparation de la commande
    $cmd = "$SD_CLI -M vid_gen --diffusion-model `"$DIFF_MODEL`" --vae `"$VAE`" --t5xxl `"$T5`" -p `"$PROMPT`" -W $Width -H $Height --video-frames $Frames --steps 1 --sampling-method euler --diffusion-fa --temporal-tiling --vae-tiling --backend `"diffusion=vulkan0,te=cpu`" -o `"$TEST_OUT`""

    # Lancement du processus
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $SD_CLI
    $psi.Arguments = "-M vid_gen --diffusion-model `"$DIFF_MODEL`" --vae `"$VAE`" --t5xxl `"$T5`" -p `"$PROMPT`" -W $Width -H $Height --video-frames $Frames --steps 1 --sampling-method euler --diffusion-fa --temporal-tiling --vae-tiling --backend `"diffusion=vulkan0,te=cpu`" -o `"$TEST_OUT`""
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::Start($psi)

    $peak_vram = $vram_repos

    # Boucle de mesure active pendant l'exécution
    while (-not $proc.HasExited) {
        $current = Get-DedicatedVramMB
        if ($current -gt $peak_vram) {
            $peak_vram = $current
        }
        Start-Sleep -Milliseconds 200
    }

    $exitCode = $proc.ExitCode
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()

    if (Test-Path $TEST_OUT) {
        Remove-Item $TEST_OUT -Force
    }

    $peak_go = [math]::Round($peak_vram / 1024, 2)
    $marge_go = [math]::Round(($TOTAL_VRAM_MO - $peak_vram) / 1024, 2)
    $pct = [math]::Round(($peak_vram / $TOTAL_VRAM_MO) * 100, 1)

    $statut = "🟢 SÛR"
    if ($peak_go -gt 13.5) {
        $statut = "🟡 ATTENTION (> 13.5 Go)"
    }
    if ($exitCode -ne 0 -or $peak_go -gt 15.0) {
        $statut = "🔴 RISQUE DE SATURATION"
    }

    Write-Host "   📊 Résultat : Peak VRAM = $peak_go Go ($pct%) | Marge Libre = $marge_go Go | Statut: $statut" -ForegroundColor $(if ($exitCode -eq 0 -and $peak_go -lt 13.5) { "Green" } else { "Yellow" })

    return [PSCustomObject]@{
        Configuration  = "$Width x $Height"
        Trames         = $Frames
        DureeVideo     = "$([math]::Round($Frames / 16, 1))s"
        PeakVRAM_Go    = $peak_go
        MargeLibre_Go  = $marge_go
        Pourcent_VRAM  = "$pct %"
        Statut         = $statut
        ExitCode       = $exitCode
    }
}

Write-Host "=================================================================" -ForegroundColor Magenta
Write-Host " 🚀 DÉMARRAGE DU BENCHMARK VRAM RÉEL (AMD Radeon RX 6950 XT 16 Go)" -ForegroundColor Magenta
Write-Host "================================================================="

$resultats = @()

# 1. 832x480 natif - 5 trames (Référence déjà validée)
$resultats += Profile-Config -Width 832 -Height 480 -Frames 5 -Label "832x480 Standard (5 trames)"

# 2. 832x480 natif - 9 trames
$resultats += Profile-Config -Width 832 -Height 480 -Frames 9 -Label "832x480 Modéré (9 trames)"

# 3. 832x480 natif - 17 trames
$resultats += Profile-Config -Width 832 -Height 480 -Frames 17 -Label "832x480 Étendu (17 trames)"

# 4. 640x360 léger - 17 trames
$resultats += Profile-Config -Width 640 -Height 360 -Frames 17 -Label "640x360 Éco (17 trames)"

# 5. 640x360 léger - 25 trames
$resultats += Profile-Config -Width 640 -Height 360 -Frames 25 -Label "640x360 Éco (25 trames)"

# 6. 640x360 léger - 33 trames
$resultats += Profile-Config -Width 640 -Height 360 -Frames 33 -Label "640x360 Éco (33 trames)"

Write-Host "`n"
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 📋 TABLEAU RÉCAPITULATIF DE TÉLÉMÉTRIE VRAM" -ForegroundColor Cyan
Write-Host "================================================================="

$resultats | Format-Table -AutoSize
