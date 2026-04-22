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


def log_db_state(label=""):
    """Log current SQLite database state — tables, row counts, key data."""
    try:
        from src.config import get_data_dir

        db_path = Path(get_data_dir()) / "saves" / "moon_traveler.db"
        if not db_path.exists():
            log(f"  [DB {label}] No database file yet")
            return

        import sqlite3

        with sqlite3.connect(str(db_path)) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t[0] for t in tables]

            log(f"  [DB {label}] Tables: {', '.join(table_names)}")

            for tname in table_names:
                count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                log(f"  [DB {label}] {tname}: {count} rows")

                if tname == "saves" and count > 0:
                    slots = conn.execute("SELECT DISTINCT slot FROM saves").fetchall()
                    log(f"  [DB {label}]   Save slots: {[s[0] for s in slots]}")

                if tname == "leaderboard" and count > 0:
                    rows = conn.execute(
                        "SELECT score, grade, won, game_mode FROM leaderboard ORDER BY id DESC LIMIT 3"
                    ).fetchall()
                    for r in rows:
                        log(f"  [DB {label}]   Score={r[0]} Grade={r[1]} Won={r[2]} Mode={r[3]}")

                if tname == "creature_memory" and count > 0:
                    mems = conn.execute("SELECT creature_id, LENGTH(memory) FROM creature_memory LIMIT 3").fetchall()
                    for m in mems:
                        log(f"  [DB {label}]   {m[0]}: {m[1]} chars")

                if tname == "chat_history" and count > 0:
                    chats = conn.execute(
                        "SELECT creature_id, COUNT(*) FROM chat_history GROUP BY creature_id LIMIT 3"
                    ).fetchall()
                    for c in chats:
                        log(f"  [DB {label}]   {c[0]}: {c[1]} messages")
    except Exception as e:
        log(f"  [DB {label}] Error reading database: {e}")


def log_game_state(ctx, label=""):
    """Log key game state from the live GameContext."""
    if not ctx:
        log(f"  [STATE {label}] No context available")
        return

    try:
        p = ctx.player
        log(f"  [STATE {label}] Location: {p.location_name}")
        log(f"  [STATE {label}] Food={p.food:.0f}% Water={p.water:.0f}% Suit={p.suit_integrity:.0f}%")
        log(f"  [STATE {label}] Inventory: {dict(p.inventory)}")
        log(f"  [STATE {label}] Known locations: {len(p.known_locations)}")

        done = sum(1 for v in ctx.repair_checklist.values() if v)
        total = len(ctx.repair_checklist)
        log(f"  [STATE {label}] Repair: {done}/{total}")

        followers = [c.name for c in ctx.creatures if c.following]
        if followers:
            log(f"  [STATE {label}] Followers: {followers}")

        if ctx.stats:
            s = ctx.stats
            log(
                f"  [STATE {label}] Stats: cmds={s.commands} km={s.km_traveled:.1f}"
                f" talks={len(s.creatures_talked)} hazards={s.hazards_survived}"
            )
    except Exception as e:
        log(f"  [STATE {label}] Error reading game state: {e}")


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

    # Seed leaderboard with sample entries so the scores screenshot isn't empty
    try:
        from src.save_load import record_score

        record_score(820, "A", True, "short", 18, 1200, 3, 12345, player_name="Ripley")
        record_score(650, "B", True, "medium", 35, 2400, 2, 67890, player_name="Dallas")
        record_score(410, "C", False, "long", 12, 900, 1, 11111, player_name="Lambert")
        log("  Seeded 3 leaderboard entries")
    except Exception as e:
        log(f"  WARN: Could not seed leaderboard: {e}")

    # The game flow: main() → _run_session() → prompt_choice (if saves exist) → prompt_choice (difficulty)
    # In --super mode on a fresh install, there may be no saves — goes straight to difficulty.
    # Wait for ask mode to know when a prompt is active.
    if await wait_for_ask_mode(timeout=5.0):
        await respond("1", wait=2.0)  # "New Game" if saves exist, or "Easy" if no saves

    # If that was new/load, we now get the difficulty prompt
    if await wait_for_ask_mode(timeout=5.0):
        await respond("1", wait=2.0)  # "Easy" difficulty

    # Player name prompt
    if await wait_for_ask_mode(timeout=5.0):
        await respond("Screenshot", wait=3.0)  # Player name

    # LLM loading may take a while — capture the narrative intro mid-boot
    # Narrative takes ~5s to render (sleep calls), then LLM loads
    await pilot.pause(12.0)
    await take("tui-intro", "Flight recorder narrative intro")

    await pilot.pause(5.0)

    # Wait for game context to be available
    _ctx_ready.wait(timeout=30)
    ctx = _game_ctx
    if not ctx:
        log("  ERROR: Could not capture game context. Exiting.")
        app.command_queue.put(None)
        return

    await take("tui-crash-site", "Crash site after boot")
    log_game_state(ctx, "GAME_START")
    log_db_state("GAME_START")

    # --- Animation screenshots: temporarily enable animations ---
    from src import animations

    animations.force_enable()

    # Look with binoculars animation — capture mid-animation
    app.command_queue.put("look")
    await pilot.pause(0.8)  # Let binoculars start scanning
    await take("tui-anim-look", "Look animation (binoculars)")
    await pilot.pause(4.0)  # Let animation + beat finish
    await take("tui-look", "Look at crash site")

    # Scan with spinning sensors — capture mid-animation
    app.command_queue.put("scan")
    await pilot.pause(1.0)  # Let scan sensors start spinning
    await take("tui-anim-scan", "Scan animation (sensors)")
    await pilot.pause(5.0)  # Let animation + results finish
    await take("tui-scan", "Scan results")
    log_game_state(ctx, "AFTER_SCAN")

    # Disable animations again for speed
    animations.force_disable()

    await send("gps", wait=4.0)
    await take("tui-gps", "GPS map")

    await send("inventory", wait=4.0)
    await take("tui-inventory", "Inventory (super mode)")

    await send("status", wait=4.0)
    await take("tui-status", "Player status")

    await send("drone", wait=4.0)
    await take("tui-drone", "Drone status")

    await send("ship", wait=4.0)
    await take("tui-ship-bays", "Ship bays menu")

    await send("help", wait=4.0)
    await take("tui-help", "Help screen")

    await send("inspect ice crystal", wait=4.0)
    await take("tui-inspect", "Inspect item")

    await send("config", wait=4.0)
    await take("tui-config", "Config screen")

    await send("stats", wait=4.0)
    await take("tui-stats", "Session stats")

    await send("scores", wait=4.0)
    await take("tui-scores", "Leaderboard (seeded entries)")

    # Scan again to discover more locations
    await send("scan", wait=4.0)
    await take("tui-scan-2", "Second scan")

    # Scan a few times to discover locations with creatures
    await send("scan", wait=4.0)
    await send("scan", wait=4.0)

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
        # Travel with drone animation — enable animations for this
        animations.force_enable()
        app.command_queue.put(f"travel {creature_loc}")
        # Travel may ask for confirmation if dangerous
        if await wait_for_ask_mode(timeout=3.0):
            await respond("y", wait=0.5)
        # Capture mid-flight: departure prints immediately, then frames at 0.35s each
        await pilot.pause(1.0)
        await take("tui-anim-travel", "Travel animation (drone in flight)")
        await pilot.pause(8.0)  # Let full travel + hold + beat finish
        animations.force_disable()
        await take("tui-travel", "Travel to creature location")
        log_game_state(ctx, "AFTER_TRAVEL")

        await send("look", wait=4.0)
        await take("tui-location-creature", "Location with creature")

    if creature_name:
        # Talk to the creature
        await send(f"talk {creature_name}", wait=6.0)
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
            log_game_state(ctx, "AFTER_TALK")
            log_db_state("AFTER_TALK")

        # Escort the creature (trust is 100 in super mode)
        await send("escort", wait=4.0)
        await take("tui-escort", "Escort creature")

    # Travel back to crash site
    await send("travel Crash Site", wait=4.0)
    if await wait_for_ask_mode(timeout=3.0):
        await respond("y", wait=6.0)
    await take("tui-return-crash", "Back at crash site")

    await send("look", wait=4.0)
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
                log_game_state(ctx, "VICTORY")
                log_db_state("VICTORY")
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

    # --- Validation: verify screenshots contain expected content ---
    log("Validating screenshots...")
    import re as _re

    def _svg_text(path):
        """Extract visible text from an SVG file."""
        try:
            with open(path) as f:
                return " ".join(
                    t.replace("&#160;", " ").replace("&#x27;", "'").strip()
                    for t in _re.findall(r">([^<]+)<", f.read())
                    if t.strip() and len(t.strip()) > 2
                )
        except FileNotFoundError:
            return ""

    validations = [
        ("tui-intro", "rescue", "Intro narrative displayed"),
        ("tui-anim-look", ".---.", "Look animation shows binoculars"),
        ("tui-anim-scan", "((", "Scan animation shows sensors"),
        ("tui-anim-travel", "Departing", "Travel animation shows departure"),
        ("tui-help", "drone", "Help shows drone commands"),
        ("tui-ship-bays", "Escort", "Ship bays show escort progress"),
        ("tui-stats", "Commands typed", "Stats shows session metrics"),
        ("tui-scores", "Ripley", "Leaderboard shows seeded entries"),
        ("tui-victory", "Grade", "Victory has score/grade"),
        ("tui-victory", "ARIA", "Victory has ARIA verdict"),
        ("tui-escort", "travel with you", "Escort command worked"),
        ("tui-drone", "Battery", "Drone shows battery"),
        ("tui-inventory", "Qty", "Inventory table rendered"),
    ]

    passed = 0
    failed = 0
    for name, expected, desc in validations:
        text = _svg_text(ASSETS_DIR / f"{name}.svg")
        if expected.lower() in text.lower():
            log(f"  PASS: {desc}")
            passed += 1
        else:
            log(f"  FAIL: {desc} — expected '{expected}' in {name}.svg")
            failed += 1

    log(f"Validation: {passed} passed, {failed} failed")
    if failed:
        log("WARNING: Some validations failed — check screenshots manually")

    # Clean up seeded leaderboard entries and screenshot game results
    try:
        import sqlite3

        from src.save_load import _db_path

        with sqlite3.connect(str(_db_path())) as conn:
            conn.execute("DELETE FROM leaderboard WHERE player_name IN ('Ripley', 'Dallas', 'Lambert', 'Screenshot')")
        log("  Cleaned up seeded leaderboard entries")
    except Exception as e:
        log(f"  WARN: Could not clean leaderboard: {e}")

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
