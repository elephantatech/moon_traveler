"""Tests for src/animations.py — animation system controls and gates."""

from unittest.mock import MagicMock, patch

from src import animations


class TestEnabled:
    """Tests for _enabled() and force_disable/force_enable."""

    def setup_method(self):
        animations._force_disabled = False

    def teardown_method(self):
        animations._force_disabled = False

    def test_enabled_by_default(self):
        with patch("src.config.get_animations_enabled", return_value=True):
            assert animations._enabled() is True

    def test_force_disable(self):
        animations.force_disable()
        with patch("src.config.get_animations_enabled", return_value=True):
            assert animations._enabled() is False

    def test_force_enable_reverses_disable(self):
        animations.force_disable()
        animations.force_enable()
        with patch("src.config.get_animations_enabled", return_value=True):
            assert animations._enabled() is True

    def test_config_disabled(self):
        with patch("src.config.get_animations_enabled", return_value=False):
            assert animations._enabled() is False

    def test_force_disabled_takes_priority_over_config(self):
        animations.force_disable()
        with patch("src.config.get_animations_enabled", return_value=True):
            assert animations._enabled() is False


class TestCanAnimate:
    """Tests for _can_animate() — requires both enabled and bridge."""

    def setup_method(self):
        animations._force_disabled = False

    def teardown_method(self):
        animations._force_disabled = False

    def test_false_when_no_animate_frame(self):
        mock_console = MagicMock(spec=[])  # no animate_frame attr
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
        ):
            assert animations._can_animate() is False

    def test_true_when_bridge_present(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
        ):
            assert animations._can_animate() is True

    def test_false_when_disabled_even_with_bridge(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        animations.force_disable()
        with patch.object(animations.ui, "console", mock_console):
            assert animations._can_animate() is False


class TestBeat:
    """Tests for beat() — sleep when enabled, no-op when disabled."""

    def teardown_method(self):
        animations._force_disabled = False

    @patch("src.animations.time.sleep")
    def test_beat_sleeps_when_enabled(self, mock_sleep):
        with patch("src.config.get_animations_enabled", return_value=True):
            animations.beat(0.5)
        mock_sleep.assert_called_once_with(0.5)

    @patch("src.animations.time.sleep")
    def test_beat_noop_when_disabled(self, mock_sleep):
        animations.force_disable()
        animations.beat(0.5)
        mock_sleep.assert_not_called()

    @patch("src.animations.time.sleep")
    def test_beat_default_duration(self, mock_sleep):
        with patch("src.config.get_animations_enabled", return_value=True):
            animations.beat()
        mock_sleep.assert_called_once_with(0.8)


class TestScanSweep:
    """Tests for scan_sweep() fallback and late-game variant."""

    def teardown_method(self):
        animations._force_disabled = False

    @patch("src.animations.time.sleep")
    def test_fallback_when_no_bridge(self, mock_sleep):
        mock_console = MagicMock(spec=["print"])
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
        ):
            animations.scan_sweep()
        mock_console.print.assert_called_once()
        assert "Scanning" in mock_console.print.call_args[0][0]

    def test_late_game_adds_interference_frame(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
            patch("src.animations.time.sleep"),
        ):
            animations.scan_sweep(hours_elapsed=30)
        # Late-game should have interference frame in the calls
        all_frames = [c[0][0] for c in mock_console.animate_frame.call_args_list]
        assert any("Interference" in f for f in all_frames)

    def test_normal_no_interference_frame(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
            patch("src.animations.time.sleep"),
        ):
            animations.scan_sweep(hours_elapsed=10)
        all_frames = [c[0][0] for c in mock_console.animate_frame.call_args_list]
        assert not any("Interference" in f for f in all_frames)


class TestTravelSequence:
    """Tests for travel_sequence() — sprite rendering and fallback."""

    def teardown_method(self):
        animations._force_disabled = False

    @patch("src.animations.time.sleep")
    def test_fallback_prints_and_sleeps(self, mock_sleep):
        mock_console = MagicMock(spec=["print"])
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
        ):
            animations.travel_sequence("Frost Ridge", 1.0, 10.0)
        calls = [c[0][0] for c in mock_console.print.call_args_list]
        assert any("Traveling" in c for c in calls)
        assert any("Arrived" in c for c in calls)

    def test_drone_eyes_upgrade(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
            patch("src.animations.time.sleep"),
        ):
            animations.travel_sequence("X", 1.0, 10.0, upgrade_count=2)
        frames = [c[0][0] for c in mock_console.animate_frame.call_args_list]
        # Upgraded drone has O eyes (Rich-escaped as \[O])
        assert any("\\[O]" in f for f in frames)

    def test_drone_no_upgrade_has_space_eyes(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
            patch("src.animations.time.sleep"),
        ):
            animations.travel_sequence("X", 1.0, 10.0, upgrade_count=0)
        frames = [c[0][0] for c in mock_console.animate_frame.call_args_list]
        # Non-upgraded drone has space eyes (Rich-escaped as \[ ])
        assert any("\\[ ]" in f for f in frames)


class TestDroneTransmit:
    """Tests for drone_transmit() — style variants."""

    def teardown_method(self):
        animations._force_disabled = False

    def test_noop_when_disabled(self):
        animations.force_disable()
        mock_console = MagicMock()
        with patch.object(animations.ui, "console", mock_console):
            animations.drone_transmit()
        # Should not call animate_frame at all
        if hasattr(mock_console, "animate_frame"):
            mock_console.animate_frame.assert_not_called()

    def test_alert_style(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
            patch("src.animations.time.sleep"),
        ):
            animations.drone_transmit(style="alert")
        frames = [c[0][0] for c in mock_console.animate_frame.call_args_list]
        assert any("ALERT" in f for f in frames)


class TestHazardFlash:
    """Tests for hazard_flash() — normal and late-game."""

    def teardown_method(self):
        animations._force_disabled = False

    def test_late_game_has_triple_exclamation(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
            patch("src.animations.time.sleep"),
        ):
            animations.hazard_flash(hours_elapsed=30)
        frames = [c[0][0] for c in mock_console.animate_frame.call_args_list]
        assert any("!!!" in f for f in frames)

    def test_normal_has_hazard(self):
        mock_console = MagicMock()
        mock_console.animate_frame = MagicMock()
        with (
            patch.object(animations.ui, "console", mock_console),
            patch("src.config.get_animations_enabled", return_value=True),
            patch("src.animations.time.sleep"),
        ):
            animations.hazard_flash(hours_elapsed=0)
        frames = [c[0][0] for c in mock_console.animate_frame.call_args_list]
        assert any("HAZARD" in f for f in frames)
