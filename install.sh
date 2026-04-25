#!/usr/bin/env bash
# Moon Traveler Terminal — cross-platform installer
# Usage: curl -fsSL https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.sh | bash
set -euo pipefail

REPO="elephantatech/moon_traveler"
INSTALL_DIR="${MOON_TRAVELER_INSTALL_DIR:-$HOME/.local/bin}"

# Colors
red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[0;90m%s\033[0m\n' "$*"; }

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

# Get latest release tag from GitHub API
get_latest_version() {
  VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
    | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')

  if [ -z "$VERSION" ]; then
    red "Failed to detect latest version."
    exit 1
  fi
  dim "Latest version: $VERSION"
}

# Download and install
install() {
  local filename="moon-traveler-${VERSION}-${PLATFORM}"
  local url="https://github.com/$REPO/releases/download/$VERSION/$filename"

  dim "Downloading $filename..."
  TMPDIR_INSTALL="$(mktemp -d)"
  trap 'rm -rf "$TMPDIR_INSTALL"' EXIT

  curl -fSL --progress-bar -o "$TMPDIR_INSTALL/$filename" "$url" || {
    red "Download failed: $url"
    red "Check https://github.com/$REPO/releases for available downloads."
    exit 1
  }

  # Install binary
  mkdir -p "$INSTALL_DIR"
  local dest="$INSTALL_DIR/moon-traveler"
  cp "$TMPDIR_INSTALL/$filename" "$dest"
  chmod +x "$dest"

  echo
  green "Moon Traveler Terminal $VERSION installed!"
  echo
  dim "  Binary: $dest"
  dim "  Data:   ~/.moonwalker/"
  echo
  dim "  On first run, the binary will download Python and"
  dim "  install dependencies (~30-60 seconds). After that,"
  dim "  it launches instantly."
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
get_latest_version
install
