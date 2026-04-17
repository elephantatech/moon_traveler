"""Bridge between the game worker thread and Textual TUI widgets.

The game logic runs synchronously in a worker thread. This bridge
provides thread-safe methods to push output to Textual widgets and
block the worker until the user provides input.
"""

import queue
import time

from rich.panel import Panel
from rich.text import Text


class UIBridge:
    """Thread-safe bridge between game worker and Textual app."""

    def __init__(self, app, game_log, status_bar, prompt_label, command_queue):
        self._app = app
        self._log = game_log
        self._status = status_bar
        self._label = prompt_label
        self._command_queue = command_queue
        self._ask_queue: queue.Queue[str] = queue.Queue()
        self._current_location = ""

    # --- Output (worker thread → Textual main thread) ---

    def write(self, renderable):
        """Write a Rich renderable to the game log."""
        self._app.call_from_thread(self._log.write, renderable)

    def print(self, *args, **kwargs):
        """Print markup text to the game log (matches Rich Console.print API)."""
        # Join args into a single string, handle basic Rich markup
        text = " ".join(str(a) for a in args)
        self._app.call_from_thread(self._log.write, text)

    def clear(self):
        """Clear the game log."""
        self._app.call_from_thread(self._app.clear_log)

    # --- Input (blocks worker thread until user responds) ---

    def input(self, prompt: str = "") -> str:
        """Block the worker thread until the user submits input.

        Used for all console.input() calls — command prompts, confirmations,
        trade menus, conversation input, etc.
        """
        # Strip Rich markup from prompt for the label display
        clean_prompt = prompt.replace("[bold]", "").replace("[/bold]", "")
        clean_prompt = clean_prompt.replace("[dim]", "").replace("[/dim]", "")
        clean_prompt = clean_prompt.replace("[cyan]", "").replace("[/cyan]", "")

        self._app.call_from_thread(self._app.enter_ask_mode, clean_prompt)
        result = self._ask_queue.get()  # Blocks worker thread
        self._app.call_from_thread(self._app.exit_ask_mode)
        self._restore_prompt_label()
        return result

    def push_response(self, text: str):
        """Called from Textual main thread when user submits during ask mode."""
        self._ask_queue.put(text)

    # --- Game input (the main command prompt) ---

    def get_command(self, location_name: str) -> str | None:
        """Block worker until user enters a command. Returns None on quit."""
        self._current_location = location_name
        self._app.call_from_thread(
            self._app.update_prompt_label,
            f"{location_name} > ",
        )
        result = self._command_queue.get()  # Blocks worker thread
        return result

    # --- Status bar ---

    def update_status_bar(self, markup: str):
        """Update the fixed status bar with Rich markup."""
        self._app.call_from_thread(self._app.update_status_bar, markup)

    def update_header(self, text: str):
        """Update the header bar."""
        self._app.call_from_thread(self._app.update_header, text)

    # --- Helpers ---

    def _restore_prompt_label(self):
        """Restore the prompt label to the current location."""
        if self._current_location:
            self._app.call_from_thread(
                self._app.update_prompt_label,
                f"{self._current_location} > ",
            )

    def sleep(self, seconds: float):
        """Sleep in the worker thread (does not block Textual reactor)."""
        time.sleep(seconds)
