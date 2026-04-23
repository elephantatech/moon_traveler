"""Textual TUI application for Moon Traveler."""

import queue

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, RichLog, Static


class MoonTravelerApp(App):
    """Main Textual application for Moon Traveler Terminal."""

    CSS_PATH = "game.tcss"
    TITLE = "Moon Traveler Terminal"
    ENABLE_COMMAND_PALETTE = False
    # Allow terminal-native text selection (hold Option/Alt on macOS, or Shift on Linux)
    ALLOW_SELECT = True

    def __init__(self):
        super().__init__()
        self.command_queue: queue.Queue[str | None] = queue.Queue()
        self._ask_mode = False
        self._bridge = None  # Set by the worker after init
        self._tab_candidates: list[str] = []
        self._tab_index: int = -1
        self._tab_prefix: str = ""
        self._command_history: list[str] = []
        self._history_index: int = -1
        self._history_temp: str = ""  # Stores current input when navigating history

    def compose(self) -> ComposeResult:
        yield Static("Moon Traveler Terminal", id="header")
        yield RichLog(id="game-log", wrap=True, markup=True, auto_scroll=True, max_lines=2000)
        yield Static("", id="animation-bar")
        yield Static("", id="status-bar")
        with Horizontal(id="input-area"):
            yield Label("", id="prompt-label")
            yield Input(id="game-input", placeholder="Enter command...")

    def on_mount(self) -> None:
        """Start the game worker thread when the app mounts."""
        # Query widgets on main thread (thread-safe) and store references
        self._header = self.query_one("#header", Static)
        self._game_log = self.query_one("#game-log", RichLog)
        self._animation_bar = self.query_one("#animation-bar", Static)
        self._status_bar = self.query_one("#status-bar", Static)
        self._prompt_label = self.query_one("#prompt-label", Label)
        self._game_input = self.query_one("#game-input", Input)
        self._game_input.focus()
        self.run_worker(self._game_worker, thread=True)

    def set_suggester(self, ctx) -> None:
        """Attach the game-aware suggester to the input widget."""
        from src.input_handler import GameSuggester

        try:
            self._game_input.suggester = GameSuggester(ctx)
        except Exception as e:
            try:
                self._game_log.write(f"[dim]Autocomplete init: {e}[/dim]")
            except Exception:
                pass

    def _game_worker(self) -> None:
        """Run the full game in a worker thread."""
        from src.tui_bridge import UIBridge

        game_log = self._game_log
        status_bar = self._status_bar
        prompt_label = self._prompt_label

        bridge = UIBridge(
            app=self,
            game_log=game_log,
            status_bar=status_bar,
            prompt_label=prompt_label,
            command_queue=self.command_queue,
        )
        self._bridge = bridge

        # Wire the bridge into ui.py so all console calls route through it
        from src import ui

        ui.set_bridge(bridge)

        # Run the game
        from src.game import main as game_main

        try:
            game_main()
        except Exception as e:
            import traceback

            from rich.markup import escape as _esc

            tb = traceback.format_exc()
            self.call_from_thread(
                game_log.write,
                f"[red]CRASH: {_esc(str(e))}[/red]\n[dim]{_esc(tb)}[/dim]",
            )
            import time

            time.sleep(10)  # Keep visible before exit
        finally:
            # Game ended — wait for exit to process on main thread
            import threading

            exit_done = threading.Event()

            def _do_exit():
                self.exit()
                exit_done.set()

            self.call_from_thread(_do_exit)
            exit_done.wait(timeout=5)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Reset tab cycling when the user types a new character."""
        if self._tab_candidates and event.value not in self._tab_candidates:
            self._tab_candidates = []
            self._tab_index = -1

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in the input field."""
        text = event.value.strip()
        event.input.clear()
        self._tab_candidates = []
        self._tab_index = -1
        self._history_index = -1

        # Add to command history (skip duplicates and empty)
        if text and (not self._command_history or self._command_history[-1] != text):
            self._command_history.append(text)

        # Echo the player's input in the game log (escaped to prevent markup injection)
        if text and self._bridge:
            from rich.markup import escape as _esc

            safe = _esc(text)
            if self._ask_mode:
                self._game_log.write(f"[bold]> {safe}[/bold]")
            elif self._bridge._current_location:
                self._game_log.write(f"[bold cyan]{self._bridge._current_location}>[/bold cyan] {safe}")
            else:
                self._game_log.write(f"[bold]> {safe}[/bold]")

        if self._ask_mode and self._bridge:
            self._bridge.push_response(text)
        else:
            self.command_queue.put(text)

    def enter_ask_mode(self, prompt: str) -> None:
        """Switch input to ask mode (sub-prompts, confirmations)."""
        self._ask_mode = True
        self._prompt_label.update(prompt)

    def exit_ask_mode(self) -> None:
        """Restore normal command input mode."""
        self._ask_mode = False

    def update_prompt_label(self, text: str) -> None:
        """Update the prompt label (e.g., location name)."""
        self._prompt_label.update(text)

    def update_status_bar(self, markup: str) -> None:
        """Update the fixed status bar."""
        self._status_bar.update(markup)

    def take_screenshot(self) -> str:
        """Save an SVG screenshot and return the file path."""
        from datetime import datetime
        from pathlib import Path

        filename = f"screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.svg"
        path = Path("assets") / filename
        path.parent.mkdir(exist_ok=True)
        svg = self.export_screenshot()
        path.write_text(svg)
        return str(path)

    def update_header(self, text: str) -> None:
        """Update the header bar."""
        self._header = getattr(self, "_header", None) or self.query_one("#header", Static)
        self._header.update(text)

    def clear_log(self) -> None:
        """Clear the game log."""
        self._game_log.clear()

    def on_key(self, event) -> None:
        """Handle Tab, arrows, F12, Ctrl+C."""
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self._handle_tab()
        elif event.key == "up":
            event.prevent_default()
            event.stop()
            self._history_up()
        elif event.key == "down":
            event.prevent_default()
            event.stop()
            self._history_down()
        elif event.key == "f12":
            event.prevent_default()
            try:
                path = self.take_screenshot()
                self._game_log.write(f"[green]Screenshot saved: {path}[/green]")
            except Exception as e:
                self._game_log.write(f"[red]Screenshot failed: {e}[/red]")
        elif event.key == "ctrl+c":
            if self._ask_mode and self._bridge:
                self._bridge.push_response(None)
            else:
                self.command_queue.put(None)

    def _history_up(self) -> None:
        """Navigate to the previous command in history."""
        if not self._command_history:
            return
        game_input = self._game_input
        if self._history_index == -1:
            # Save current input before navigating
            self._history_temp = game_input.value
            self._history_index = len(self._command_history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        else:
            return  # Already at oldest
        game_input.value = self._command_history[self._history_index]
        game_input.cursor_position = len(game_input.value)

    def _history_down(self) -> None:
        """Navigate to the next command in history."""
        if self._history_index == -1:
            return  # Not navigating history
        if self._history_index < len(self._command_history) - 1:
            self._history_index += 1
            self._game_input.value = self._command_history[self._history_index]
            self._game_input.cursor_position = len(self._game_input.value)
        else:
            # Back to the bottom — restore the saved input
            self._history_index = -1
            self._game_input.value = self._history_temp
            self._game_input.cursor_position = len(self._game_input.value)

    def _handle_tab(self) -> None:
        """Cycle through autocomplete candidates on Tab press."""
        game_input = self._game_input
        if not game_input.has_focus:
            return

        current = game_input.value

        # If we already have candidates and the prefix hasn't changed, cycle
        if self._tab_candidates and current in self._tab_candidates:
            self._tab_index = (self._tab_index + 1) % len(self._tab_candidates)
            choice = self._tab_candidates[self._tab_index]
            game_input.value = choice
            game_input.cursor_position = len(choice)
            return

        # Build new candidate list from the suggester
        self._tab_candidates = []
        self._tab_index = -1
        self._tab_prefix = current

        if not hasattr(game_input, "suggester") or not game_input.suggester:
            return

        suggester = game_input.suggester
        if not hasattr(suggester, "_get_all_suggestions"):
            # Fallback: just use the single suggestion
            if hasattr(game_input, "_suggestion") and game_input._suggestion:
                game_input.value = game_input._suggestion
                game_input.cursor_position = len(game_input.value)
            return

        candidates = suggester._get_all_suggestions(current)
        if not candidates:
            return

        self._tab_candidates = candidates
        self._tab_index = 0
        game_input.value = candidates[0]
        game_input.cursor_position = len(candidates[0])

    def on_unmount(self) -> None:
        """Unblock worker queues when the app exits."""
        self.command_queue.put(None)
        if self._bridge:
            self._bridge.push_response(None)


def run_tui():
    """Launch the Textual TUI."""
    app = MoonTravelerApp()
    app.run()
