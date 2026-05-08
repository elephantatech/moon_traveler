# Moon Traveler Terminal — Windows installer (PowerShell)
#
# Stable:  irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex
# Beta:    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1))) -Beta
# Alt:     $env:MOON_TRAVELER_BETA=1; irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex

param(
    [switch]$Beta
)

$ErrorActionPreference = "Stop"

$Repo = "elephantatech/moon_traveler"
$InstallDir = if ($env:MOON_TRAVELER_INSTALL_DIR) { $env:MOON_TRAVELER_INSTALL_DIR } else { "$env:LOCALAPPDATA\Programs\moon-traveler" }

# Support both -Beta parameter and environment variable
if ($env:MOON_TRAVELER_BETA -eq "1") { $Beta = $true }

Write-Host ""
Write-Host "Moon Traveler Terminal Installer" -ForegroundColor Cyan
Write-Host ""

# Get version (beta or stable)
if ($Beta) {
    Write-Host ""
    Write-Host "  BETA: This build may be unstable and is under active development." -ForegroundColor Yellow
    Write-Host "  Re-run without MOON_TRAVELER_BETA=1 to install the latest stable release." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Checking latest beta..." -ForegroundColor DarkGray
    $Releases = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases"
    $PreRelease = $Releases | Where-Object { $_.prerelease -eq $true } | Select-Object -First 1
    if (-not $PreRelease) {
        Write-Host "  No beta releases found. Install the stable version instead." -ForegroundColor Red
        exit 1
    }
    $Version = $PreRelease.tag_name
    Write-Host "  Latest beta: $Version" -ForegroundColor DarkGray
} else {
    Write-Host "  Checking latest version..." -ForegroundColor DarkGray
    $Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
    $Version = $Release.tag_name
    Write-Host "  Latest version: $Version" -ForegroundColor DarkGray
}

# Download single binary (PyApp)
$Filename = "moon-traveler-$Version-windows.exe"
$Url = "https://github.com/$Repo/releases/download/$Version/$Filename"
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "moon-traveler-install"

if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

$TmpFile = Join-Path $TmpDir $Filename
Write-Host "  Downloading $Filename..." -ForegroundColor DarkGray

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $Url -OutFile $TmpFile -UseBasicParsing
    $ProgressPreference = 'Continue'
} catch {
    Write-Host "  Download failed: $Url" -ForegroundColor Red
    Write-Host "  Check https://github.com/$Repo/releases for available downloads." -ForegroundColor Red
    exit 1
}

# Install binary
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
$Dest = Join-Path $InstallDir "moon-traveler.exe"
Copy-Item -Path $TmpFile -Destination $Dest -Force

# Clean up
Remove-Item $TmpDir -Recurse -Force

# Add to user PATH if not already there
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$InstallDir;$UserPath", "User")
    Write-Host ""
    Write-Host "  Added to PATH. Restart your terminal for it to take effect." -ForegroundColor Yellow
}

Write-Host ""
if ($Beta) {
    Write-Host "  Moon Traveler Terminal $Version (beta) installed!" -ForegroundColor Green
} else {
    Write-Host "  Moon Traveler Terminal $Version installed!" -ForegroundColor Green
}
Write-Host ""
Write-Host "  Location: $Dest" -ForegroundColor DarkGray
Write-Host "  Data:     $env:USERPROFILE\.moonwalker\" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  On first run, the binary will install dependencies" -ForegroundColor DarkGray
Write-Host "  (~15-30 seconds). After that, it launches instantly." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Run:  moon-traveler" -ForegroundColor White
Write-Host ""
