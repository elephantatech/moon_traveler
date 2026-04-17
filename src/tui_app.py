"""Textual TUI application for Moon Traveler."""

import queue

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, RichLog, Static


class MoonTravelerApp(App):
    """Main Textual application for Moon Traveler Terminal."""

    CSS_PATH = "game.tcss"
    TITLE = "Moon Traveler Terminal"

    def __init__(self):
        super().__init__()
        self.command_queue: queue.Queue[str | None] = queue.Queue()
        self._ask_mode = False
        self._bridge = None  # Set by the worker after init

    def compose(self) -> ComposeResult:
        yield Static("Moon Traveler Terminal", id="header")
        yield RichLog(id="game-log", wrap=True, markup=True, auto_scroll=True)
        yield Static("", id="status-bar")
        with Horizontal(id="input-area"):
            yield Label("", id="prompt-label")
            yield Input(id="game-input", placeholder="Enter command...")

    def on_mount(self) -> None:
        """Start the game worker thread when the app mounts."""
        self.query_one("#game-input", Input).focus()
        self.run_worker(self._game_worker, thread=True)

    def set_suggester(self, ctx) -> None:
        """Attach the game-aware suggester to the input widget. Call from worker via call_from_thread."""
        from src.input_handler import GameSuggester
        game_input = self.query_one("#game-input", Input)
        game_input.suggester = GameSuggester(ctx)

    def _game_worker(self) -> None:
        """Run the full game in a worker thread."""
        from src.tui_bridge import UIBridge

        game_log = self.query_one("#game-log", RichLog)
        status_bar = self.query_one("#status-bar", Static)
        prompt_label = self.query_one("#prompt-label", Label)

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
        except Exception:
            pass
        finally:
            # Game ended — exit the app
            self.call_from_thread(self.exit)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in the input field."""
        text = event.value.strip()
        event.input.clear()

        if self._ask_mode and self._bridge:
            self._bridge.push_response(text)
        else:
            self.command_queue.put(text)

    def enter_ask_mode(self, prompt: str) -> None:
        """Switch input to ask mode (sub-prompts, confirmations)."""
        self._ask_mode = True
        self.query_one("#prompt-label", Label).update(prompt)

    def exit_ask_mode(self) -> None:
        """Restore normal command input mode."""
        self._ask_mode = False

    def update_prompt_label(self, text: str) -> None:
        """Update the prompt label (e.g., location name)."""
        self.query_one("#prompt-label", Label).update(text)

    def update_status_bar(self, markup: str) -> None:
        """Update the fixed status bar."""
        self.query_one("#status-bar", Static).update(markup)

    def update_header(self, text: str) -> None:
        """Update the header bar."""
        self.query_one("#header", Static).update(text)

    def clear_log(self) -> None:
        """Clear the game log."""
        self.query_one("#game-log", RichLog).clear()

    def on_key(self, event) -> None:
        """Handle special keys."""
        if event.key == "ctrl+c":
            if self._ask_mode and self._bridge:
                self._bridge.push_response("")
            else:
                self.command_queue.put(None)


def run_tui():
    """Launch the Textual TUI."""
    app = MoonTravelerApp()
    app.run()
