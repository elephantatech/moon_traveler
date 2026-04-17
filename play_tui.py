"""Launch Moon Traveler in Textual TUI mode.

Usage:
    python play_tui.py              Normal game
    python play_tui.py --dev        Start with dev mode enabled
    python play_tui.py --super      Start with super mode (max trust, all items, full upgrades)
    python play_tui.py --dev --super  Both
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.tui_app import run_tui

if __name__ == "__main__":
    run_tui()
