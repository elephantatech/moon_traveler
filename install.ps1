# Moon Traveler Terminal — Windows installer (PowerShell)
# Usage: irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$Repo = "elephantatech/moon_traveler"
$InstallDir = if ($env:MOON_TRAVELER_INSTALL_DIR) { $env:MOON_TRAVELER_INSTALL_DIR } else { "$env:LOCALAPPDATA\Programs\moon-traveler" }

Write-Host ""
Write-Host "Moon Traveler Terminal Installer" -ForegroundColor Cyan
Write-Host ""

# Get latest version
Write-Host "  Checking latest version..." -ForegroundColor DarkGray
$Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
$Version = $Release.tag_name
Write-Host "  Latest version: $Version" -ForegroundColor DarkGray

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
Write-Host "  Moon Traveler Terminal $Version installed!" -ForegroundColor Green
Write-Host ""
Write-Host "  Location: $Dest" -ForegroundColor DarkGray
Write-Host "  Data:     $env:USERPROFILE\.moonwalker\" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  On first run, the binary will download Python and" -ForegroundColor DarkGray
Write-Host "  install dependencies (~30-60 seconds). After that," -ForegroundColor DarkGray
Write-Host "  it launches instantly." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Run:  moon-traveler" -ForegroundColor White
Write-Host ""
