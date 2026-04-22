"""In-place upgrade — check for new versions and download updates."""

import json
import os
import platform
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from src import ui

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
    except Exception:
        pass
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
        pass

    return {
        "current": current,
        "latest": latest_version,
        "tag": latest_tag,
        "body": data.get("body", ""),
        "assets": data.get("assets", []),
        "html_url": data.get("html_url", ""),
    }


def _find_platform_asset(assets: list, plat: str) -> dict | None:
    """Find the download asset matching the current platform."""
    for asset in assets:
        name = asset.get("name", "").lower()
        if plat in name and (name.endswith(".zip") or name.endswith(".tar.gz")):
            return asset
    return None


def _is_editable_install() -> bool:
    """Check if running from a pip editable install (source checkout)."""
    if getattr(sys, "frozen", False):
        return False  # PyInstaller binary — never editable
    src_dir = Path(__file__).parent
    pyproject = src_dir.parent / "pyproject.toml"
    git_dir = src_dir.parent / ".git"
    return pyproject.exists() and git_dir.exists()


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
        lines = body.split("\n")[:10]
        ui.console.print()
        ui.console.print("[bold]Release notes:[/bold]")
        for line in lines:
            ui.console.print(f"  [dim]{line}[/dim]")
        if len(body.split("\n")) > 10:
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

    asset_name = asset["name"]
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
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="moon-upgrade-"))
        tmp_file = tmp_dir / asset_name
        urllib.request.urlretrieve(asset_url, str(tmp_file))
    except KeyboardInterrupt:
        ui.warn("Download cancelled.")
        return
    except Exception as e:
        ui.error(f"Download failed: {e}")
        return

    # Extract and replace
    try:
        game_dir = Path(sys.executable).parent
        if not game_dir.is_dir():
            game_dir = Path(__file__).parent.parent

        extract_dir = tmp_dir / "extracted"
        if asset_name.endswith(".zip"):
            with zipfile.ZipFile(tmp_file) as zf:
                # Safe extraction: filter out absolute paths and path traversal
                safe_names = [
                    n for n in zf.namelist() if not os.path.isabs(n) and ".." not in os.path.normpath(n).split(os.sep)
                ]
                zf.extractall(extract_dir, members=safe_names)
        else:
            import tarfile

            with tarfile.open(tmp_file) as tf:
                # Safe extraction: filter out absolute paths and path traversal
                safe_members = []
                for member in tf.getmembers():
                    norm = os.path.normpath(member.name)
                    if os.path.isabs(norm) or ".." in norm.split(os.sep):
                        continue
                    safe_members.append(member)
                tf.extractall(extract_dir, members=safe_members)

        # Find the extracted contents (may be in a subdirectory)
        contents = list(extract_dir.iterdir())
        source_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else extract_dir

        ui.success(f"Downloaded v{release['latest']}.")
        ui.console.print()
        ui.info("To complete the upgrade:")
        ui.console.print("  1. Close the game")
        ui.console.print(f"  2. Copy files from: [cyan]{source_dir}[/cyan]")
        ui.console.print(f"     to: [cyan]{game_dir}[/cyan]")
        ui.console.print("  3. Restart the game")
        ui.console.print()
        ui.dim("Your saves in ~/.moonwalker/ are safe — they're never touched by upgrades.")
        ui.dim(f"Clean up when done: delete {tmp_dir}")
    except Exception as e:
        ui.error(f"Extract failed: {e}")
        ui.dim(f"Manual download: {release['html_url']}")
    finally:
        # Clean up download (keep extracted for user to copy)
        try:
            tmp_file.unlink(missing_ok=True)
        except Exception:
            pass
