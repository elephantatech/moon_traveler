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
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"

  case "$os" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    MINGW*|MSYS*|CYGWIN*)
      red "On Windows, use the PowerShell installer instead:"
      red "  irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex"
      exit 1 ;;
    *)       red "Unsupported OS: $os"; exit 1 ;;
  esac

  dim "Detected: $os ($arch)"
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

# Download and extract
install() {
  local ext="tar.gz"
  [ "$PLATFORM" = "windows" ] && ext="zip"

  local filename="moon-traveler-${VERSION}-${PLATFORM}.${ext}"
  local url="https://github.com/$REPO/releases/download/$VERSION/$filename"

  dim "Downloading $filename..."
  TMPDIR_INSTALL="$(mktemp -d)"
  trap 'rm -rf "$TMPDIR_INSTALL"' EXIT
  local tmpdir="$TMPDIR_INSTALL"

  curl -fSL --progress-bar -o "$tmpdir/$filename" "$url" || {
    red "Download failed: $url"
    red "Check https://github.com/$REPO/releases for available downloads."
    exit 1
  }

  dim "Extracting..."
  if [ "$ext" = "zip" ]; then
    unzip -q "$tmpdir/$filename" -d "$tmpdir"
  else
    tar -xzf "$tmpdir/$filename" -C "$tmpdir"
  fi

  # Find the extracted binary
  local bin_name="moon-traveler"
  [ "$PLATFORM" = "windows" ] && bin_name="moon-traveler.exe"

  # Always copy to a permanent location (temp dir is cleaned up on exit)
  local app_dir="$HOME/.local/share/moon-traveler"
  rm -rf "$app_dir"
  mkdir -p "$app_dir"

  # Find the binary in the extracted archive
  local found_bin
  found_bin="$(find "$tmpdir" -name "$bin_name" -type f | head -1)"

  if [ -z "$found_bin" ]; then
    red "Could not find binary '$bin_name' in the downloaded archive."
    red "Please download manually from https://github.com/$REPO/releases"
    exit 1
  fi

  # Copy the directory containing the binary (includes _internal/ and other files)
  local content_dir
  content_dir="$(dirname "$found_bin")"
  cp -r "$content_dir"/* "$app_dir/"
  local extracted="$app_dir/$bin_name"

  # Symlink to install dir
  mkdir -p "$INSTALL_DIR"
  local link="$INSTALL_DIR/moon-traveler"
  [ "$PLATFORM" = "windows" ] && link="$INSTALL_DIR/moon-traveler.exe"

  if [ -f "$extracted" ]; then
    chmod +x "$extracted"
    ln -sf "$extracted" "$link"
  else
    red "Could not find binary '$bin_name' in the downloaded archive."
    red "Please download manually from https://github.com/$REPO/releases"
    exit 1
  fi

  echo
  green "Moon Traveler CLI $VERSION installed!"
  echo
  dim "  Binary: $extracted"
  dim "  Symlink: $link"
  dim "  Data:   ~/.moonwalker/"
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
