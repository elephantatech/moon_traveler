$ErrorActionPreference = 'Stop'

$packageName = 'moon-traveler'
$url = 'https://github.com/elephantatech/moon_traveler/releases/download/v0.3.0/moon-traveler-windows.zip'
# $checksum = 'UPDATE_WITH_ACTUAL_SHA256_AFTER_RELEASE'

$installDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"

$packageArgs = @{
  packageName    = $packageName
  unzipLocation  = $installDir
  url            = $url
  # checksum       = $checksum
  checksumType   = 'sha256'
}

Install-ChocolateyZipPackage @packageArgs

# Add to PATH
$binDir = Join-Path $installDir 'moon-traveler'
Install-ChocolateyPath -PathToInstall $binDir -PathType 'User'

Write-Host "Moon Traveler CLI installed! Run 'moon-traveler' to play." -ForegroundColor Green
Write-Host "On first launch, the game offers to download an AI model (~1.3 GB)." -ForegroundColor Yellow
