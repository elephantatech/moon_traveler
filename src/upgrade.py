"""In-place upgrade — check for new versions and download updates."""

import json
import logging
import os
import platform
import shutil
import stat
import sys
import tempfile
import urllib.request
from pathlib import Path

from src import ui

logger = logging.getLogger(__name__)

_REPO = "elephantatech/moon_traveler"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"


def get_current_version() -> str:
    """Read current version from pyproject.toml."""
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject.exists():
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("version", "unknown")
    except Exception as e:
        ui.warn(f"Could not read version: {e}")
    return "unknown"


def _detect_platform() -> str:
    """Return platform name matching release asset naming."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def check_for_update() -> dict | None:
    """Check GitHub for a newer release. Returns release info dict or None."""
    try:
        req = urllib.request.Request(_API_URL, headers={"User-Agent": "moon-traveler"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        ui.error(f"Could not check for updates: {e}")
        return None

    latest_tag = data.get("tag_name", "")
    latest_version = latest_tag.lstrip("v")
    current = get_current_version()

    if not latest_version or latest_version == current:
        return None

    # Simple version comparison (works for semver without pre-release)
    try:
        current_parts = [int(x) for x in current.split(".")]
        latest_parts = [int(x) for x in latest_version.split(".")]
        if latest_parts <= current_parts:
            return None
    except ValueError:
        # Can't parse versions — don't suggest upgrade on uncertainty
        return None

    return {
        "current": current,
        "latest": latest_version,
        "tag": latest_tag,
        "body": data.get("body", ""),
        "assets": data.get("assets", []),
        "html_url": data.get("html_url", ""),
    }


def _find_platform_asset(assets: list, plat: str) -> dict | None:
    """Find the download asset matching the current platform.

    Matches bare binaries (PyApp), .zip, and .tar.gz assets.
    Skips .sha256 checksum files.
    """
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith(".sha256"):
            continue
        if plat in name:
            return asset
    return None


def _find_checksum_asset(assets: list, binary_name: str) -> dict | None:
    """Find the .sha256 checksum asset for a given binary."""
    checksum_name = f"{binary_name}.sha256".lower()
    for asset in assets:
        if asset.get("name", "").lower() == checksum_name:
            return asset
    return None


def _fetch_checksum(url: str) -> str | None:
    """Download a .sha256 file and return the hex hash.

    Expected format: ``<hex_hash>  <filename>\\n``
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "moon-traveler"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode().strip()
        # Parse BSD/GNU checksum format: "hash  filename"
        parts = content.split()
        if parts and len(parts[0]) == 64:
            return parts[0]
        logger.warning("Unexpected checksum file format: %s", content[:80])
        return None
    except Exception as e:
        logger.warning("Could not download checksum: %s", e)
        return None


def _verify_checksum(file_path: Path, expected_hash: str) -> bool:
    """Verify SHA-256 hash of a file. Returns True if valid."""
    import hashlib

    ui.dim("  Verifying integrity (SHA-256)...")
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    actual = sha256.hexdigest()
    if actual != expected_hash:
        ui.error("Checksum verification failed!")
        ui.error(f"  Expected: {expected_hash[:16]}...")
        ui.error(f"  Got:      {actual[:16]}...")
        ui.error("  The downloaded file may be corrupted or tampered with.")
        return False
    ui.dim("  Checksum verified.")
    return True


def _is_editable_install() -> bool:
    """Check if running from a pip editable install (source checkout)."""
    if getattr(sys, "frozen", False):
        return False  # PyInstaller binary — never editable
    src_dir = Path(__file__).parent
    pyproject = src_dir.parent / "pyproject.toml"
    git_dir = src_dir.parent / ".git"
    return pyproject.exists() and git_dir.exists()


def _is_binary_install() -> bool:
    """Check if running from a PyApp binary."""
    exe = Path(sys.executable)
    name = exe.name.lower()
    return "moon-traveler" in name or "moon_traveler" in name


def _get_binary_path() -> Path:
    """Get the path to the currently running binary."""
    return Path(sys.executable).resolve()


def _replace_binary(new_binary: Path, target: Path) -> bool:
    """Replace the running binary with a new one.

    On Windows the running exe is locked, so we rename the old binary
    first (Windows allows renaming a locked file), then move the new
    one into place.
    """
    backup = target.with_suffix(target.suffix + ".old")

    try:
        # Remove any leftover backup from a previous upgrade
        if backup.exists():
            backup.unlink()

        # Rename current binary to .old (works even on locked Windows exe)
        target.rename(backup)
    except OSError as e:
        logger.warning("Could not rename current binary: %s", e)
        ui.error(f"Could not rename current binary: {e}")
        return False

    try:
        # Move new binary into place
        shutil.move(str(new_binary), str(target))
        # Ensure executable permission on Unix
        if sys.platform != "win32":
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as e:
        logger.error("Could not install new binary: %s", e)
        ui.error(f"Could not install new binary: {e}")
        # Try to restore backup
        try:
            backup.rename(target)
        except OSError:
            ui.error(f"CRITICAL: Could not restore backup. Recover manually from: {backup}")
        return False

    # Clean up backup
    try:
        backup.unlink()
    except OSError:
        # On Windows the old exe may still be locked — it will be cleaned up next run
        logger.debug("Could not remove backup %s (may be locked)", backup)

    return True


def run_upgrade():
    """Full upgrade flow: check, confirm, download, apply."""
    current = get_current_version()
    ui.info(f"Current version: v{current}")
    ui.dim("Checking for updates...")

    release = check_for_update()
    if release is None:
        ui.success("You're on the latest version.")
        return

    ui.console.print()
    ui.success(f"New version available: v{release['latest']} (you have v{release['current']})")

    # Show release notes (truncated)
    body = release.get("body", "").strip()
    if body:
        all_lines = body.split("\n")
        ui.console.print()
        ui.console.print("[bold]Release notes:[/bold]")
        for line in all_lines[:10]:
            ui.console.print(f"  [dim]{line}[/dim]")
        if len(all_lines) > 10:
            ui.dim("  ...")
    ui.console.print()

    # Editable install — just show instructions
    if _is_editable_install():
        ui.info("You're running from source. To upgrade:")
        ui.console.print("  [cyan]git pull origin main[/cyan]")
        ui.console.print("  [cyan]uv sync[/cyan]")
        ui.console.print()
        ui.dim(f"Or download the release: {release['html_url']}")
        return

    # Find platform asset
    plat = _detect_platform()
    asset = _find_platform_asset(release["assets"], plat)
    if asset is None:
        ui.warn(f"No release binary found for {plat}.")
        ui.dim(f"Download manually: {release['html_url']}")
        return

    asset_name = Path(asset["name"]).name
    if not asset_name or ".." in asset_name:
        ui.error("Invalid asset name in release metadata. Aborting.")
        return
    asset_url = asset["browser_download_url"]
    asset_size_mb = asset.get("size", 0) / 1024 / 1024

    # Validate download URL domain
    from urllib.parse import urlparse

    parsed = urlparse(asset_url)
    if parsed.scheme != "https" or not parsed.netloc.endswith(("github.com", "githubusercontent.com")):
        ui.error("Unexpected download URL. Aborting for safety.")
        return

    ui.console.print(f"  [cyan]Asset:[/cyan] {asset_name} ({asset_size_mb:.1f} MB)")
    ui.console.print()

    try:
        answer = ui.console.input("[bold]Download and install? (y/n) > [/bold]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer not in ("y", "yes"):
        ui.dim("Upgrade cancelled.")
        return

    # Download to temp file
    ui.info(f"Downloading {asset_name}...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="moon-upgrade-"))
    tmp_file = tmp_dir / asset_name

    try:
        try:
            urllib.request.urlretrieve(asset_url, str(tmp_file))
        except KeyboardInterrupt:
            ui.warn("Download cancelled.")
            return
        except Exception as e:
            ui.error(f"Download failed: {e}")
            return

        # Verify download size
        expected_size = asset.get("size", 0)
        actual_size = tmp_file.stat().st_size
        if expected_size and actual_size != expected_size:
            ui.error(f"Download incomplete: got {actual_size} bytes, expected {expected_size}.")
            ui.dim(f"Manual download: {release['html_url']}")
            return

        # Verify SHA-256 checksum
        checksum_asset = _find_checksum_asset(release["assets"], asset_name)
        if checksum_asset:
            expected_hash = _fetch_checksum(checksum_asset["browser_download_url"])
            if expected_hash:
                if not _verify_checksum(tmp_file, expected_hash):
                    ui.dim(f"Manual download: {release['html_url']}")
                    return
            else:
                ui.warn("Could not parse checksum file — skipping verification.")
        else:
            ui.warn("No checksum available for this release — skipping verification.")

        # Binary install — direct replacement
        if _is_binary_install():
            target = _get_binary_path()
            ui.dim(f"Replacing binary: {target}")
            if _replace_binary(tmp_file, target):
                ui.console.print()
                ui.success(f"Upgraded to v{release['latest']}!")
                ui.dim("Restart the game to use the new version.")
                ui.dim("Your saves in ~/.moonwalker/ are untouched.")
            return

        # Archive install (legacy — .zip or .tar.gz)
        extract_dir = tmp_dir / "extracted"
        if asset_name.endswith(".zip"):
            import zipfile

            with zipfile.ZipFile(tmp_file) as zf:
                safe_names = [
                    n for n in zf.namelist() if not os.path.isabs(n) and ".." not in os.path.normpath(n).split(os.sep)
                ]
                zf.extractall(extract_dir, members=safe_names)
        elif asset_name.endswith((".tar.gz", ".tgz")):
            import tarfile

            with tarfile.open(tmp_file) as tf:
                safe_members = []
                for member in tf.getmembers():
                    norm = os.path.normpath(member.name)
                    if os.path.isabs(norm) or ".." in norm.split(os.sep):
                        continue
                    safe_members.append(member)
                tf.extractall(extract_dir, members=safe_members)
        else:
            ui.error(f"Unknown archive format: {asset_name}")
            ui.dim(f"Manual download: {release['html_url']}")
            return

        contents = list(extract_dir.iterdir())
        if not contents:
            ui.error("Archive appears to be empty after extraction.")
            ui.dim(f"Manual download: {release['html_url']}")
            return
        source_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else extract_dir

        ui.success(f"Downloaded v{release['latest']}.")
        ui.console.print()
        ui.info("To complete the upgrade:")
        ui.console.print("  1. Close the game")
        ui.console.print(f"  2. Copy files from: [cyan]{source_dir}[/cyan]")
        game_dir = Path(sys.executable).parent
        ui.console.print(f"     to: [cyan]{game_dir}[/cyan]")
        ui.console.print("  3. Restart the game")
        ui.console.print()
        ui.dim("Your saves in ~/.moonwalker/ are safe — they're never touched by upgrades.")
        ui.dim(f"Clean up when done: delete {tmp_dir}")

    except Exception as e:
        ui.error(f"Upgrade failed: {e}")
        ui.dim(f"Manual download: {release['html_url']}")
    finally:
        # Clean up temp files (but not if we told the user to copy from there)
        if _is_binary_install():
            shutil.rmtree(tmp_dir, ignore_errors=True)
