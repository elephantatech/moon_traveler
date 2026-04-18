# Moon Traveler Terminal — Windows installer (PowerShell)
# Usage: irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$Repo = "elephantatech/moon_traveler"
$InstallDir = if ($env:MOON_TRAVELER_INSTALL_DIR) { $env:MOON_TRAVELER_INSTALL_DIR } else { "$env:LOCALAPPDATA\Programs\moon-traveler" }

Write-Host ""
Write-Host "Moon Traveler CLI Installer" -ForegroundColor Cyan
Write-Host ""

# Get latest version
Write-Host "  Checking latest version..." -ForegroundColor DarkGray
$Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
$Version = $Release.tag_name
Write-Host "  Latest version: $Version" -ForegroundColor DarkGray

# Download
$Filename = "moon-traveler-$Version-windows.zip"
$Url = "https://github.com/$Repo/releases/download/$Version/$Filename"
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "moon-traveler-install"

if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

$ZipPath = Join-Path $TmpDir $Filename
Write-Host "  Downloading $Filename..." -ForegroundColor DarkGray

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing
    $ProgressPreference = 'Continue'
} catch {
    Write-Host "  Download failed: $Url" -ForegroundColor Red
    Write-Host "  Check https://github.com/$Repo/releases for available downloads." -ForegroundColor Red
    exit 1
}

# Extract
Write-Host "  Extracting..." -ForegroundColor DarkGray
Expand-Archive -Path $ZipPath -DestinationPath $TmpDir -Force

# Find and copy the app directory
$AppContent = Get-ChildItem -Path $TmpDir -Directory -Recurse | Where-Object {
    Test-Path (Join-Path $_.FullName "moon-traveler.exe")
} | Select-Object -First 1

if (-not $AppContent) {
    Write-Host "  Could not find moon-traveler.exe in archive." -ForegroundColor Red
    exit 1
}

# Install
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
Copy-Item -Path $AppContent.FullName -Destination $InstallDir -Recurse -Force

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
Write-Host "  Moon Traveler CLI $Version installed!" -ForegroundColor Green
Write-Host ""
Write-Host "  Location: $InstallDir" -ForegroundColor DarkGray
Write-Host "  Data:     $env:USERPROFILE\.moonwalker\" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Run:  moon-traveler" -ForegroundColor White
Write-Host ""
