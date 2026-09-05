# PowerShell script for downloading video models
param (
    [ValidateSet('1.3b', '14b', 'vae', 'all')]
    [string]$Model = '1.3b',
    [string]$TargetDir = 'C:\Modeles_LLM',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

$pack = switch ($Model) {
    '1.3b' { 'video-1.3b' }
    '14b'  { 'video-14b' }
    'vae'  { 'video-vae' }
    'all'  { 'video' }
}

Write-Host '=================================================================' -ForegroundColor Cyan
Write-Host ' Telechargement des Modeles Video Wan 2.1 pour Vulkan' -ForegroundColor Cyan
Write-Host (' Dossier cible : ' + $TargetDir) -ForegroundColor Yellow
Write-Host (' Pack selectionne : ' + $pack) -ForegroundColor Green
Write-Host '=================================================================' -ForegroundColor Cyan

$pyScript = Join-Path $PSScriptRoot 'download_models.py'

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $cmd = @('run', 'python', $pyScript, '--pack', $pack)
    if ($Force) { $cmd += '--force' }
    & uv @cmd
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $cmd = @($pyScript, '--pack', $pack)
    if ($Force) { $cmd += '--force' }
    & python @cmd
} else {
    Write-Error 'Python ou uv introuvable dans le PATH.'
}
