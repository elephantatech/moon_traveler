#!/usr/bin/env python3
"""Moon Traveler CLI — Entry point."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.game import main

if __name__ == "__main__":
    main()
