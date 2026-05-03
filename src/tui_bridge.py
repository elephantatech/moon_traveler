"""Bridge between the game worker thread and Textual TUI widgets.

The game logic runs synchronously in a worker thread. This bridge
provides thread-safe methods to push output to Textual widgets and
block the worker until the user provides input.
"""

import logging
import queue
import time

logger = logging.getLogger(__name__)


class UIBridge:
    """Thread-safe bridge between game worker and Textual app."""

    def __init__(self, app, game_log, status_bar, prompt_label, command_queue):
        self._app = app
        self._log = game_log
        self._status = status_bar
        self._label = prompt_label
        self._command_queue = command_queue
        self._ask_queue: queue.Queue[str | None] = queue.Queue()
        self._current_location = ""

    # --- Output (worker thread → Textual main thread) ---

    def _safe_call(self, fn, *args):
        """Queue a callback for the heartbeat to execute on the main thread.

        Bypasses Textual's cross-thread messaging (post_message,
        call_soon_threadsafe) entirely.  The App heartbeat drains this queue
        every ~33 ms using the event loop's own timer, which is reliable on
        Windows ProactorEventLoop.
        """
        try:
            self._app._bridge_queue.put_nowait((fn, args))
        except Exception:
            logger.warning("_safe_call: queue put failed", exc_info=True)

    def write(self, renderable):
        """Write a Rich renderable to the game log."""
        self._safe_call(self._log.write, renderable)

    def print(self, *args, **kwargs):
        """Print to the game log (matches Rich Console.print API).

        Passes Rich renderables (Panel, Table, Text) directly to RichLog.write().
        Strings with Rich markup are passed as-is (RichLog has markup=True).
        Zero args prints a blank line. Multi-arg calls are joined.
        """
        if not args:
            self._safe_call(self._log.write, "")
            return
        if len(args) == 1 and not kwargs:
            self._safe_call(self._log.write, args[0])
            return
        # Multiple args or kwargs: render through a temporary Console
        import io

        from rich.console import Console as _TmpConsole

        buf = io.StringIO()
        tmp = _TmpConsole(file=buf, highlight=False, markup=True)
        tmp.print(*args, **kwargs)
        self._safe_call(self._log.write, buf.getvalue().rstrip("\n"))

    def animate_frame(self, content: str):
        """Update the animation bar widget in-place (single frame)."""
        anim = getattr(self._app, "_animation_bar", None)
        if anim is not None:
            self._safe_call(anim.update, content)

    def clear_animation(self):
        """Clear the animation bar."""
        self.animate_frame("")

    def clear(self):
        """Clear the game log."""
        self._safe_call(self._app.clear_log)

    # --- Input (blocks worker thread until user responds) ---

    def input(self, prompt: str = "") -> str:
        """Block the worker thread until the user submits input.

        Used for all console.input() calls — command prompts, confirmations,
        trade menus, conversation input, etc.
        """
        import re

        clean_prompt = re.sub(r"\[/?[a-z_ ]+\]", "", prompt)

        # Enter ask mode: set flag directly (simple bool assignment, safe
        # without lock) and queue the label update.  Avoids Windows deadlock.
        self._app._ask_mode = True
        self._safe_call(self._app.update_prompt_label, clean_prompt)

        result = self._ask_queue.get()  # Blocks worker thread

        # Exit ask mode
        self._app._ask_mode = False
        self._restore_prompt_label()

        if result is None:
            raise KeyboardInterrupt
        return result

    def push_response(self, text: str | None):
        """Called from Textual main thread when user submits during ask mode."""
        self._ask_queue.put(text)

    # --- Game input (the main command prompt) ---

    def get_command(self, location_name: str) -> str | None:
        """Block worker until user enters a command. Returns None on quit."""
        self._current_location = location_name
        self._safe_call(
            self._app.update_prompt_label,
            f"{location_name} > ",
        )
        result = self._command_queue.get()  # Blocks worker thread
        return result

    # --- Status bar ---

    def update_status_bar(self, markup: str):
        """Update the fixed status bar with Rich markup."""
        self._safe_call(self._app.update_status_bar, markup)

    def update_header(self, text: str):
        """Update the header bar."""
        self._safe_call(self._app.update_header, text)

    # --- Screenshot ---

    def take_screenshot(self) -> str:
        """Take a screenshot from the worker thread. Blocks until done."""
        import threading

        result = []
        done = threading.Event()

        def _do():
            result.append(self._app.take_screenshot())
            done.set()

        self._app._bridge_queue.put_nowait((_do, ()))
        done.wait(timeout=5)
        return result[0] if result else ""

    # --- Helpers ---

    def _restore_prompt_label(self):
        """Restore the prompt label to the current location."""
        if self._current_location:
            self._safe_call(
                self._app.update_prompt_label,
                f"{self._current_location} > ",
            )

    def sleep(self, seconds: float):
        """Sleep in the worker thread (does not block Textual reactor)."""
        time.sleep(seconds)
