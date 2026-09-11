<#
.SYNOPSIS
    Installateur tout-en-un de generator-assets : environnement uv + moteurs C++ Vulkan + FFmpeg + packs de modeles.

.DESCRIPTION
    Installe une machine Windows 10/11 neuve "from scratch" :
      1. Preflight : Windows, git, uv (auto-install via winget ou astral.sh), espace disque.
      2. uv sync (dependances Python du depot).
      3. Moteurs C++ Vulkan telecharges depuis les RELEASES OFFICIELLES upstream
         (versions epinglees connues-bonnes lues dans scripts/engines_manifest.json) :
         sd-cli, llama.cpp, audio.cpp, trellis.cpp + build FFmpeg standard BtbN.
         Idempotent : un moteur deja present est ignore sauf -Force.
         (Linux et macOS : voir scripts/install_unix.sh)
      4. Packs de modeles via scripts/download_models.py (defaut : base,onnx,upscalers).
      5. Verification finale : uv run python main.py --check.

    NOTE REDISTRIBUTION : le depot ne republie AUCUN binaire. Les moteurs proviennent
    des releases upstream ; le FFmpeg installe est un build STANDARD (BtbN) qui couvre
    100 % des recettes du depot. Le build FFmpeg custom de la station de dev
    (AMF RDNA2, libfdk-aac, --cpu=native) est machine-specifique et nonfree :
    il n'est ni publie ni installe par ce script.

.PARAMETER Prefix
    Dossier racine d'installation des moteurs (defaut "C:\" -> C:\SD, C:\llama.cpp,
    C:\audio-cpp, C:\trellis, C:\ffmpeg, chemins par defaut de core/config.py).
    Si different de "C:\", exporter les variables SD_CLI_PATH, LLAMA_CLI_PATH,
    AUDIOCPP_PATH, FFMPEG_PATH (cf. core/config.py).

.PARAMETER Engines
    Liste comma-separated de moteurs a installer (defaut : tous).

.PARAMETER Packs
    Packs de modeles download_models.py a telecharger (defaut "base,onnx,upscalers").

.PARAMETER SkipModels / SkipUvSync / SkipCheck
    Saute l'etape correspondante.

.PARAMETER Force
    Retelecharge et remplace meme si l'executable est deja present.

.PARAMETER DryRun
    Simule : resout les URLs (API GitHub) mais ne telecharge n'extrait ni n'installe rien.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
    powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -DryRun
    powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 -Engines "sd-cli,ffmpeg" -SkipModels
#>

[CmdletBinding()]
param (
    [string]$Prefix = "C:\",
    [string]$Engines = "sd-cli,llama.cpp,audio.cpp,trellis.cpp,ffmpeg",
    [string]$Packs = "base,onnx,upscalers",
    [switch]$SkipModels,
    [switch]$SkipUvSync,
    [switch]$SkipCheck,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $PSScriptRoot "engines_manifest.json"
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "generator-assets-install"

# ---------------------------------------------------------------- helpers

function Write-Etape { param($msg) Write-Host "`n==> $msg" -ForegroundColor Magenta }
function Write-Ok    { param($msg) Write-Host "  [ok] $msg" -ForegroundColor Green }
function Write-Info  { param($msg) Write-Host "  ..   $msg" -ForegroundColor Cyan }
function Write-Alerte{ param($msg) Write-Host "  [!]  $msg" -ForegroundColor Yellow }

function Invoke-Telechargement {
    param([string]$Url, [string]$Dest)
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -sSL --fail --retry 3 -o "$Dest" "$Url"
        if ($LASTEXITCODE -ne 0) { throw "curl a echoue (code $LASTEXITCODE) sur $Url" }
    } else {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    }
}

function Get-ReleasesGitHub {
    param([string]$Repo, [int]$ParPage = 8)
    $uri = "https://api.github.com/repos/$Repo/releases?per_page=$ParPage"
    return Invoke-RestMethod -Uri $uri -Headers @{ "User-Agent" = "generator-assets-installer/1.0" }
}

# Resout l'URL de l'asset d'un moteur a partir de sa fiche plateforme du manifeste.
function Resolve-UrlMoteur {
    param([string]$Repo, [psobject]$Spec)
    if ($Spec.url) {
        return @{ url = $Spec.url; label = Split-Path $Spec.url -Leaf }
    }
    if ($Spec.epingle -and $Spec.asset) {
        return @{
            url   = "https://github.com/$Repo/releases/download/$($Spec.epingle)/$($Spec.asset)"
            label = "$($Spec.asset) (epingle $($Spec.epingle))"
        }
    }
    if ($Spec.release -eq "latest") {
        Write-Info "Recherche de la derniere release $Repo..."
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
                                 -Headers @{ "User-Agent" = "generator-assets-installer/1.0" }
        foreach ($a in $rel.assets) {
            if ($a.name -like $Spec.asset_pattern) {
                return @{ url = $a.browser_download_url; label = "$($a.name) ($($rel.tag_name))" }
            }
        }
        throw "Aucun asset '$($Spec.asset_pattern)' dans la release $($rel.tag_name) de $Repo"
    }
    if ($Spec.scan_releases) {
        Write-Info "Scan des $($Spec.scan_releases) dernieres releases $Repo..."
        $rels = Get-ReleasesGitHub -Repo $Repo -ParPage $Spec.scan_releases
        foreach ($rel in $rels) {
            foreach ($a in $rel.assets) {
                if ($a.name -like $Spec.asset_pattern) {
                    return @{ url = $a.browser_download_url; label = "$($a.name) ($($rel.tag_name))" }
                }
            }
        }
        throw "Aucun asset '$($Spec.asset_pattern)' trouve dans les dernieres releases de $Repo"
    }
    throw "Fiche plateforme incomplete dans engines_manifest.json (ni url, ni epingle, ni release/scan_releases)"
}

# Installe un moteur : telecharge l'asset epingle/resolu, extrait, deplace l'exe
# (et ses DLL voisines) vers le dossier cible. Idempotent sauf -Force.
function Install-Moteur {
    param([string]$Nom, [psobject]$Moteur, [psobject]$Spec)
    Write-Etape "Moteur $Nom"
    $dir = [System.IO.Path]::GetFullPath((Join-Path $Prefix $Spec.sous_dossier))
    $exe = Join-Path $dir $Spec.exe

    if ((Test-Path $exe) -and -not $Force) {
        Write-Ok "$exe deja present -> ignore (-Force pour reinstaller)"
        return
    }

    $resolu = Resolve-UrlMoteur -Repo $Moteur.repo -Spec $Spec
    Write-Info "Asset : $($resolu.label)"
    if ($DryRun) { Write-Alerte "DRYRUN : telechargement/extraction simules vers $dir"; return }

    $zip = Join-Path $TempRoot "$Nom.zip"
    $extract = Join-Path $TempRoot $Nom
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    New-Item -ItemType Directory -Path $TempRoot, $extract -Force | Out-Null

    Write-Info "Telechargement $($resolu.url)"
    Invoke-Telechargement -Url $resolu.url -Dest $zip
    $tailleMo = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Ok "Telecharge ($tailleMo Mo)"

    Write-Info "Extraction..."
    Expand-Archive -Path $zip -DestinationPath $extract -Force

    $exeTrouve = Get-ChildItem $extract -Recurse -Filter $Spec.exe | Select-Object -First 1
    if (-not $exeTrouve) { throw "$($Spec.exe) introuvable dans l'archive de $Nom" }

    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Copy-Item (Join-Path $exeTrouve.FullName "..\*") $dir -Force
    if (-not (Test-Path $exe)) { throw "Echec de l'installation de $Nom ($exe absent)" }
    Write-Ok "Installe dans $dir"

    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------- preflight

Write-Host "`n========================================================" -ForegroundColor Magenta
Write-Host " generator-assets - INSTALLATION WINDOWS TOUT-EN-UN" -ForegroundColor Magenta
Write-Host "========================================================" -ForegroundColor Magenta
if ($DryRun) { Write-Alerte "Mode DRYRUN : aucun telechargement ni installation reelle." }

if ($env:OS -ne "Windows_NT") { throw "Windows requis (detecte : $($env:OS))." }
Write-Ok "Windows detecte"

if (-not (Test-Path $ManifestPath)) { throw "Manifeste introuvable : $ManifestPath" }
$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

# git
if (Get-Command git -ErrorAction SilentlyContinue) { Write-Ok "git detecte" }
else { Write-Alerte "git introuvable : installez https://git-scm.com/download/win puis relancez." }

# uv (auto-install si absent)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Alerte "uv introuvable -> installation automatique..."
    if ($DryRun) {
        Write-Info "DRYRUN : winget install astral-sh.uv (ou irm astral.sh/uv/install.ps1 | iex)"
    } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id astral-sh.uv --accept-source-agreements --accept-package-agreements
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    } else {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv non disponible apres installation : ouvrez un nouveau terminal et relancez."
    }
}
Write-Ok "uv detecte ($(uv --version))"

# espace disque
$drive = [System.IO.DriveInfo]::new(([System.IO.Path]::GetPathRoot(( [System.IO.Path]::GetFullPath($Prefix)))))
$libreGo = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
if ($libreGo -lt 20) { Write-Alerte "Seulement $libreGo Go libres sur $($drive.Name) (~20 Go conseilles moteurs + pack base)." }
else { Write-Ok "$libreGo Go libres sur $($drive.Name)" }

if ($Prefix -ne "C:\") {
    Write-Alerte "Prefix '$Prefix' different du defaut : exportez ensuite SD_CLI_PATH, LLAMA_CLI_PATH,"
    Write-Alerte "AUDIOCPP_PATH et FFMPEG_PATH vers les dossiers installes (cf. core/config.py)."
}

# ---------------------------------------------------------------- dependances python

if ($SkipUvSync) {
    Write-Etape "uv sync : ignore (-SkipUvSync)"
} elseif ($DryRun) {
    Write-Etape "uv sync : simule (DRYRUN)"
} else {
    Write-Etape "Synchronisation des dependances Python (uv sync)"
    Push-Location $RepoRoot
    try { uv sync } finally { Pop-Location }
    Write-Ok "Dependances synchronisees"
}

# ---------------------------------------------------------------- moteurs

$choisies = $Engines -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
foreach ($nom in $choisies) {
    $moteur = $Manifest.moteurs.$nom
    if (-not $moteur) { throw "Moteur '$nom' inconnu dans engines_manifest.json (disponibles : $($Manifest.moteurs.PSObject.Properties.Name -join ', '))" }
    $plat = $moteur.plateformes.windows
    if (-not $plat) { Write-Alerte "Moteur $nom : pas de binaire Windows publie en amont -> ignore"; continue }
    Install-Moteur -Nom $nom -Moteur $moteur -Spec $plat
}

if (Test-Path $TempRoot) { Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue }

# ---------------------------------------------------------------- modeles

if ($SkipModels) {
    Write-Etape "Modeles : ignore (-SkipModels)"
} else {
    foreach ($pack in ($Packs -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
        Write-Etape "Pack de modeles '$pack' (download_models.py)"
        if ($DryRun) { Write-Alerte "DRYRUN : uv run python scripts/download_models.py --pack $pack"; continue }
        Push-Location $RepoRoot
        try { uv run python scripts/download_models.py --pack $pack } finally { Pop-Location }
    }
}

# ---------------------------------------------------------------- verification

if ($SkipCheck) {
    Write-Etape "Verification finale : ignoree (-SkipCheck)"
} elseif ($DryRun) {
    Write-Etape "Verification finale : simulee (DRYRUN) -> uv run python main.py --check"
} else {
    Write-Etape "Verification finale (main.py --check)"
    Push-Location $RepoRoot
    try { uv run python main.py --check } finally { Pop-Location }
}

Write-Host "`n========================================================" -ForegroundColor Magenta
Write-Host " Installation terminee." -ForegroundColor Magenta
Write-Host " Demarrage :  uv run python main.py --interactive" -ForegroundColor Magenta
Write-Host " Autres packs de modeles : video, video-14b, all (cf. README, section Modeles)." -ForegroundColor Magenta
Write-Host "========================================================`n" -ForegroundColor Magenta
