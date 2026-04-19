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


LOG_FILE = Path("screenshot_debug.log")


def log(msg):
    """Write to a log file (print is captured by Textual)."""
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


async def screenshot_pilot(pilot):
    """Inject commands via queue and capture screenshots."""

    ASSETS_DIR.mkdir(exist_ok=True)
    LOG_FILE.write_text("")  # Clear log
    app = pilot.app

    async def take(name, desc):
        await pilot.pause(0.5)
        app.refresh()
        await pilot.pause(0.5)
        app.save_screenshot(str(ASSETS_DIR / f"{name}.svg"))
        log(f"  Saved: assets/{name}.svg — {desc}")

    async def send(text, wait=4.0):
        log(f"  >>> send command: {text!r}")
        app.command_queue.put(text)
        await pilot.pause(wait)

    async def respond(text, wait=2.0):
        """Send a response to the ask_queue (for prompts like y/n, menus)."""
        log(f"  >>> respond: {text!r}  (ask_mode={app._ask_mode})")
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
                log(f"  ... ask_mode detected after {elapsed:.1f}s")
                return True
            await pilot.pause(0.3)
            elapsed += 0.3
        log(f"  ... ask_mode TIMEOUT after {timeout}s")
        return False

    log("Taking TUI screenshots...")

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
        log("  ERROR: Could not capture game context. Exiting.")
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

    await send("stats", wait=3.0)
    await take("tui-stats", "Session stats")

    await send("scores", wait=3.0)
    await take("tui-scores", "Leaderboard")

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
            log("  WARN: drained stale ask_queue entry")
        except Exception:
            break

    # Verify we're at crash site with materials
    log(f"  Location: {ctx.player.location_name}")
    log(f"  Inventory: {dict(ctx.player.inventory)}")
    log(f"  Checklist: {ctx.repair_checklist}")

    # Ship repair — send command and immediately start polling for the y/n prompt
    app.command_queue.put("ship repair")
    await pilot.pause(1.0)

    # Wait for the "Install all? (y/n)" prompt
    # The repair flow may have multiple ask_mode cycles:
    # 1. Companion may trigger repair prompts (accept companion help)
    # 2. The actual "Install all? (y/n)" prompt
    # 3. The play-again prompt after victory
    # Keep answering "y" until we see the game has been won (check_win)
    victory_captured = False
    for attempt in range(10):
        if await wait_for_ask_mode(timeout=20.0):
            # Check if all materials are installed (game won)
            if all(ctx.repair_checklist.values()):
                log(f"  ... all materials installed! Taking victory screenshot (attempt {attempt})")
                await pilot.pause(3.0)
                app.refresh()
                await pilot.pause(1.0)
                await take("tui-victory", "Victory + post-game score screen")
                await respond("n", wait=2.0)  # Decline play-again
                victory_captured = True
                break

            # Not won yet — take repair prompt on first attempt, then keep answering "y"
            if attempt == 0:
                await take("tui-repair-prompt", "Repair install prompt")
            log(f"  ... answering 'y' to prompt (attempt {attempt}, checklist: {ctx.repair_checklist})")
            await respond("y", wait=2.0)

            # Wait for ask_mode to clear before polling again
            for _ in range(20):
                if not app._ask_mode:
                    break
                await pilot.pause(0.3)
        else:
            log(f"  ... ask_mode timeout on attempt {attempt}")
            break

    if not victory_captured:
        log("  WARN: victory not captured — taking current state")
        await take("tui-victory", "Victory (may be incomplete)")

    log(f"Done! Screenshots saved to {ASSETS_DIR}/")
    # Give the worker time to finish, then force exit
    await pilot.pause(3.0)
    app.exit()


if __name__ == "__main__":
    # Patch game_loop to capture context
    from src import game

    _original_game_loop = game.game_loop
    game.game_loop = _patched_game_loop

    app = MoonTravelerApp()
    app.run(auto_pilot=screenshot_pilot)
