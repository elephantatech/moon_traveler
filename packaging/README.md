# Packaging & Distribution

This directory contains packaging configurations for distributing Moon Traveler Terminal via package managers and stores.

## GitHub Releases (Primary)

Releases are built automatically via GitHub Actions when a version tag is pushed:

```bash
git tag v0.3.0
git push origin v0.3.0
```

This triggers `.github/workflows/release.yml`, which builds standalone executables for Windows, macOS, and Linux using PyInstaller, then creates a GitHub Release with archives and SHA256 checksums.

## Homebrew (macOS/Linux)

**Formula:** `packaging/homebrew/moon-traveler.rb`

### To publish to a tap:
1. Create a tap repo: `elephantatech/homebrew-tap`
2. Copy the formula: `cp packaging/homebrew/moon-traveler.rb <tap-repo>/Formula/`
3. Update the `sha256` with the actual archive hash after release
4. Users install with:
   ```bash
   brew tap elephantatech/tap
   brew install moon-traveler
   ```

### To submit to Homebrew core:
1. Ensure the formula meets [Homebrew's criteria](https://docs.brew.sh/Acceptable-Formulae)
2. Open a PR to `Homebrew/homebrew-core`

## Chocolatey (Windows)

**Package:** `packaging/chocolatey/`

### To publish:
1. Create a Chocolatey account at https://community.chocolatey.org
2. Get an API key
3. Update the `sha256` checksum in `chocolateyinstall.ps1`
4. Pack and push:
   ```powershell
   cd packaging/chocolatey
   choco pack
   choco push moon-traveler.0.3.0.nupkg --api-key YOUR_KEY
   ```
5. Users install with:
   ```powershell
   choco install moon-traveler
   ```

## Steam

**Config:** `packaging/steam/`

See `packaging/steam/README.md` for full setup instructions. Requires:
1. Steamworks developer account ($100)
2. SteamCMD for upload
3. Store page assets (derived from existing SVG banner/screenshots)

## GitHub Pages

The game's website is at `docs/index.html`, deployed via `.github/workflows/pages.yml`. Push to `main` to update.

## Version Checklist

When releasing a new version:
1. Update `version` in `pyproject.toml`
2. Update `CHANGELOG.md` with new entry
3. Update `spec.md` version header
4. Update version badges in `docs/index.html`
5. Update URLs in packaging configs (Homebrew formula, Chocolatey install script)
6. Tag and push: `git tag v0.3.0 && git push origin v0.3.0`
