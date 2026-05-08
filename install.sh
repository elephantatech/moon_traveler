#!/usr/bin/env bash
# Moon Traveler Terminal — cross-platform installer
# Usage: curl -fsSL https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.sh | bash
# Beta:  curl -fsSL https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.sh | bash -s -- --beta
set -euo pipefail

REPO="elephantatech/moon_traveler"
INSTALL_DIR="${MOON_TRAVELER_INSTALL_DIR:-$HOME/.local/bin}"
BETA=false

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --beta) BETA=true ;;
  esac
done

# Colors
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
dim()    { printf '\033[0;90m%s\033[0m\n' "$*"; }

# Detect platform
detect_platform() {
  local os
  os="$(uname -s)"

  case "$os" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    MINGW*|MSYS*|CYGWIN*)
      red "On Windows, use the PowerShell installer instead:"
      red "  irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex"
      exit 1 ;;
    *)       red "Unsupported OS: $os"; exit 1 ;;
  esac

  dim "Detected: $os"
}

# Check for C/C++ compiler (required for llama-cpp-python)
check_compiler() {
  if [ "$PLATFORM" != "linux" ]; then
    return  # macOS has Xcode command line tools
  fi

  local has_cc=false
  local has_cmake=false

  # Check for C compiler
  if command -v gcc >/dev/null 2>&1; then
    has_cc=true
    dim "  C compiler: gcc $(gcc -dumpversion 2>/dev/null || echo '?')"
  elif command -v clang >/dev/null 2>&1; then
    has_cc=true
    dim "  C compiler: clang $(clang --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo '?')"
  fi

  # Check for cmake
  if command -v cmake >/dev/null 2>&1; then
    has_cmake=true
    dim "  CMake: $(cmake --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo '?')"
  fi

  if $has_cc && $has_cmake; then
    return
  fi

  echo
  yellow "  WARNING: C/C++ compiler or CMake not found."
  yellow "  The AI model (llama-cpp-python) requires compilation on first run."
  echo
  echo "  Install build tools for your distro:"
  echo

  # Detect distro and show appropriate command
  if command -v apt >/dev/null 2>&1; then
    echo "    sudo apt install build-essential cmake     # Ubuntu / Debian"
  elif command -v dnf >/dev/null 2>&1; then
    echo "    sudo dnf install gcc gcc-c++ cmake         # Fedora / RHEL"
  elif command -v pacman >/dev/null 2>&1; then
    echo "    sudo pacman -S base-devel cmake            # Arch Linux"
  elif command -v zypper >/dev/null 2>&1; then
    echo "    sudo zypper install gcc gcc-c++ cmake      # openSUSE"
  elif command -v apk >/dev/null 2>&1; then
    echo "    sudo apk add build-base cmake              # Alpine"
  else
    echo "    Install gcc, g++, and cmake using your package manager."
  fi

  echo
  echo "  Without these, the game will use pre-written dialogue"
  echo "  instead of AI-powered conversations."
  echo

  # Ask user if they want to continue
  printf "  Continue anyway? (y/n) "
  read -r answer </dev/tty 2>/dev/null || answer="y"
  if [ "$answer" != "y" ] && [ "$answer" != "Y" ] && [ "$answer" != "" ]; then
    echo
    dim "  Install the build tools above, then re-run this script."
    exit 0
  fi
}

# Get release tag from GitHub API
get_latest_version() {
  if $BETA; then
    yellow ""
    yellow "  BETA: This build may be unstable and is under active development."
    yellow "  Re-run without --beta to install the latest stable release."
    yellow ""
    VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases" \
      | grep -B2 '"prerelease": true' | grep '"tag_name"' | head -1 \
      | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')

    if [ -z "$VERSION" ]; then
      red "No beta releases found. Install the stable version instead:"
      red "  curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash"
      exit 1
    fi
    dim "Latest beta: $VERSION"
  else
    VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
      | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')

    if [ -z "$VERSION" ]; then
      red "Failed to detect latest version."
      exit 1
    fi
    dim "Latest version: $VERSION"
  fi
}

# Download and install
install() {
  local filename="moon-traveler-${VERSION}-${PLATFORM}"
  local url="https://github.com/$REPO/releases/download/$VERSION/$filename"
  local dest="$INSTALL_DIR/moon-traveler"

  dim "Downloading $filename..."
  mkdir -p "$INSTALL_DIR"
  TMP_DEST="${dest}.tmp.$$"
  trap 'rm -f "$TMP_DEST"' EXIT

  curl -fSL --progress-bar -o "$TMP_DEST" "$url" || {
    red "Download failed: $url"
    red "Check https://github.com/$REPO/releases for available downloads."
    exit 1
  }

  # Verify SHA-256 checksum
  local checksum_url="${url}.sha256"
  local expected_hash
  expected_hash=$(curl -fsSL "$checksum_url" 2>/dev/null | awk '{print $1}')
  if [ -n "$expected_hash" ]; then
    dim "Verifying integrity (SHA-256)..."
    local actual_hash
    if command -v sha256sum >/dev/null 2>&1; then
      actual_hash=$(sha256sum "$TMP_DEST" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
      actual_hash=$(shasum -a 256 "$TMP_DEST" | awk '{print $1}')
    else
      yellow "  No sha256sum or shasum found — skipping verification."
      actual_hash=""
    fi
    if [ -n "$actual_hash" ]; then
      if [ "$actual_hash" != "$expected_hash" ]; then
        red "Checksum verification failed!"
        red "  Expected: ${expected_hash:0:16}..."
        red "  Got:      ${actual_hash:0:16}..."
        red "  The downloaded file may be corrupted or tampered with."
        rm -f "$TMP_DEST"
        exit 1
      fi
      dim "  Checksum verified."
    fi
  else
    yellow "  No checksum available — skipping verification."
  fi

  mv "$TMP_DEST" "$dest"
  chmod +x "$dest"

  echo
  if $BETA; then
    green "Moon Traveler Terminal $VERSION (beta) installed!"
  else
    green "Moon Traveler Terminal $VERSION installed!"
  fi
  echo
  dim "  Binary: $dest"
  dim "  Data:   ~/.moonwalker/"
  echo
  dim "  On first run, the binary will install dependencies"
  dim "  (~15-30 seconds). After that, it launches instantly."
  echo

  # Check if install dir is in PATH
  if ! echo "$PATH" | tr ':' '\n' | grep -q "^$INSTALL_DIR$"; then
    echo "  Add to your PATH:"
    echo "    export PATH=\"$INSTALL_DIR:\$PATH\""
    echo
  fi

  echo "  Run:  moon-traveler"
  echo
}

detect_platform
check_compiler
get_latest_version
install
