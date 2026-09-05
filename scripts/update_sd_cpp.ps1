<#
.SYNOPSIS
    Script PowerShell d'automatisation de la mise à jour et de compilation Vulkan pour stable-diffusion.cpp.

.DESCRIPTION
    Ce script enveloppe et exécute scripts/update_sd_cpp.py avec détection de l'environnement Python
    (uv run, virtualenv local ou python global).
    Permet la vérification, le téléchargement rapide des binaires Vulkan GitHub ou la compilation native
    avec CMake et Visual Studio / Vulkan SDK.

.PARAMETER Check
    Vérifie l'état actuel et indique si une mise à jour est disponible.

.PARAMETER Download
    Télécharge et installe la dernière release officielle Vulkan pour Windows (x64).

.PARAMETER Build
    Clone/met à jour les sources et compile nativement avec Vulkan (CMake + MSVC).

.PARAMETER Rollback
    Restaure la sauvegarde précédente.

.PARAMETER Clean
    Nettoie le dossier build avant la compilation.

.EXAMPLE
    .\scripts\update_sd_cpp.ps1 -Check
    .\scripts\update_sd_cpp.ps1 -Download
    .\scripts\update_sd_cpp.ps1 -Build -Clean
#>

[CmdletBinding()]
param (
    [switch]$Check,
    [switch]$Download,
    [switch]$Build,
    [switch]$Rollback,
    [switch]$ListBackups,
    [switch]$Clean,
    [string]$InstallDir = "C:\SD",
    [string]$SourceDir = "C:\GIT\stable-diffusion.cpp",
    [string]$Branch = "master",
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " 🚀 STABLE-DIFFUSION.CPP - AUTOMATION DE MISE À JOUR & VULKAN" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# Détection de Python / uv
$PythonCmd = @()
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $PythonCmd = @("uv", "run", "python")
} elseif (Test-Path "$PSScriptRoot\..\.venv\Scripts\python.exe") {
    $PythonCmd = @("$PSScriptRoot\..\.venv\Scripts\python.exe")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = @("python")
} else {
    Write-Error "Python ou uv est introuvable. Veuillez installer Python ou uv."
    exit 1
}

$ScriptPath = Join-Path $PSScriptRoot "update_sd_cpp.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Le script Python $ScriptPath est introuvable."
    exit 1
}

# Construction des arguments
$ArgsList = @($ScriptPath)

if ($Check) {
    $ArgsList += "--check"
} elseif ($Download) {
    $ArgsList += "--download"
} elseif ($Build) {
    $ArgsList += "--build"
} elseif ($Rollback) {
    $ArgsList += "--rollback"
} elseif ($ListBackups) {
    $ArgsList += "--list-backups"
} else {
    # Mode par défaut : vérification
    $ArgsList += "--check"
}

if ($InstallDir) {
    $ArgsList += @("--install-dir", $InstallDir)
}
if ($SourceDir) {
    $ArgsList += @("--source-dir", $SourceDir)
}
if ($Branch) {
    $ArgsList += @("--branch", $Branch)
}
if ($Clean) {
    $ArgsList += "--clean"
}
if ($NoBackup) {
    $ArgsList += "--no-backup"
}

# Exécution
Write-Host "Lancement de : $($PythonCmd -join ' ') $($ArgsList -join ' ')...`n" -ForegroundColor DarkGray
& $PythonCmd[0] $PythonCmd[1..($PythonCmd.Length - 1)] $ArgsList
exit $LASTEXITCODE
