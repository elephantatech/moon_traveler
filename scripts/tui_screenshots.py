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

# Shared game context — set by a hook in game.py
_game_ctx = None
_ctx_ready = threading.Event()

# Monkey-patch game_loop to capture the context
_original_game_loop = None


def _patched_game_loop(ctx):
    """Intercept game_loop to capture ctx before it runs."""
    global _game_ctx
    _game_ctx = ctx
    _ctx_ready.set()
    return _original_game_loop(ctx)


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
        print(f"  >>> send command: {text!r}")
        app.command_queue.put(text)
        await pilot.pause(wait)

    async def respond(text, wait=2.0):
        """Send a response to the ask_queue (for prompts like y/n, menus)."""
        print(f"  >>> respond: {text!r}  (ask_mode={app._ask_mode})")
        if app._bridge:
            app._bridge.push_response(text)
        else:
            # Bridge not ready yet — wait for it
            for _ in range(20):
                await pilot.pause(0.5)
                if app._bridge:
                    app._bridge.push_response(text)
                    break
        await pilot.pause(wait)

    async def wait_for_ask_mode(timeout=10.0):
        """Wait until the app enters ask mode (blocking on a prompt)."""
        elapsed = 0.0
        while elapsed < timeout:
            if app._ask_mode:
                print(f"  ... ask_mode detected after {elapsed:.1f}s")
                return True
            await pilot.pause(0.3)
            elapsed += 0.3
        print(f"  ... ask_mode TIMEOUT after {timeout}s")
        return False

    print("Taking TUI screenshots...\n")

    # Wait for app to mount and bridge to be ready
    await pilot.pause(3.0)
    await take("tui-title", "Title screen")

    # The game flow: main() → _run_session() → prompt_choice (if saves exist) → prompt_choice (difficulty)
    # In --super mode on a fresh install, there may be no saves — goes straight to difficulty.
    # Wait for ask mode to know when a prompt is active.
    if await wait_for_ask_mode(timeout=5.0):
        await respond("1", wait=2.0)  # "New Game" if saves exist, or "Easy" if no saves

    # If that was new/load, we now get the difficulty prompt
    if await wait_for_ask_mode(timeout=5.0):
        await respond("1", wait=3.0)  # "Easy" difficulty

    # LLM loading may take a while
    await pilot.pause(15.0)

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

    # Scan again to discover more locations
    await send("scan", wait=3.0)
    await take("tui-scan-2", "Second scan")

    # Scan a few times to discover locations with creatures
    await send("scan", wait=3.0)
    await send("scan", wait=3.0)

    # Find a creature at a KNOWN location
    creature_loc = None
    creature_name = None
    known = ctx.player.known_locations
    for c in ctx.creatures:
        if not c.following and c.location_name in known and c.location_name != ctx.player.location_name:
            creature_loc = c.location_name
            creature_name = c.name
            break

    if creature_loc:
        # Travel to the creature's location
        await send(f"travel {creature_loc}", wait=3.0)
        # Travel may ask for confirmation if dangerous
        if await wait_for_ask_mode(timeout=3.0):
            await respond("y", wait=5.0)
        await take("tui-travel", "Travel to creature location")

        await send("look", wait=3.0)
        await take("tui-location-creature", "Location with creature")

    if creature_name:
        # Talk to the creature
        await send(f"talk {creature_name}", wait=5.0)
        await take("tui-talk-start", "Conversation started")

        # Say hello — wait for ask mode (conversation input prompt)
        if await wait_for_ask_mode(timeout=5.0):
            await respond(
                "hello, I crashed here and need help fixing my ship",
                wait=10.0,
            )
            await take("tui-conversation-1", "First response")

        # Ask them to come help
        if await wait_for_ask_mode(timeout=5.0):
            await respond(
                "would you come to my ship and help me fix it?",
                wait=10.0,
            )
            await take("tui-conversation-2", "Asking for help")

        # Say bye
        if await wait_for_ask_mode(timeout=5.0):
            await respond("bye", wait=3.0)
            await take("tui-conversation-end", "Conversation ended")

        # Escort the creature (trust is 100 in super mode)
        await send("escort", wait=3.0)
        await take("tui-escort", "Escort creature")

    # Travel back to crash site
    await send("travel Crash Site", wait=3.0)
    if await wait_for_ask_mode(timeout=3.0):
        await respond("y", wait=5.0)
    await take("tui-return-crash", "Back at crash site")

    await send("look", wait=3.0)
    await take("tui-crash-return-look", "Crash site after exploring")

    # Drain any stale responses from ask_queue before repair
    while not app._bridge._ask_queue.empty():
        try:
            app._bridge._ask_queue.get_nowait()
            print("  WARN: drained stale ask_queue entry")
        except Exception:
            break

    # Verify we're at crash site with materials
    print(f"  Location: {ctx.player.location_name}")
    print(f"  Inventory: {dict(ctx.player.inventory)}")
    print(f"  Checklist: {ctx.repair_checklist}")

    # Ship repair — send command and immediately start polling for the y/n prompt
    app.command_queue.put("ship repair")
    await pilot.pause(1.0)

    # Wait for the "Install all? (y/n)" prompt
    if await wait_for_ask_mode(timeout=15.0):
        await take("tui-repair-prompt", "Repair install prompt")
        await respond("y", wait=3.0)
        # Victory sequence: narrated lines + launch art + ally list + MISSION COMPLETE
        # Wait for the play-again prompt as signal that everything rendered
        if await wait_for_ask_mode(timeout=45.0):
            await take("tui-victory", "Victory — mission complete")
            await respond("n", wait=2.0)  # Decline play-again
        else:
            print("  WARN: play-again prompt not detected, taking screenshot anyway")
            await take("tui-victory", "Victory (may be incomplete)")
    else:
        print("  WARN: repair prompt not detected — materials may not be in inventory")
        await take("tui-ship-repair", "Ship repair status")

    print(f"\nDone! Screenshots saved to {ASSETS_DIR}/")
    app.command_queue.put(None)
    await pilot.pause(1.0)


if __name__ == "__main__":
    # Patch game_loop to capture context
    from src import game

    _original_game_loop = game.game_loop
    game.game_loop = _patched_game_loop

    app = MoonTravelerApp()
    app.run(auto_pilot=screenshot_pilot)
