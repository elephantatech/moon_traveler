"""Tests for src/tui_bridge.py and heartbeat in src/tui_app.py."""

import logging
import queue
import threading
import time
from unittest.mock import MagicMock, patch

from src.tui_bridge import UIBridge

THREAD_TIMEOUT = 1.0  # max seconds to wait for worker thread


class MockApp:
    """Minimal app mock with bridge queue and ask mode flag."""

    def __init__(self):
        self._bridge_queue = queue.Queue()
        self._ask_mode = False
        self._animation_bar = MagicMock()
        self.update_prompt_label = MagicMock()
        self.update_status_bar = MagicMock()
        self.update_header = MagicMock()
        self.clear_log = MagicMock()


def _make_bridge():
    app = MockApp()
    game_log = MagicMock()
    command_queue = queue.Queue()
    bridge = UIBridge(app, game_log, MagicMock(), MagicMock(), command_queue)
    return bridge, app, game_log, command_queue


def _run_in_thread(fn):
    """Run fn in a daemon thread and return the thread."""
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    return t


class TestSafeCall:
    def test_queues_callback_with_args(self):
        bridge, app, _, _ = _make_bridge()
        callback = MagicMock()
        bridge._safe_call(callback, "arg1", "arg2")
        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is callback
        assert queued_args == ("arg1", "arg2")

    def test_logs_warning_on_queue_failure(self):
        bridge, app, _, _ = _make_bridge()
        app._bridge_queue = MagicMock()
        app._bridge_queue.put_nowait.side_effect = RuntimeError("queue broken")
        with patch("src.tui_bridge.logger") as mock_logger:
            bridge._safe_call(lambda: None)
            mock_logger.warning.assert_called_once()


class TestOutput:
    def test_write_queues_renderable(self):
        bridge, app, game_log, _ = _make_bridge()
        bridge.write("hello")
        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is game_log.write
        assert queued_args == ("hello",)

    def test_print_no_args_writes_blank_line(self):
        bridge, app, game_log, _ = _make_bridge()
        bridge.print()
        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is game_log.write
        assert queued_args == ("",)

    def test_print_single_arg_passes_through(self):
        bridge, app, game_log, _ = _make_bridge()
        bridge.print("test message")
        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is game_log.write
        assert queued_args == ("test message",)

    def test_animate_frame_queues_widget_update(self):
        bridge, app, _, _ = _make_bridge()
        bridge.animate_frame("frame content")
        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is app._animation_bar.update
        assert queued_args == ("frame content",)

    def test_animate_frame_noop_without_animation_bar(self):
        bridge, app, _, _ = _make_bridge()
        del app._animation_bar
        bridge.animate_frame("frame")
        assert app._bridge_queue.empty()

    def test_clear_queues_clear_log(self):
        bridge, app, _, _ = _make_bridge()
        bridge.clear()
        queued_fn, _ = app._bridge_queue.get_nowait()
        assert queued_fn is app.clear_log

    def test_update_status_bar_queues_markup(self):
        bridge, app, _, _ = _make_bridge()
        bridge.update_status_bar("[bold]status[/bold]")
        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is app.update_status_bar
        assert queued_args == ("[bold]status[/bold]",)

    def test_update_header_queues_text(self):
        bridge, app, _, _ = _make_bridge()
        bridge.update_header("header text")
        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is app.update_header
        assert queued_args == ("header text",)


class TestInput:
    def _wait_for_ask_mode(self, app, timeout=THREAD_TIMEOUT):
        """Poll until ask mode is set."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if app._ask_mode:
                return True
            time.sleep(0.005)
        return False

    def test_blocks_until_response_and_toggles_ask_mode(self):
        bridge, app, _, _ = _make_bridge()
        response = None

        def worker():
            nonlocal response
            response = bridge.input("[bold]Name > [/bold]")

        t = _run_in_thread(worker)
        assert self._wait_for_ask_mode(app), "ask_mode was never set"
        assert app._ask_mode is True

        bridge.push_response("Alice")
        t.join(timeout=THREAD_TIMEOUT)

        assert response == "Alice"
        assert app._ask_mode is False

    def test_none_response_raises_keyboard_interrupt(self):
        bridge, app, _, _ = _make_bridge()
        caught_exception = None

        def worker():
            nonlocal caught_exception
            try:
                bridge.input("prompt")
            except BaseException as e:
                caught_exception = e

        t = _run_in_thread(worker)
        assert self._wait_for_ask_mode(app), "ask_mode was never set"
        bridge.push_response(None)
        t.join(timeout=THREAD_TIMEOUT)

        assert isinstance(caught_exception, KeyboardInterrupt)

    def test_strips_rich_markup_from_prompt(self):
        bridge, app, _, _ = _make_bridge()

        def worker():
            bridge.input("[bold cyan]Name > [/bold cyan]")

        t = _run_in_thread(worker)
        assert self._wait_for_ask_mode(app), "ask_mode was never set"
        bridge.push_response("test")
        t.join(timeout=THREAD_TIMEOUT)

        queued_fn, queued_args = app._bridge_queue.get_nowait()
        assert queued_fn is app.update_prompt_label
        assert "[" not in queued_args[0]


class TestGetCommand:
    def test_blocks_until_command_submitted(self):
        bridge, _, _, command_queue = _make_bridge()
        received_command = None

        def worker():
            nonlocal received_command
            received_command = bridge.get_command("Crash Site")

        t = _run_in_thread(worker)
        time.sleep(0.02)  # let thread reach queue.get()
        command_queue.put("look")
        t.join(timeout=THREAD_TIMEOUT)

        assert received_command == "look"
        assert bridge._current_location == "Crash Site"

    def test_returns_none_on_quit(self):
        bridge, _, _, command_queue = _make_bridge()
        received_command = "sentinel"

        def worker():
            nonlocal received_command
            received_command = bridge.get_command("Crash Site")

        t = _run_in_thread(worker)
        time.sleep(0.02)  # let thread reach queue.get()
        command_queue.put(None)
        t.join(timeout=THREAD_TIMEOUT)

        assert received_command is None


class _FakeApp:
    """Minimal app stub for heartbeat tests (no Textual dependency)."""

    def __init__(self):
        self._bridge_queue = queue.Queue()
        self._heartbeat_active = True

    def set_timer(self, delay, callback):
        pass

    def _schedule_heartbeat(self):
        pass


def _make_heartbeat_app():
    """Create a fake app and bind the real _heartbeat method to it."""
    from src.tui_app import MoonTravelerApp

    app = _FakeApp()
    app._heartbeat = MoonTravelerApp._heartbeat.__get__(app, _FakeApp)
    app._schedule_heartbeat = lambda: None
    return app


def _bad_callback():
    raise RuntimeError("widget broken")


class TestHeartbeatEscalation:
    def test_successful_callback_produces_no_logs(self, caplog):
        app = _make_heartbeat_app()
        app._bridge_queue.put((lambda: None, ()))
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        assert len(caplog.records) == 0

    def test_single_failure_logs_warning(self, caplog):
        app = _make_heartbeat_app()
        app._bridge_queue.put((_bad_callback, ()))
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        assert any("bridge callback failed" in r.message for r in caplog.records)
        assert all(r.levelno < logging.ERROR for r in caplog.records)

    def test_5_consecutive_failures_escalates_to_error(self, caplog):
        app = _make_heartbeat_app()
        for _ in range(5):
            app._bridge_queue.put((_bad_callback, ()))
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert "failing repeatedly" in error_records[0].message

    def test_success_between_failures_resets_escalation(self, caplog):
        app = _make_heartbeat_app()
        # 4 failures, then success, then 4 more — never hits 5 consecutive
        for _ in range(4):
            app._bridge_queue.put((_bad_callback, ()))
        app._bridge_queue.put((lambda: None, ()))
        for _ in range(4):
            app._bridge_queue.put((_bad_callback, ()))
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 0

    def test_error_log_is_rate_limited(self, caplog):
        app = _make_heartbeat_app()
        # Queue 110 failures — should get ERROR at #5 and #105, not every failure
        for _ in range(110):
            app._bridge_queue.put((_bad_callback, ()))
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 2  # failure #5 and #105

    def test_empty_queue_produces_no_logs(self, caplog):
        app = _make_heartbeat_app()
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        assert len(caplog.records) == 0

    def test_counter_does_not_persist_across_ticks(self, caplog):
        app = _make_heartbeat_app()
        # Tick 1: 3 failures
        for _ in range(3):
            app._bridge_queue.put((_bad_callback, ()))
        app._heartbeat()
        caplog.clear()
        # Tick 2: 3 more failures — should NOT escalate (counter reset)
        for _ in range(3):
            app._bridge_queue.put((_bad_callback, ()))
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 0
