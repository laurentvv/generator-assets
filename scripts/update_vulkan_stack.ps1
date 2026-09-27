<#
.SYNOPSIS
    PowerShell script managing the whole Vulkan AI Suite (stable-diffusion.cpp + llama.cpp).

.DESCRIPTION
    Supervises and updates in one click the whole Vulkan-accelerated AI suite:
    - Vulkan GPU hardware detection (AMD Radeon / NVIDIA / Intel)
    - stable-diffusion.cpp (Diffusion, PBR, Video)
    - llama.cpp (Art Direction LLM)

.PARAMETER Check
    Checks the state of the whole suite.

.PARAMETER Download
    Updates both engines via the latest official GitHub releases.

.PARAMETER Build
    Compiles both engines natively with Vulkan (CMake + MSVC).

.PARAMETER Rollback
    Restores the previous backups of both engines.

.PARAMETER Clean
    Cleans the build folders before compiling.

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

# Python / uv detection
$PythonCmd = @()
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $PythonCmd = @("uv", "run", "python")
} elseif (Test-Path "$PSScriptRoot\..\.venv\Scripts\python.exe") {
    $PythonCmd = @("$PSScriptRoot\..\.venv\Scripts\python.exe")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = @("python")
} else {
    Write-Error "Python or uv not found."
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
