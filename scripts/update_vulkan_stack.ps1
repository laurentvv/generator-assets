<#
.SYNOPSIS
    Script PowerShell de gestion globale de la Suite IA Vulkan (stable-diffusion.cpp + llama.cpp).

.DESCRIPTION
    Supervise et met à jour en un seul clic l'intégralité de la suite IA accélérée sous Vulkan :
    - Détection matérielle GPU Vulkan (AMD Radeon / NVIDIA / Intel)
    - stable-diffusion.cpp (Diffusion, PBR, Vidéo)
    - llama.cpp (LLM Direction Artistique)

.PARAMETER Check
    Vérifie l'état de l'ensemble de la suite.

.PARAMETER Download
    Met à jour les deux moteurs via les dernières releases officielles GitHub.

.PARAMETER Build
    Recompile nativement les deux moteurs avec Vulkan (CMake + MSVC).

.PARAMETER Rollback
    Restaure les sauvegardes précédentes des deux moteurs.

.PARAMETER Clean
    Nettoie les dossiers build avant compilation.

.EXAMPLE
    .\scripts\update_vulkan_stack.ps1 -Check
    .\scripts\update_vulkan_stack.ps1 -Download
    .\scripts\update_vulkan_stack.ps1 -Build -Clean
#>

[CmdletBinding()]
param (
    [switch]$Check,
    [switch]$Download,
    [switch]$Build,
    [switch]$Rollback,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Détection de Python / uv
$PythonCmd = @()
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $PythonCmd = @("uv", "run", "python")
} elseif (Test-Path "$PSScriptRoot\..\.venv\Scripts\python.exe") {
    $PythonCmd = @("$PSScriptRoot\..\.venv\Scripts\python.exe")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = @("python")
} else {
    Write-Error "Python ou uv est introuvable."
    exit 1
}

$ScriptPath = Join-Path $PSScriptRoot "update_vulkan_stack.py"
$ArgsList = @($ScriptPath)

if ($Check) {
    $ArgsList += "--check"
} elseif ($Download) {
    $ArgsList += "--download"
} elseif ($Build) {
    $ArgsList += "--build"
} elseif ($Rollback) {
    $ArgsList += "--rollback"
} else {
    $ArgsList += "--check"
}

if ($Clean) {
    $ArgsList += "--clean"
}

& $PythonCmd[0] $PythonCmd[1..($PythonCmd.Length - 1)] $ArgsList
exit $LASTEXITCODE
