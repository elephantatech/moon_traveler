#!/usr/bin/env python3
"""Build Moon Traveler binaries using PyApp.

PyApp creates a small Rust binary that bootstraps Python + installs
the project via uv on first run. Native libraries (llama-cpp-python)
are installed via precompiled wheels, avoiding PyInstaller's linking issues.

Usage:
    python scripts/build_pyapp.py [--platform PLATFORM]

Requires:
    - Rust toolchain (cargo): https://rustup.rs
    - Internet access (downloads PyApp source)

Output:
    dist/moon-traveler-v{VERSION}-{PLATFORM}[.exe]
"""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
APP_NAME = "moon-traveler"

PYAPP_VERSION = "0.29.0"
PYAPP_SOURCE_URL = f"https://github.com/ofek/pyapp/releases/download/v{PYAPP_VERSION}/source.tar.gz"

with open(PROJECT_ROOT / "pyproject.toml", "rb") as _f:
    _pyproject = tomllib.load(_f)
    VERSION = _pyproject["project"]["version"]


def detect_platform() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    return "linux"


def check_cargo():
    """Ensure Rust toolchain is installed."""
    try:
        result = subprocess.run(["cargo", "--version"], capture_output=True, text=True, check=True)
        print(f"  Cargo: {result.stdout.strip()}")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("ERROR: Rust toolchain not found.")
        print("  Install: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
        print("  Windows: https://rustup.rs")
        sys.exit(1)


def download_pyapp_source(tmpdir: Path) -> Path:
    """Download and extract PyApp source."""
    archive = tmpdir / "pyapp-source.tar.gz"
    print(f"  Downloading PyApp v{PYAPP_VERSION}...")
    urllib.request.urlretrieve(PYAPP_SOURCE_URL, str(archive))

    print("  Extracting...")
    with tarfile.open(archive) as tf:
        tf.extractall(tmpdir, filter="data")

    # Find the extracted directory
    for item in tmpdir.iterdir():
        if item.is_dir() and item.name != "__MACOSX":
            return item

    raise RuntimeError("Could not find PyApp source directory after extraction")


def build_binary(target_platform: str):
    """Build the PyApp binary for the given platform."""
    print(f"\n{'=' * 60}")
    print(f"Building {APP_NAME} v{VERSION} for {target_platform} (PyApp)")
    print(f"{'=' * 60}\n")

    current = detect_platform()
    if target_platform != current:
        print("WARNING: Cross-compilation not supported.")
        print(f"  Current: {current}, Target: {target_platform}")
        print("  Build on the target platform instead.")
        return False

    check_cargo()

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # Build wheel first — embed it in the PyApp binary (no PyPI needed)
    print("  Building wheel...")
    wheel_dir = DIST_DIR / "wheel"
    if wheel_dir.exists():
        shutil.rmtree(wheel_dir)
    subprocess.check_call(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir)],
        cwd=str(PROJECT_ROOT),
    )
    wheels = list(wheel_dir.glob("*.whl"))
    if not wheels:
        print("ERROR: No wheel produced by build")
        return False
    wheel_path = wheels[0]
    print(f"  Wheel: {wheel_path.name}")

    with tempfile.TemporaryDirectory(prefix="pyapp-build-") as tmpdir:
        tmpdir = Path(tmpdir)
        pyapp_dir = download_pyapp_source(tmpdir)

        # Configure PyApp via environment variables
        env = os.environ.copy()
        env.update(
            {
                # Embed the wheel — no PyPI needed for game code at runtime
                "PYAPP_PROJECT_PATH": str(wheel_path.resolve()),
                # Entry point
                "PYAPP_EXEC_SPEC": "src.tui_app:run_tui",
                # Python version
                "PYAPP_PYTHON_VERSION": "3.13",
                # Embed Python in the binary — no Python download on first run
                "PYAPP_DISTRIBUTION_EMBED": "1",
                # Use uv for fast installs
                "PYAPP_UV_ENABLED": "1",
            }
        )

        print(f"  PyApp source: {pyapp_dir}")
        print(f"  Project: {APP_NAME} v{VERSION} (embedded wheel)")
        print("  Entry: src.tui_app:run_tui")
        print("  Python: 3.13 (embedded in binary)")
        print("  Installer: uv")
        print()
        print("  Building with cargo (this may take a minute)...")

        try:
            subprocess.check_call(
                ["cargo", "build", "--release"],
                cwd=str(pyapp_dir),
                env=env,
            )
        except subprocess.CalledProcessError as e:
            print(f"\nERROR: Build failed with exit code {e.returncode}")
            return False

        # Find the built binary
        ext = ".exe" if target_platform == "windows" else ""
        built = pyapp_dir / "target" / "release" / f"pyapp{ext}"
        if not built.exists():
            print(f"ERROR: Built binary not found at {built}")
            return False

        # Copy and rename to final location
        output_name = f"{APP_NAME}-v{VERSION}-{target_platform}{ext}"
        output_path = DIST_DIR / output_name
        shutil.copy2(built, output_path)

        # Make executable on Unix
        if target_platform != "windows":
            output_path.chmod(0o755)

        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"\n  Built: {output_path} ({size_mb:.1f} MB)")
        print("\n  First run will:")
        print("    1. Extract embedded Python 3.13 (no download)")
        print(f"    2. Install {APP_NAME} dependencies via pip")
        print("    3. Launch the game")
        print("  Subsequent runs launch instantly.")

    return True


def write_checksum(filepath: Path):
    """Write SHA-256 checksum file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    checksum_path = filepath.with_suffix(filepath.suffix + ".sha256")
    checksum_path.write_text(f"{sha256.hexdigest()}  {filepath.name}\n")
    print(f"  Checksum: {checksum_path}")


def main():
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} with PyApp")
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux", "all"],
        default=detect_platform(),
        help="Target platform (default: current)",
    )
    args = parser.parse_args()

    if args.platform == "all":
        targets = ["windows", "macos", "linux"]
    else:
        targets = [args.platform]

    results = {}
    for target in targets:
        success = build_binary(target)
        results[target] = success
        if success:
            ext = ".exe" if target == "windows" else ""
            output = DIST_DIR / f"{APP_NAME}-v{VERSION}-{target}{ext}"
            write_checksum(output)

    # Summary
    print(f"\n{'=' * 60}")
    print("Build Summary")
    print(f"{'=' * 60}")
    for target, success in results.items():
        status = "OK" if success else "SKIPPED" if target != detect_platform() else "FAILED"
        print(f"  {target:10s}  {status}")
    print()


if __name__ == "__main__":
    main()
