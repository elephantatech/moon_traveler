"""Launch Moon Traveler in Textual TUI mode.

Usage:
    python play_tui.py                    Normal game
    python play_tui.py --help             Show all options
    python play_tui.py --dev              Start with developer diagnostics
    python play_tui.py --super            Max trust, all items, full upgrades (testing)
    python play_tui.py --upgrade          Check for game updates
    python play_tui.py --disable-animation  No ASCII animations
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.tui_app import run_tui

if __name__ == "__main__":
    run_tui()
