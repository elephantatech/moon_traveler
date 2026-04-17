#!/usr/bin/env python3
"""Auto-play script that takes TUI screenshots at key game moments.

Usage: uv run python scripts/tui_screenshots.py

Launches the game in --super mode, injects commands into the game's
command queue, waits for output to render, then captures screenshots.
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.argv = ["play_tui.py", "--super"]

from src.tui_app import MoonTravelerApp

ASSETS_DIR = Path("assets")

# Shared game context — set by a hook in game.py init
_game_ctx = None
_ctx_ready = threading.Event()


# Monkey-patch init_game to capture the context
_original_init = None


def _patched_game_loop(ctx):
    """Intercept game_loop to capture ctx before it runs."""
    global _game_ctx
    _game_ctx = ctx
    _ctx_ready.set()
    return _original_init(ctx)


async def screenshot_pilot(pilot):
    """Inject commands via queue and capture screenshots."""

    ASSETS_DIR.mkdir(exist_ok=True)
    app = pilot.app

    async def take(name, desc):
        await pilot.pause(0.5)
        app.refresh()
        await pilot.pause(0.5)
        app.save_screenshot(str(ASSETS_DIR / f"{name}.svg"))
        print(f"  Saved: assets/{name}.svg — {desc}")

    async def send(text, wait=4.0):
        app.command_queue.put(text)
        await pilot.pause(wait)

    async def respond(text, wait=2.0):
        if app._bridge:
            app._bridge.push_response(text)
        await pilot.pause(wait)

    print("Taking TUI screenshots...\n")

    # Wait for app to mount
    await pilot.pause(3.0)
    await take("tui-title", "Title screen")

    # New Game → Easy mode
    await respond("1", wait=2.0)
    await respond("1", wait=15.0)

    # Wait for game context to be available
    _ctx_ready.wait(timeout=30)
    ctx = _game_ctx
    if not ctx:
        print("  ERROR: Could not capture game context. Exiting.")
        app.command_queue.put(None)
        return

    await take("tui-crash-site", "Crash site after boot")

    await send("look", wait=3.0)
    await take("tui-look", "Look at crash site")

    await send("scan", wait=3.0)
    await take("tui-scan", "Scan results")

    await send("gps", wait=3.0)
    await take("tui-gps", "GPS map")

    await send("inventory", wait=3.0)
    await take("tui-inventory", "Inventory (super mode)")

    await send("status", wait=3.0)
    await take("tui-status", "Player status")

    await send("drone", wait=3.0)
    await take("tui-drone", "Drone status")

    await send("ship", wait=3.0)
    await take("tui-ship-bays", "Ship bays menu")

    await send("help", wait=3.0)
    await take("tui-help", "Help screen")

    await send("inspect ice crystal", wait=3.0)
    await take("tui-inspect", "Inspect item")

    await send("config", wait=3.0)
    await take("tui-config", "Config screen")

    # Find a creature to talk to
    # Get the first location that has a creature
    creature_loc = None
    creature_name = None
    for c in ctx.creatures:
        if not c.following:
            creature_loc = c.location_name
            creature_name = c.name
            break

    if creature_loc and creature_loc != ctx.player.location_name:
        # Travel to the creature's location
        await send(f"travel {creature_loc}", wait=3.0)
        # Travel may ask for confirmation if dangerous
        # Check if we're in ask mode — if so, confirm
        await pilot.pause(1.0)
        if app._ask_mode:
            await respond("y", wait=5.0)
        await take("tui-travel", "Travel to creature location")

        await send("look", wait=3.0)
        await take("tui-location-creature", "Location with creature")

    if creature_name:
        # Talk to the creature
        await send(f"talk {creature_name}", wait=5.0)
        await take("tui-talk-start", "Conversation started")

        # Say hello
        await respond(
            "hello, I crashed here and need help fixing my ship",
            wait=10.0,
        )
        await take("tui-conversation-1", "First response")

        # Ask them to come help
        await respond(
            "would you come to my ship and help me fix it?",
            wait=10.0,
        )
        await take("tui-conversation-2", "Asking for help")

        # Say bye
        await respond("bye", wait=3.0)
        await take("tui-conversation-end", "Conversation ended")

        # Escort the creature (trust is 100 in super mode)
        await send(f"escort", wait=3.0)
        await take("tui-escort", "Escort creature")

    # Travel back to crash site
    await send("travel Crash Site", wait=3.0)
    if app._ask_mode:
        await respond("y", wait=5.0)
    await take("tui-return-crash", "Back at crash site")

    await send("look", wait=3.0)
    await take("tui-crash-return-look", "Crash site after exploring")

    # Ship repair — "ship repair" is a direct subcommand (no bay menu)
    # It shows installable materials then prompts "Install all? (y/n)"
    # send() puts it in command_queue, worker runs _bay_repair(),
    # which calls console.input() for the y/n confirmation (ask mode).
    await send("ship repair", wait=5.0)

    # Wait for ask mode to be active (worker is blocking on ask_queue)
    for _ in range(20):
        if app._ask_mode:
            break
        await pilot.pause(0.5)

    await take("tui-repair-prompt", "Repair install prompt")

    # Confirm installation
    await respond("y", wait=15.0)
    await take("tui-victory", "Victory — mission complete")

    print(f"\nDone! Screenshots saved to {ASSETS_DIR}/")
    app.command_queue.put(None)
    await pilot.pause(1.0)


if __name__ == "__main__":
    # Patch game_loop to capture context
    from src import game

    _original_init = game.game_loop
    game.game_loop = _patched_game_loop

    app = MoonTravelerApp()
    app.run(auto_pilot=screenshot_pilot)
