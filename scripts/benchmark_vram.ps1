# benchmark_vram.ps1
# Load test and VRAM profiling in real conditions on AMD Radeon RX 6950 XT (16 GB)

$SD_CLI = "C:\SD\sd-cli.exe"
$DIFF_MODEL = "C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf"
$VAE = "C:\Modeles_LLM\wan_2.1_vae.safetensors"
$T5 = "C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"
$PROMPT = "A golden dragon soaring in clouds, cinematic lighting, 8k"
$TEST_OUT = "C:\GIT\generator-assets\output\vram_test.webm"

$TOTAL_VRAM_MO = 16384 # 16 GB

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
    Write-Host "🔍 VRAM TEST: $Label ($Width x $Height, $Frames frames)" -ForegroundColor Cyan
    Write-Host "======================================================="

    $vram_repos = Get-DedicatedVramMB
    Write-Host "   VRAM at rest before launch: $vram_repos MB ($([math]::Round($vram_repos/1024, 2)) GB)"

    # Building the command
    $cmd = "$SD_CLI -M vid_gen --diffusion-model `"$DIFF_MODEL`" --vae `"$VAE`" --t5xxl `"$T5`" -p `"$PROMPT`" -W $Width -H $Height --video-frames $Frames --steps 1 --sampling-method euler --diffusion-fa --temporal-tiling --vae-tiling --backend `"diffusion=vulkan0,te=cpu`" -o `"$TEST_OUT`""

    # Launching the process
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $SD_CLI
    $psi.Arguments = "-M vid_gen --diffusion-model `"$DIFF_MODEL`" --vae `"$VAE`" --t5xxl `"$T5`" -p `"$PROMPT`" -W $Width -H $Height --video-frames $Frames --steps 1 --sampling-method euler --diffusion-fa --temporal-tiling --vae-tiling --backend `"diffusion=vulkan0,te=cpu`" -o `"$TEST_OUT`""
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::Start($psi)

    $peak_vram = $vram_repos

    # Active measurement loop while running
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

    $statut = "🟢 SAFE"
    if ($peak_go -gt 13.5) {
        $statut = "🟡 CAUTION (> 13.5 GB)"
    }
    if ($exitCode -ne 0 -or $peak_go -gt 15.0) {
        $statut = "🔴 SATURATION RISK"
    }

    Write-Host "   📊 Result: Peak VRAM = $peak_go GB ($pct%) | Free Headroom = $marge_go GB | Status: $statut" -ForegroundColor $(if ($exitCode -eq 0 -and $peak_go -lt 13.5) { "Green" } else { "Yellow" })

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
Write-Host " 🚀 STARTING THE REAL VRAM BENCHMARK (AMD Radeon RX 6950 XT 16 GB)" -ForegroundColor Magenta
Write-Host "================================================================="

$resultats = @()

# 1. 832x480 native - 5 frames (Already-validated reference)
$resultats += Profile-Config -Width 832 -Height 480 -Frames 5 -Label "832x480 Standard (5 frames)"

# 2. 832x480 native - 9 frames
$resultats += Profile-Config -Width 832 -Height 480 -Frames 9 -Label "832x480 Moderate (9 frames)"

# 3. 832x480 native - 17 frames
$resultats += Profile-Config -Width 832 -Height 480 -Frames 17 -Label "832x480 Extended (17 frames)"

# 4. 640x360 light - 17 frames
$resultats += Profile-Config -Width 640 -Height 360 -Frames 17 -Label "640x360 Eco (17 frames)"

# 5. 640x360 light - 25 frames
$resultats += Profile-Config -Width 640 -Height 360 -Frames 25 -Label "640x360 Eco (25 frames)"

# 6. 640x360 light - 33 frames
$resultats += Profile-Config -Width 640 -Height 360 -Frames 33 -Label "640x360 Eco (33 frames)"

Write-Host "`n"
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 📋 VRAM TELEMETRY SUMMARY TABLE" -ForegroundColor Cyan
Write-Host "================================================================="

$resultats | Format-Table -AutoSize
