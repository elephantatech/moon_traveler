#!/usr/bin/env python3
"""Session 2: Load saved game — verify state, escort creature, collect materials, win."""

import sqlite3
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.argv = ["play_tui.py", "--super"]  # Super mode to ensure we can finish

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
        from src.save_load import _db_path

        db_path = _db_path()
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
        log(f"  [{label}] Loc={p.location_name} Food={p.food:.0f}% Water={p.water:.0f}%")
        log(f"  [{label}] Inv={dict(p.inventory)} Known={len(p.known_locations)}")
        done = sum(1 for v in ctx.repair_checklist.values() if v)
        log(f"  [{label}] Repair={done}/{len(ctx.repair_checklist)} Escorts={ctx.escorts_completed}")
        for c in ctx.creatures:
            if c.trust > 10 or c.memory:
                mem = len(c.memory) if c.memory else 0
                f = " FOLLOWING" if c.following else ""
                log(f"  [{label}] {c.name} trust={c.trust} mem={mem}c{f}")
    except Exception as e:
        log(f"  [{label}] Error: {e}")


async def session2_pilot(pilot):
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

    log("\n--- SESSION 2: LOAD AND FINISH ---")

    await pilot.pause(3.0)

    # The game starts with new/load menu since save exists
    # Choose "Load Game"
    if await wait_ask(timeout=5.0):
        await respond("2", wait=2.0)  # Load Game

    # Choose slot
    if await wait_ask(timeout=5.0):
        await respond("walkthrough", wait=5.0)

    # Wait for game to load
    await pilot.pause(15.0)

    _ctx_ready.wait(timeout=30)
    ctx = _game_ctx
    if not ctx:
        log("  ERROR: Could not load game context")
        app.exit()
        return

    log("\n  --- LOADED STATE ---")
    log_state(ctx, "LOADED")
    log_db()

    # Verify state was preserved from session 1
    repairs_before = sum(1 for v in ctx.repair_checklist.values() if v)
    log(f"  VERIFY: Repair progress preserved: {repairs_before}")

    # Check if creatures remember us from session 1
    creatures_with_memory = [c for c in ctx.creatures if c.memory]
    log(f"  VERIFY: Creatures with memory: {len(creatures_with_memory)}")
    for c in creatures_with_memory:
        log(f"  VERIFY: {c.name} remembers: {c.memory[:100]}...")

    # Super mode was applied on load — all materials + max trust
    log_state(ctx, "SUPER_MODE")

    # Find a creature to escort (all have trust 100 from --super)
    escort_target = None
    for c in ctx.creatures:
        if not c.following and c.location_name in ctx.player.known_locations:
            if c.location_name != ctx.player.location_name:
                escort_target = c
                break

    if escort_target:
        log(f"\n  --- Escorting {escort_target.name} ---")
        await send(f"travel {escort_target.location_name}", wait=3.0)
        if await wait_ask(timeout=3.0):
            await respond("y", wait=5.0)

        await send("escort", wait=3.0)
        log_state(ctx, "ESCORTED")

        # Return to crash site with escort
        await send("travel Crash Site", wait=3.0)
        if await wait_ask(timeout=3.0):
            await respond("y", wait=5.0)
        log(f"  Escorts completed after return: {ctx.escorts_completed}")

    # Attempt repair — with super mode materials and escort done
    log("\n  --- FINAL REPAIR ---")
    log_state(ctx, "BEFORE_REPAIR")

    # Handle multiple ask_mode cycles (companion help + install prompt)
    victory = False
    for attempt in range(10):
        if await wait_ask(timeout=15.0):
            from src.game import check_win

            if check_win(ctx):
                log(f"  WIN at attempt {attempt}!")
                victory = True
                break
            log(f"  Prompt (attempt {attempt}), answering y")
            await respond("y", wait=5.0)

            # Wait for ask_mode to clear before re-polling
            for _ in range(20):
                if not app._ask_mode:
                    break
                await pilot.pause(0.3)
        else:
            log(f"  ask_mode timeout at attempt {attempt}")
            # Maybe we need to send ship repair command
            if attempt == 0:
                await send("ship repair", wait=3.0)
            else:
                break

    log_state(ctx, "AFTER_REPAIR")

    if victory:
        log("\n  *** VICTORY! ***")
        # Victory sequence renders, then play-again prompt
        if await wait_ask(timeout=45.0):
            log("  Play-again prompt — victory sequence complete")
            await respond("n", wait=2.0)
    else:
        from src.game import check_win

        if check_win(ctx):
            log("\n  *** VICTORY (detected late)! ***")
            if await wait_ask(timeout=45.0):
                await respond("n", wait=2.0)
        else:
            log("\n  Game not won — check logs for details")

    log("\n  --- FINAL STATE ---")
    log_state(ctx, "FINAL")
    log_db()

    log("  Session 2 complete")
    await pilot.pause(3.0)
    app.exit()


if __name__ == "__main__":
    from src import game

    _original_game_loop = game.game_loop
    game.game_loop = _patched_game_loop

    app = MoonTravelerApp()
    app.run(auto_pilot=session2_pilot)
