"""Launch Moon Traveler in Textual TUI mode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.tui_app import run_tui

if __name__ == "__main__":
    run_tui()
