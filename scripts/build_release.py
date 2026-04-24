#!/usr/bin/env python3
"""Build release executables for Windows, macOS, and Linux.

Usage:
    python scripts/build_release.py [--platform PLATFORM]

Options:
    --platform  Target platform: windows, macos, linux, or all (default: current)

Requires:
    pip install pyinstaller

This script builds a standalone executable that bundles the game code.
The GGUF model file is NOT included in the build (too large) — users must
place it in the models/ directory next to the executable.

Output:
    dist/
      moon-traveler-<platform>/
        moon-traveler[.exe]
        models/               (empty, user places .gguf here)
        saves/                (empty, created at runtime)
"""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
APP_NAME = "moon-traveler"
ENTRY_POINT = PROJECT_ROOT / "play_tui.py"

with open(PROJECT_ROOT / "pyproject.toml", "rb") as _f:
    VERSION = tomllib.load(_f)["project"]["version"]


def detect_platform() -> str:
    """Detect current platform."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    else:
        print(f"Warning: Unknown platform '{system}', treating as linux")
        return "linux"


def check_pyinstaller():
    """Ensure PyInstaller is installed."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_executable(target_platform: str):
    """Build the executable for the given platform."""
    print(f"\n{'=' * 60}")
    print(f"Building {APP_NAME} v{VERSION} for {target_platform}")
    print(f"{'=' * 60}\n")

    current = detect_platform()
    if target_platform != current:
        print("WARNING: Cross-compilation is not supported by PyInstaller.")
        print(f"  Current platform: {current}")
        print(f"  Target platform:  {target_platform}")
        print("  You must build on the target platform itself.")
        print(f"  Skipping {target_platform} build.\n")
        return False

    output_name = f"{APP_NAME}-{target_platform}"
    output_dir = DIST_DIR / output_name

    # Clean previous build
    if output_dir.exists():
        shutil.rmtree(output_dir)

    # Build PyInstaller command
    exe_name = APP_NAME
    if target_platform == "windows":
        exe_name += ".exe"

    hooks_dir = PROJECT_ROOT / "scripts" / "pyinstaller_hooks"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--onedir",
        "--console",
        # Include source packages
        "--add-data",
        f"{PROJECT_ROOT / 'src'}{os.pathsep}src",
        # Hidden imports that PyInstaller might miss
        "--hidden-import",
        "rich",
        "--hidden-import",
        "textual",
        "--hidden-import",
        "psutil",
        "--hidden-import",
        "llama_cpp",
        "--hidden-import",
        "jinja2",
        "--hidden-import",
        "markupsafe",
        # Collect entire packages (includes native .dll/.so/.dylib in lib/ dirs)
        "--collect-all",
        "llama_cpp",
        "--collect-all",
        "textual",
        # Custom hooks for llama_cpp native library resolution
        "--additional-hooks-dir",
        str(hooks_dir),
        "--runtime-hook",
        str(hooks_dir / "rthook_llama.py"),
        "--add-data",
        f"{PROJECT_ROOT / 'play_tui.py'}{os.pathsep}.",
        # Output directories
        "--distpath",
        str(DIST_DIR / output_name),
        "--workpath",
        str(BUILD_DIR / output_name),
        "--specpath",
        str(BUILD_DIR),
        # Entry point
        str(ENTRY_POINT),
    ]

    print(f"Running: {' '.join(cmd[:6])}...\n")

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Build failed with exit code {e.returncode}")
        return False

    # Create empty directories for user content
    exe_root = output_dir / APP_NAME
    if not exe_root.exists():
        # PyInstaller may put files directly in output_dir
        exe_root = output_dir

    models_dir = exe_root / "models"
    saves_dir = exe_root / "saves"
    models_dir.mkdir(parents=True, exist_ok=True)
    saves_dir.mkdir(parents=True, exist_ok=True)

    # Create a README for the models directory
    (models_dir / "PLACE_MODEL_HERE.txt").write_text(
        "Place your GGUF model file here, or let the game download one on first run.\n\n"
        "Recommended: Qwen3.5-2B-Q4_K_M.gguf (~1.3 GB, lower RAM usage)\n"
        "Full quality: gemma-4-E2B-it-Q4_K_M.gguf (~3.1 GB)\n\n"
        "Any .gguf file will work. The game falls back to\n"
        "pre-written dialogue if no model is found.\n"
    )

    print("\nBuild successful!")
    print(f"  Output: {output_dir}")
    print(f"  Executable: {exe_root / exe_name}")
    print("\nTo distribute:")
    print(f"  1. Place a .gguf model in {models_dir}")
    print(f"  2. Zip the entire {output_name}/ directory")
    print(f"  3. Users unzip and run {exe_name}")
    return True


def _write_checksum(filepath: Path):
    """Write a SHA-256 checksum file alongside the archive."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    checksum_path = filepath.with_suffix(filepath.suffix + ".sha256")
    checksum_path.write_text(f"{sha256.hexdigest()}  {filepath.name}\n")
    print(f"  Checksum: {checksum_path}")


def create_release_archive(target_platform: str):
    """Create a zip/tar.gz archive of the built release."""
    output_name = f"{APP_NAME}-{target_platform}"
    output_dir = DIST_DIR / output_name

    if not output_dir.exists():
        return

    archive_name = f"{APP_NAME}-v{VERSION}-{target_platform}"
    archive_path = DIST_DIR / archive_name

    if target_platform == "windows":
        shutil.make_archive(str(archive_path), "zip", str(DIST_DIR), output_name)
        final = Path(f"{archive_path}.zip")
        print(f"  Archive: {final}")
        _write_checksum(final)
    else:
        shutil.make_archive(str(archive_path), "gztar", str(DIST_DIR), output_name)
        final = Path(f"{archive_path}.tar.gz")
        print(f"  Archive: {final}")
        _write_checksum(final)


def main():
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} release")
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux", "all"],
        default=detect_platform(),
        help="Target platform (default: current)",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Skip creating release archives",
    )
    args = parser.parse_args()

    check_pyinstaller()

    if args.platform == "all":
        targets = ["windows", "macos", "linux"]
    else:
        targets = [args.platform]

    results = {}
    for target in targets:
        success = build_executable(target)
        results[target] = success
        if success and not args.no_archive:
            create_release_archive(target)

    # Summary
    print(f"\n{'=' * 60}")
    print("Build Summary")
    print(f"{'=' * 60}")
    for target, success in results.items():
        status = "OK" if success else "SKIPPED (wrong platform)" if target != detect_platform() else "FAILED"
        print(f"  {target:10s}  {status}")
    print()


if __name__ == "__main__":
    main()
