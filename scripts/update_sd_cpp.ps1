<#
.SYNOPSIS
    PowerShell script automating the Vulkan update and compilation of stable-diffusion.cpp.

.DESCRIPTION
    This script wraps and runs scripts/update_sd_cpp.py with Python environment detection
    (uv run, local virtualenv or global python).
    Allows checking, quickly downloading the GitHub Vulkan binaries or compiling natively
    with CMake and Visual Studio / Vulkan SDK.

.PARAMETER Check
    Checks the current state and reports whether an update is available.

.PARAMETER Download
    Downloads and installs the latest official Vulkan release for Windows (x64).

.PARAMETER Build
    Clones/updates the sources and compiles natively with Vulkan (CMake + MSVC).

.PARAMETER Rollback
    Restores the previous backup.

.PARAMETER Clean
    Cleans the build folder before compiling.

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
Write-Host " 🚀 STABLE-DIFFUSION.CPP - UPDATE & VULKAN AUTOMATION" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# Python / uv detection
$PythonCmd = @()
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $PythonCmd = @("uv", "run", "python")
} elseif (Test-Path "$PSScriptRoot\..\.venv\Scripts\python.exe") {
    $PythonCmd = @("$PSScriptRoot\..\.venv\Scripts\python.exe")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = @("python")
} else {
    Write-Error "Python or uv not found. Please install Python or uv."
    exit 1
}

$ScriptPath = Join-Path $PSScriptRoot "update_sd_cpp.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "The Python script $ScriptPath was not found."
    exit 1
}

# Building the arguments
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
    # Default mode: check
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

# Execution
Write-Host "Launching: $($PythonCmd -join ' ') $($ArgsList -join ' ')...`n" -ForegroundColor DarkGray
& $PythonCmd[0] $PythonCmd[1..($PythonCmd.Length - 1)] $ArgsList
exit $LASTEXITCODE
