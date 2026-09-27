<#
.SYNOPSIS
    PowerShell script automating the Vulkan update and compilation of llama.cpp.

.DESCRIPTION
    This script wraps and runs scripts/update_llama_cpp.py with Python environment detection
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
    .\scripts\update_llama_cpp.ps1 -Check
    .\scripts\update_llama_cpp.ps1 -Download
    .\scripts\update_llama_cpp.ps1 -Build -Clean
#>

[CmdletBinding()]
param (
    [switch]$Check,
    [switch]$Download,
    [switch]$Build,
    [switch]$Rollback,
    [switch]$ListBackups,
    [switch]$Clean,
    [string]$InstallDir = "C:\llama.cpp",
    [string]$SourceDir = "C:\GIT\llama.cpp",
    [string]$Branch = "master",
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "`n========================================================" -ForegroundColor Magenta
Write-Host " 🦙 LLAMA.CPP - UPDATE & VULKAN AUTOMATION" -ForegroundColor Magenta
Write-Host "========================================================`n" -ForegroundColor Magenta

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

$ScriptPath = Join-Path $PSScriptRoot "update_llama_cpp.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "The Python script $ScriptPath was not found."
    exit 1
}

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

Write-Host "Launching: $($PythonCmd -join ' ') $($ArgsList -join ' ')...`n" -ForegroundColor DarkGray
& $PythonCmd[0] $PythonCmd[1..($PythonCmd.Length - 1)] $ArgsList
exit $LASTEXITCODE
