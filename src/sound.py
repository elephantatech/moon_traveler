"""Cross-platform system sound effects using built-in OS sounds.

No external dependencies. Uses:
- macOS:   terminal bell (default) + 'say' command (when voice module installed)
- Windows: winsound module (built-in) + Windows Media .wav files
- Linux:   paplay/aplay with freedesktop sounds, or terminal bell fallback

Sound mode:
- Default: short beep patterns (terminal bell) for all events
- Voice module upgrade: unlocks spoken word announcements via 'say' (macOS)
  or platform equivalent

All sounds play asynchronously (non-blocking) so they never slow the game.
Sound can be disabled globally via disable().
"""

import os
import platform
import subprocess
import threading
import time

_enabled = True
_voice_enabled = False
_system = platform.system()
_lock = threading.Lock()


def enable():
    global _enabled
    _enabled = True


def disable():
    global _enabled
    _enabled = False


def is_enabled() -> bool:
    return _enabled


def set_voice(enabled: bool):
    """Enable/disable voice announcements (requires drone voice_module upgrade)."""
    global _voice_enabled
    _voice_enabled = enabled


def is_voice_enabled() -> bool:
    return _voice_enabled


def _play_async(func, *args):
    """Play sound in a background thread. Skips if another sound is already playing."""
    if not _enabled:
        return
    if not _lock.acquire(blocking=False):
        return  # Another sound is playing — skip

    def _run():
        try:
            func(*args)
        finally:
            _lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Beep patterns — terminal bell with timing for distinct sounds
# ---------------------------------------------------------------------------

# Each pattern is a list of (delay_before_beep,) tuples
# Single beep = notification, double = success, triple = warning, etc.
_BEEP_PATTERNS = {
    "error": [0, 0.08, 0.08],  # 3 rapid beeps
    "warning": [0, 0.12],  # 2 beeps
    "success": [0, 0.15],  # 2 spaced beeps
    "info": [0],  # 1 beep
    "discovery": [0, 0.1, 0.1],  # 3 quick beeps
    "damage": [0, 0.06, 0.06, 0.06],  # 4 rapid beeps (alarm)
    "trust": [0],  # 1 beep
    "chat_open": [0, 0.2],  # 2 slow beeps
    "chat_close": [0],  # 1 beep
    "pickup": [0],  # 1 beep
    "repair": [0, 0.15, 0.15],  # 3 spaced beeps
    "victory": [0, 0.1, 0.1, 0.2, 0.1, 0.1],  # fanfare pattern
    "game_over": [0, 0.3, 0.3],  # 3 slow beeps
    "aria_warning": [0, 0.1, 0.1],  # 3 beeps
    "boot": [0, 0.2, 0.2],  # 3 spaced beeps
    "scan": [0, 0.12],  # 2 beeps
    "trade": [0, 0.15],  # 2 beeps
    "escort": [0, 0.1, 0.1, 0.1],  # 4 quick beeps
    "upgrade": [0, 0.1, 0.2],  # 3 ascending feel
    "hazard_geyser": [0, 0.06, 0.06, 0.06],  # 4 rapid
    "hazard_ice": [0, 0.06, 0.06, 0.06],  # 4 rapid
    "hazard_storm": [0, 0.08, 0.08],  # 3 rapid
}


def _play_beep_pattern(event):
    """Play a terminal bell pattern via fd 2 directly.

    Uses os.write(2, ...) instead of sys.stderr.write() to bypass
    Textual's stderr capture in TUI mode.
    """
    pattern = _BEEP_PATTERNS.get(event, [0])
    for delay in pattern:
        if delay > 0:
            time.sleep(delay)
        try:
            os.write(2, b"\a")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# macOS voice — 'say' command (only when voice module is installed)
# ---------------------------------------------------------------------------

_MACOS_VOICE_MAP = {
    "error": ("error", "Samantha", 250),
    "warning": ("warning", "Samantha", 230),
    "success": ("done", "Samantha", 280),
    "info": ("note", "Samantha", 280),
    "discovery": ("found", "Samantha", 250),
    "damage": ("damage", "Samantha", 220),
    "trust": ("trust gained", "Samantha", 280),
    "chat_open": ("connected", "Samantha", 250),
    "chat_close": ("disconnected", "Samantha", 250),
    "pickup": ("collected", "Samantha", 280),
    "repair": ("installed", "Samantha", 230),
    "victory": ("mission complete", "Samantha", 180),
    "game_over": ("game over", "Samantha", 160),
    "aria_warning": ("caution", "Samantha", 220),
    "boot": ("systems online", "Samantha", 220),
    "scan": ("scanning", "Samantha", 250),
    "trade": ("trade complete", "Samantha", 250),
    "escort": ("companion joined", "Samantha", 230),
    "upgrade": ("upgrade installed", "Samantha", 250),
    "hazard_geyser": ("geyser", "Samantha", 220),
    "hazard_ice": ("ice breach", "Samantha", 220),
    "hazard_storm": ("storm incoming", "Samantha", 200),
}


def _play_macos(event):
    """Play sound on macOS: voice if enabled, otherwise beep pattern."""
    if _voice_enabled:
        mapping = _MACOS_VOICE_MAP.get(event)
        if mapping:
            word, voice, rate = mapping
            try:
                subprocess.run(
                    ["say", "-v", voice, "-r", str(rate), word],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                return
            except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                pass
    # Default: beep pattern
    _play_beep_pattern(event)


# ---------------------------------------------------------------------------
# Windows: winsound module
# ---------------------------------------------------------------------------

_WINDOWS_MEDIA = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Media")

_WINDOWS_WAV_MAP = {
    "error": "Windows Critical Stop.wav",
    "warning": "Windows Exclamation.wav",
    "success": "Windows Print complete.wav",
    "info": "Windows Balloon.wav",
    "discovery": "Windows Balloon.wav",
    "damage": "Windows Critical Stop.wav",
    "pickup": "Windows Balloon.wav",
    "repair": "Windows Print complete.wav",
    "victory": "tada.wav",
    "game_over": "Windows Shutdown.wav",
    "aria_warning": "Windows Exclamation.wav",
    "boot": "Windows Logon.wav",
    "scan": "Windows Balloon.wav",
    "trade": "Windows Print complete.wav",
    "escort": "tada.wav",
    "upgrade": "Windows Print complete.wav",
    "hazard_geyser": "Windows Critical Stop.wav",
    "hazard_ice": "Windows Critical Stop.wav",
    "hazard_storm": "Windows Exclamation.wav",
}

_WINDOWS_BEEP_MAP = {
    "error": 0x10,  # MB_ICONHAND
    "warning": 0x30,  # MB_ICONEXCLAMATION
    "success": 0x40,  # MB_ICONASTERISK
    "info": 0x40,  # MB_ICONASTERISK
    "damage": 0x10,  # MB_ICONHAND
    "victory": 0x40,  # MB_ICONASTERISK
    "game_over": 0x10,  # MB_ICONHAND
    "aria_warning": 0x30,  # MB_ICONEXCLAMATION
}


def _play_windows(event):
    try:
        import winsound
    except ImportError:
        _play_beep_pattern(event)
        return

    filename = _WINDOWS_WAV_MAP.get(event)
    if filename:
        path = os.path.join(_WINDOWS_MEDIA, filename)
        if os.path.exists(path):
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except Exception:
                pass

    beep_type = _WINDOWS_BEEP_MAP.get(event)
    if beep_type is not None:
        try:
            winsound.MessageBeep(beep_type)
            return
        except Exception:
            pass

    _play_beep_pattern(event)


# ---------------------------------------------------------------------------
# Linux: paplay/aplay with freedesktop sounds, or terminal bell
# ---------------------------------------------------------------------------

_LINUX_SOUND_DIRS = [
    "/usr/share/sounds/freedesktop/stereo",
    "/usr/share/sounds/gnome/default/alerts",
    "/usr/share/sounds/ubuntu/stereo",
]

_LINUX_MAP = {
    "error": "dialog-error.oga",
    "warning": "dialog-warning.oga",
    "success": "complete.oga",
    "info": "dialog-information.oga",
    "discovery": "message-new-instant.oga",
    "damage": "dialog-error.oga",
    "repair": "complete.oga",
    "victory": "complete.oga",
    "game_over": "dialog-error.oga",
    "aria_warning": "dialog-warning.oga",
    "boot": "service-login.oga",
    "scan": "dialog-information.oga",
    "trade": "complete.oga",
    "escort": "complete.oga",
    "upgrade": "complete.oga",
    "hazard_geyser": "dialog-error.oga",
    "hazard_ice": "dialog-error.oga",
    "hazard_storm": "dialog-warning.oga",
}

_linux_player = None


def _find_linux_player():
    for player in ("paplay", "aplay", "pw-play"):
        try:
            result = subprocess.run(
                ["which", player],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return player
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def _play_linux(event):
    global _linux_player
    if _linux_player is None:
        _linux_player = _find_linux_player() or ""

    filename = _LINUX_MAP.get(event)
    if filename and _linux_player:
        for d in _LINUX_SOUND_DIRS:
            path = os.path.join(d, filename)
            if os.path.exists(path):
                try:
                    subprocess.run(
                        [_linux_player, path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=3,
                    )
                    return
                except (OSError, subprocess.SubprocessError):
                    pass

    _play_beep_pattern(event)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def play(event: str):
    """Play a system sound for the given game event. Non-blocking.

    Uses beep patterns by default. When the drone's voice_module upgrade
    is installed (set_voice(True)), uses spoken word announcements on macOS.

    Events: error, warning, success, info, discovery, damage, trust,
    chat_open, chat_close, pickup, repair, victory, game_over,
    aria_warning, boot, scan, trade, escort, upgrade,
    hazard_geyser, hazard_ice, hazard_storm
    """
    if not _enabled:
        return

    if _system == "Darwin":
        _play_async(_play_macos, event)
    elif _system == "Windows":
        _play_async(_play_windows, event)
    elif _system == "Linux":
        _play_async(_play_linux, event)
