"""Tests for the DevMode module."""

from src.dev_mode import DevMode, _system_metrics


class TestDevMode:
    def test_initial_state_disabled(self):
        dm = DevMode()
        assert not dm.enabled

    def test_toggle_enables(self):
        dm = DevMode()
        dm.toggle()
        assert dm.enabled

    def test_toggle_twice_disables(self):
        dm = DevMode()
        dm.toggle()
        dm.toggle()
        assert not dm.enabled


class TestSystemMetrics:
    def test_returns_two_strings(self):
        ram, cpu = _system_metrics()
        assert isinstance(ram, str)
        assert isinstance(cpu, str)

    def test_psutil_returns_numbers_or_fallback(self):
        ram, cpu = _system_metrics()
        # Either "X.X MB" or "psutil not installed" or "error: ..."
        assert "MB" in ram or "psutil" in ram or "error" in ram
