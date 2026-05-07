"""Tests for src/tui_bridge.py and heartbeat in src/tui_app.py."""

import logging
import queue
import threading
import time
from unittest.mock import MagicMock, patch

from src.tui_bridge import UIBridge

THREAD_SETTLE = 0.05  # seconds to let worker thread reach blocking call


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


def _run_in_thread(fn, settle=THREAD_SETTLE):
    """Run fn in a thread, wait for it to settle, return the thread."""
    t = threading.Thread(target=fn)
    t.start()
    time.sleep(settle)
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
    def test_blocks_until_response_and_toggles_ask_mode(self):
        bridge, app, _, _ = _make_bridge()
        response = None

        def worker():
            nonlocal response
            response = bridge.input("[bold]Name > [/bold]")

        t = _run_in_thread(worker)

        # Wait for ask mode to be set
        for _ in range(50):
            if app._ask_mode:
                break
            time.sleep(0.01)

        assert app._ask_mode is True

        bridge.push_response("Alice")
        t.join(timeout=1)

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
        bridge.push_response(None)
        t.join(timeout=1)

        assert isinstance(caught_exception, KeyboardInterrupt)

    def test_strips_rich_markup_from_prompt(self):
        bridge, app, _, _ = _make_bridge()

        def worker():
            bridge.input("[bold cyan]Name > [/bold cyan]")

        t = _run_in_thread(worker)
        bridge.push_response("test")
        t.join(timeout=1)

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
        command_queue.put("look")
        t.join(timeout=1)

        assert received_command == "look"
        assert bridge._current_location == "Crash Site"

    def test_returns_none_on_quit(self):
        bridge, _, _, command_queue = _make_bridge()
        received_command = "sentinel"

        def worker():
            nonlocal received_command
            received_command = bridge.get_command("Crash Site")

        t = _run_in_thread(worker)
        command_queue.put(None)
        t.join(timeout=1)

        assert received_command is None


class _FakeApp:
    """Minimal app stub for heartbeat tests (no Textual dependency)."""

    def __init__(self):
        self._bridge_queue = queue.Queue()
        self._heartbeat_active = True
        self._heartbeat_failures = 0

    def set_timer(self, delay, callback):
        pass  # Don't actually schedule next tick

    def _schedule_heartbeat(self):
        pass


def _make_heartbeat_app():
    """Create a fake app and bind the real _heartbeat method to it."""
    from src.tui_app import MoonTravelerApp

    app = _FakeApp()
    # Bind the real _heartbeat method to our fake app
    app._heartbeat = MoonTravelerApp._heartbeat.__get__(app, _FakeApp)
    app._schedule_heartbeat = lambda: None  # no-op to prevent timer scheduling
    return app


class TestHeartbeatEscalation:
    def test_success_resets_failure_counter(self):
        app = _make_heartbeat_app()
        app._heartbeat_failures = 3
        app._bridge_queue.put((lambda: None, ()))
        app._heartbeat()
        assert app._heartbeat_failures == 0

    def test_failure_increments_counter(self):
        app = _make_heartbeat_app()

        def bad_callback():
            raise RuntimeError("widget broken")

        app._bridge_queue.put((bad_callback, ()))
        app._heartbeat()
        assert app._heartbeat_failures == 1

    def test_logs_warning_below_threshold(self, caplog):
        app = _make_heartbeat_app()

        def bad_callback():
            raise RuntimeError("widget broken")

        app._bridge_queue.put((bad_callback, ()))
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        assert any("bridge callback failed" in r.message for r in caplog.records)
        assert all(r.levelno < logging.ERROR for r in caplog.records)

    def test_escalates_to_error_after_5_consecutive(self, caplog):
        app = _make_heartbeat_app()
        app._heartbeat_failures = 4  # Next failure is #5

        def bad_callback():
            raise RuntimeError("widget broken")

        app._bridge_queue.put((bad_callback, ()))
        with caplog.at_level(logging.ERROR):
            app._heartbeat()
        assert app._heartbeat_failures == 5
        assert any(r.levelno == logging.ERROR for r in caplog.records)
        assert any("failing repeatedly" in r.message for r in caplog.records)

    def test_mixed_success_and_failure_resets_counter(self):
        app = _make_heartbeat_app()

        def bad_callback():
            raise RuntimeError("broken")

        # Queue: fail, fail, succeed, fail
        app._bridge_queue.put((bad_callback, ()))
        app._bridge_queue.put((bad_callback, ()))
        app._bridge_queue.put((lambda: None, ()))
        app._bridge_queue.put((bad_callback, ()))
        app._heartbeat()
        # After succeed, counter reset to 0, then one more failure = 1
        assert app._heartbeat_failures == 1

    def test_empty_queue_drains_without_error(self, caplog):
        app = _make_heartbeat_app()
        with caplog.at_level(logging.WARNING):
            app._heartbeat()
        assert len(caplog.records) == 0
        assert app._heartbeat_failures == 0
