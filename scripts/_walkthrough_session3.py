#!/usr/bin/env python3
"""Session 3: Load saved game with depleted resources — travel to trigger loss."""

import sqlite3
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.argv = ["play_tui.py"]  # No --super — natural loss scenario

from src.tui_app import MoonTravelerApp

LOG_FILE = Path("walkthrough_debug.log")
_game_ctx = None
_ctx_ready = threading.Event()
_original_game_loop = None


def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


def _patched_game_loop(ctx):
    global _game_ctx
    _game_ctx = ctx
    _ctx_ready.set()
    return _original_game_loop(ctx)


def log_db():
    try:
        from src.config import get_data_dir

        db_path = Path(get_data_dir()) / "saves" / "moon_traveler.db"
        if not db_path.exists():
            log("  [DB] No database")
            return
        with sqlite3.connect(str(db_path)) as conn:
            for t in ["saves", "chat_history", "creature_memory", "leaderboard"]:
                try:
                    n = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                    log(f"  [DB] {t}: {n} rows")
                except sqlite3.OperationalError:
                    pass
            try:
                lb = conn.execute("SELECT score, grade, won FROM leaderboard ORDER BY id DESC LIMIT 3").fetchall()
                for r in lb:
                    log(f"  [DB]   leaderboard: score={r[0]} grade={r[1]} won={r[2]}")
            except sqlite3.OperationalError:
                pass
    except Exception as e:
        log(f"  [DB] Error: {e}")


def log_state(ctx, label=""):
    if not ctx:
        return
    try:
        p = ctx.player
        log(f"  [{label}] Loc={p.location_name} Food={p.food:.0f}% Water={p.water:.0f}% Suit={p.suit_integrity:.0f}%")
        log(f"  [{label}] Inv={dict(p.inventory)} Known={len(p.known_locations)}")
        done = sum(1 for v in ctx.repair_checklist.values() if v)
        log(f"  [{label}] Repair={done}/{len(ctx.repair_checklist)} Escorts={ctx.escorts_completed}")
    except Exception as e:
        log(f"  [{label}] Error: {e}")


async def session3_pilot(pilot):
    app = pilot.app

    async def send(text, wait=4.0):
        log(f"  >>> {text}")
        app.command_queue.put(text)
        await pilot.pause(wait)

    async def respond(text, wait=2.0):
        log(f"  >>> respond: {text!r}")
        if app._bridge:
            app._bridge.push_response(text)
        else:
            for _ in range(20):
                await pilot.pause(0.5)
                if app._bridge:
                    app._bridge.push_response(text)
                    break
        await pilot.pause(wait)

    async def wait_ask(timeout=10.0):
        elapsed = 0.0
        while elapsed < timeout:
            if app._ask_mode:
                return True
            await pilot.pause(0.3)
            elapsed += 0.3
        return False

    log("\n--- SESSION 3: LOAD AND LOSE (SUIT FAILURE) ---")

    await pilot.pause(3.0)

    # The game starts with new/load menu since save exists
    # Choose "Load Game"
    if await wait_ask(timeout=5.0):
        await respond("2", wait=2.0)  # Load Game

    # Choose slot
    if await wait_ask(timeout=5.0):
        await respond("walkthrough_loss", wait=5.0)

    # Wait for game to load
    await pilot.pause(15.0)

    _ctx_ready.wait(timeout=30)
    ctx = _game_ctx
    if not ctx:
        log("  ERROR: Could not load game context")
        app.exit()
        return

    log("\n  --- LOADED STATE (LOSS SCENARIO) ---")
    log_state(ctx, "LOADED")

    # Resources should already be critically low from DB manipulation
    p = ctx.player
    log(f"  VERIFY: Food={p.food:.1f}% Water={p.water:.1f}% Suit={p.suit_integrity:.1f}% (all near 1%)")

    # Travel repeatedly to trigger suit depletion → game over
    # The game loop checks check_lose() BEFORE accepting the next command,
    # so we just need to get suit to 0 and the loop handles the rest.
    known = ctx.player.known_locations
    destinations = [loc for loc in known if loc != ctx.player.location_name]

    if not destinations:
        log("  ERROR: No known locations to travel to")
        app.exit(return_code=1)
        return

    from src.game import check_lose

    for i, dest in enumerate(destinations[:5]):
        if check_lose(ctx):
            log(f"  LOSS DETECTED after trip {i}: Suit={ctx.player.suit_integrity:.1f}%")
            break

        # Manually wear down suit 1% between trips (environmental exposure)
        if i > 0:
            ctx.player.suit_integrity = max(0, ctx.player.suit_integrity - 1.0)
            log(f"  [WEAR] Suit degraded to {ctx.player.suit_integrity:.1f}%")
            if check_lose(ctx):
                log(f"  LOSS DETECTED from suit wear: Suit={ctx.player.suit_integrity:.1f}%")
                break

        log(f"\n  --- Trip {i + 1}: Traveling to {dest} ---")
        await send(f"travel {dest}", wait=3.0)
        if await wait_ask(timeout=3.0):
            await respond("y", wait=8.0)
        log_state(ctx, f"AFTER_TRIP_{i + 1}")

    # Wait for game over sequence + play-again prompt
    game_over = False
    if await wait_ask(timeout=45.0):
        log("  Play-again prompt detected — game over sequence complete")
        game_over = True
        await respond("n", wait=2.0)

    log("\n  --- FINAL STATE ---")
    log_state(ctx, "FINAL")
    log_db()

    if game_over:
        log("\n  *** GAME OVER CONFIRMED ***")
    else:
        log("\n  WARNING: Game over sequence not detected")

    log("  Session 3 complete")
    await pilot.pause(3.0)
    app.exit()


if __name__ == "__main__":
    from src import game

    _original_game_loop = game.game_loop
    game.game_loop = _patched_game_loop

    app = MoonTravelerApp()
    app.run(auto_pilot=session3_pilot)
