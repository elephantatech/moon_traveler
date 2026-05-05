"""Manual sound demo — plays all game events through speakers.

Usage: uv run python scripts/sound_demo.py

Tests chime mode (default) then voice mode (macOS only).
Not an automated test — use tests/test_sound.py for that.
"""

import time

from src import sound

events = [
    ("boot", "Game start"),
    ("scan", "Scan"),
    ("success", "Success"),
    ("error", "Error"),
    ("warning", "Warning"),
    ("chat_open", "Chat open"),
    ("damage", "Damage"),
    ("repair", "Repair"),
    ("victory", "Victory"),
    ("game_over", "Game over"),
]

print("=== BEEP MODE (default — no voice module) ===\n")
sound.set_voice(False)
for event, label in events:
    print(f"  {label}")
    sound.play(event)
    time.sleep(1.5)

print("\n=== VOICE MODE (after voice_module upgrade) ===\n")
sound.set_voice(True)
for event, label in events:
    print(f"  {label}")
    sound.play(event)
    time.sleep(2.5)

print("\nDone!")
