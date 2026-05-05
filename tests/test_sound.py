"""Tests for src/sound.py — chime-based sound system."""

import time
from unittest.mock import MagicMock, patch

from src import sound

THREAD_SETTLE = 0.1  # seconds for daemon thread to execute


class TestEnableDisable:
    def setup_method(self):
        sound.enable()
        sound.set_voice(False)
        sound._chime_available = None

    def test_starts_enabled(self):
        assert sound.is_enabled() is True

    def test_disable_then_enable(self):
        sound.disable()
        assert sound.is_enabled() is False
        sound.enable()
        assert sound.is_enabled() is True

    def test_voice_off_by_default(self):
        assert sound.is_voice_enabled() is False

    def test_voice_toggle(self):
        sound.set_voice(True)
        assert sound.is_voice_enabled() is True
        sound.set_voice(False)
        assert sound.is_voice_enabled() is False


class TestPlay:
    def setup_method(self):
        sound.enable()
        sound.set_voice(False)
        sound._chime_available = None
        if sound._lock.locked():
            sound._lock.release()

    def test_noop_when_disabled(self):
        sound.disable()
        with patch.object(sound, "_play_chime") as mock_chime:
            sound.play("success")
            time.sleep(THREAD_SETTLE)
            mock_chime.assert_not_called()

    def test_skips_when_another_sound_playing(self):
        sound._lock.acquire()
        try:
            with patch.object(sound, "_play_chime") as mock_chime:
                sound.play("success")
                time.sleep(THREAD_SETTLE)
                mock_chime.assert_not_called()
        finally:
            sound._lock.release()

    def test_dispatches_to_play_chime(self):
        with patch.object(sound, "_play_chime") as mock_chime:
            sound.play("info")
            time.sleep(THREAD_SETTLE)
            mock_chime.assert_called_once_with("info")


class TestPlayChime:
    def setup_method(self):
        sound._chime_available = None
        sound.set_voice(False)

    def test_maps_known_event_to_chime_function(self):
        mock_chime = MagicMock()
        with patch.dict("sys.modules", {"chime": mock_chime}):
            sound._chime_available = None
            sound._play_chime("victory")
            mock_chime.success.assert_called_once_with(sync=False)

    def test_unknown_event_defaults_to_info(self):
        mock_chime = MagicMock()
        with patch.dict("sys.modules", {"chime": mock_chime}):
            sound._chime_available = None
            sound._play_chime("unknown_event")
            mock_chime.info.assert_called_once_with(sync=False)

    def test_caches_false_after_import_error(self):
        sound._chime_available = None
        real_import = __import__

        def selective_import(name, *args, **kwargs):
            if name == "chime":
                raise ImportError("no chime")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            sound._play_chime("info")
        assert sound._chime_available is False

    def test_skips_immediately_when_cached_unavailable(self):
        sound._chime_available = False
        mock_chime = MagicMock()
        with patch.dict("sys.modules", {"chime": mock_chime}):
            sound._play_chime("info")
            mock_chime.info.assert_not_called()


class TestVoiceMode:
    def setup_method(self):
        sound.set_voice(True)
        sound._chime_available = None

    def teardown_method(self):
        sound.set_voice(False)

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_plays_say_command_on_macos(self, mock_run, _mock_system):
        sound._play_chime("success")
        mock_run.assert_called_once()
        say_args = mock_run.call_args[0][0]
        assert say_args[0] == "say"
        assert "-v" in say_args
        assert "Samantha" in say_args

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run", side_effect=OSError("no say"))
    def test_falls_back_to_chime_when_say_fails(self, _mock_run, _mock_system):
        mock_chime = MagicMock()
        with patch.dict("sys.modules", {"chime": mock_chime}):
            sound._play_chime("success")
            mock_chime.success.assert_called_once_with(sync=False)

    @patch("platform.system", return_value="Linux")
    def test_uses_chime_on_non_macos(self, _mock_system):
        mock_chime = MagicMock()
        with patch.dict("sys.modules", {"chime": mock_chime}):
            sound._play_chime("success")
            mock_chime.success.assert_called_once_with(sync=False)


class TestEventMap:
    EXPECTED_EVENTS = [
        "success",
        "victory",
        "repair",
        "trade",
        "escort",
        "upgrade",
        "pickup",
        "trust",
        "error",
        "damage",
        "game_over",
        "hazard_geyser",
        "hazard_ice",
        "warning",
        "aria_warning",
        "hazard_storm",
        "info",
        "discovery",
        "boot",
        "scan",
        "chat_open",
        "chat_close",
    ]
    VALID_CHIME_TYPES = {"success", "error", "warning", "info"}

    def test_all_22_events_present(self):
        for event in self.EXPECTED_EVENTS:
            assert event in sound._EVENT_MAP, f"Missing event: {event}"

    def test_all_values_are_valid_chime_types(self):
        for event, chime_type in sound._EVENT_MAP.items():
            assert chime_type in self.VALID_CHIME_TYPES, f"Invalid chime type '{chime_type}' for event '{event}'"
