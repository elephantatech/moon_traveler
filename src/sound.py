"""Cross-platform sound effects using the chime library.

Uses chime's bundled themed .wav files for consistent sound across platforms.
On macOS, the drone voice_module upgrade enables spoken word announcements
via the 'say' command.

All sounds play asynchronously (non-blocking) so they never slow the game.
Sound can be disabled globally via disable().
"""

import logging
import subprocess
import threading

logger = logging.getLogger(__name__)

_enabled = True
_voice_enabled = False
_lock = threading.Lock()

# Map game events → chime function names (success, error, warning, info)
_EVENT_MAP = {
    # Success family
    "success": "success",
    "victory": "success",
    "repair": "success",
    "trade": "success",
    "escort": "success",
    "upgrade": "success",
    "pickup": "success",
    "trust": "success",
    # Error family
    "error": "error",
    "damage": "error",
    "game_over": "error",
    "hazard_geyser": "error",
    "hazard_ice": "error",
    # Warning family
    "warning": "warning",
    "aria_warning": "warning",
    "hazard_storm": "warning",
    # Info family
    "info": "info",
    "discovery": "info",
    "boot": "info",
    "scan": "info",
    "chat_open": "info",
    "chat_close": "info",
}

# macOS voice — 'say' command (only when voice module is installed)
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


def _play_chime(event: str):
    """Play a chime sound for the given event. Runs in a background thread."""
    import platform

    # macOS voice override
    if _voice_enabled and platform.system() == "Darwin":
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

    # Map event to chime type and play
    chime_type = _EVENT_MAP.get(event, "info")
    try:
        import chime

        fn = getattr(chime, chime_type, chime.info)
        fn(sync=False)
    except Exception:
        logger.debug("chime playback failed", exc_info=True)


def play(event: str):
    """Play a sound for the given game event. Non-blocking.

    Uses chime library for cross-platform themed sounds.
    When the drone's voice_module upgrade is installed (set_voice(True)),
    uses spoken word announcements on macOS.

    Events: error, warning, success, info, discovery, damage, trust,
    chat_open, chat_close, pickup, repair, victory, game_over,
    aria_warning, boot, scan, trade, escort, upgrade,
    hazard_geyser, hazard_ice, hazard_storm
    """
    if not _enabled:
        return
    if not _lock.acquire(blocking=False):
        return  # Another sound is playing — skip

    def _run():
        try:
            _play_chime(event)
        finally:
            _lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
