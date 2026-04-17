#!/usr/bin/env python3
"""Moon Traveler CLI — Entry point.

Usage:
    python play.py              Normal game
    python play.py --dev        Start with dev mode enabled
    python play.py --super      Start with super mode (max trust, all items, full upgrades)
    python play.py --dev --super  Both
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.game import main

if __name__ == "__main__":
    main()
