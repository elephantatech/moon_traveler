"""Tests for the DevMode module."""

import json
import logging
import tempfile
from pathlib import Path

from src.dev_mode import DevMode, _system_metrics_dict


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
    def test_returns_dict_with_expected_keys(self):
        result = _system_metrics_dict()
        assert isinstance(result, dict)
        assert "ram_rss_mb" in result
        assert "ram_vms_mb" in result
        assert "system_ram_total_gb" in result
        assert "model_loaded" in result
        assert "cpu_percent" in result

    def test_rss_is_number_or_none(self):
        result = _system_metrics_dict()
        assert result["ram_rss_mb"] is None or isinstance(result["ram_rss_mb"], (int, float))


class TestDevModeLogging:
    def test_render_panel_logs_diagnostics(self):
        """render_panel should log a valid JSON diagnostics entry."""
        from src.game import init_game

        ctx = init_game("short", seed=42)
        dm = ctx.dev_mode

        # Set up a log handler to capture output
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            handler = logging.FileHandler(log_file, mode="w")
            handler.setLevel(logging.DEBUG)
            dev_logger = logging.getLogger("dev_mode")
            dev_logger.addHandler(handler)
            dev_logger.setLevel(logging.DEBUG)

            dm.enabled = True
            dm.render_panel(ctx)

            handler.flush()
            dev_logger.removeHandler(handler)
            handler.close()

            assert log_file.exists()
            content = log_file.read_text().strip()
            assert content
            entry = json.loads(content)
            assert entry["event"] == "diagnostics"
            assert "system" in entry
            assert "game" in entry
            assert "locations" in entry
            assert "creatures" in entry
            assert entry["game"]["mode"] == "short"
            assert entry["game"]["seed"] == 42
            assert len(entry["locations"]) == 8
            assert len(entry["creatures"]) == 5
