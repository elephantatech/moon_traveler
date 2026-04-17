#!/usr/bin/env python3
"""Auto-play script that takes TUI screenshots at key game moments.

Usage: uv run python scripts/tui_screenshots.py

Launches the game in --super mode with auto_pilot, runs a sequence
of commands, and saves screenshots after each step to assets/.
Runs headless — no terminal needed.

References:
- https://textual.textualize.io/guide/testing/
- https://textual.textualize.io/api/pilot/
- https://textual.textualize.io/api/app/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force --super mode so we have all items and max trust
sys.argv = ["play_tui.py", "--super"]

from src.tui_app import MoonTravelerApp

ASSETS_DIR = Path("assets")


async def screenshot_pilot(pilot):
    """Automated pilot that plays through key game moments and captures screenshots."""

    ASSETS_DIR.mkdir(exist_ok=True)

    async def take(name: str, desc: str):
        await pilot.pause(3.0)  # Wait for output to fully render
        pilot.app.save_screenshot(str(ASSETS_DIR / f"{name}.svg"))
        print(f"  Saved: assets/{name}.svg — {desc}")

    async def type_and_enter(text: str):
        """Type a full command and press Enter."""
        for char in text:
            if char == " ":
                await pilot.press("space")
            else:
                await pilot.press(char)
        await pilot.press("enter")
        await pilot.pause(2.0)  # Wait for command output to render

    # Wait for boot sequence to complete
    print("Taking TUI screenshots...\n")
    await pilot.pause(5)

    # 1. New Game prompt
    await take("tui-new-game", "New Game / Load Game menu")

    # Select New Game (1) then Easy mode (1)
    await pilot.press("1")
    await pilot.press("enter")
    await pilot.pause(2)
    await pilot.press("1")
    await pilot.press("enter")
    await pilot.pause(8)  # Wait for LLM load + boot sequence

    # 2. Crash site after boot
    await take("tui-crash-site", "Crash site with status bar")

    # 3. Look
    await type_and_enter("look")
    await take("tui-look", "Look at current location")

    # 4. Scan
    await type_and_enter("scan")
    await take("tui-scan", "Scan discovering locations")

    # 5. GPS
    await type_and_enter("gps")
    await take("tui-gps", "GPS map view")

    # 6. Inventory
    await type_and_enter("inventory")
    await take("tui-inventory", "Inventory with all items (super mode)")

    # 7. Status
    await type_and_enter("status")
    await take("tui-status", "Player status")

    # 8. Drone
    await type_and_enter("drone")
    await take("tui-drone", "Drone status with all upgrades")

    # 9. Ship bays
    await type_and_enter("ship")
    await take("tui-ship-bays", "Ship bays menu")

    # 10. Ship repair
    await type_and_enter("ship repair")
    await pilot.pause(0.5)
    await take("tui-ship-repair", "Ship repair progress")

    # 11. Help
    await type_and_enter("help")
    await take("tui-help", "Help screen")

    # 12. Inspect an item
    await type_and_enter("inspect ice crystal")
    await take("tui-inspect", "Inspect item description")

    # 13. Config
    await type_and_enter("config")
    await take("tui-config", "Game configuration")

    # 14. Win sequence — install all repair materials
    await type_and_enter("ship repair")
    await pilot.pause(1.0)
    await pilot.press("y")  # Confirm install
    await pilot.press("enter")
    await pilot.pause(5.0)  # Wait for win sequence narration
    await take("tui-victory", "Victory — mission complete")

    print(f"\nDone! Screenshots saved to {ASSETS_DIR}/")


if __name__ == "__main__":
    app = MoonTravelerApp()
    app.run(headless=True, auto_pilot=screenshot_pilot)
