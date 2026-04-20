#!/usr/bin/env python3
"""Session 1: Play Easy mode — explore, talk to 2 creatures, give gifts, save."""

import sqlite3
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.argv = ["play_tui.py"]

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
            log("  [DB] No database yet")
            return
        with sqlite3.connect(str(db_path)) as conn:
            for t in ["saves", "chat_history", "creature_memory", "leaderboard"]:
                try:
                    n = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                    log(f"  [DB] {t}: {n} rows")
                except sqlite3.OperationalError:
                    pass
    except Exception as e:
        log(f"  [DB] Error: {e}")


def log_creatures(ctx, label=""):
    for c in ctx.creatures:
        following = " FOLLOWING" if c.following else ""
        mem = len(c.memory) if c.memory else 0
        log(
            f"  [{label}] {c.name} ({c.archetype}) trust={c.trust} disp={c.disposition}"
            f" at={c.location_name} mem={mem}c hist={len(c.conversation_history)}m{following}"
        )


def log_state(ctx, label=""):
    if not ctx:
        return
    try:
        p = ctx.player
        log(f"  [{label}] Loc={p.location_name} Food={p.food:.0f}% Water={p.water:.0f}% Suit={p.suit_integrity:.0f}%")
        log(f"  [{label}] Inv={dict(p.inventory)} Known={len(p.known_locations)} Hours={p.hours_elapsed}")
        done = sum(1 for v in ctx.repair_checklist.values() if v)
        log(f"  [{label}] Repair={done}/{len(ctx.repair_checklist)} Escorts={ctx.escorts_completed}")
        if ctx.stats:
            s = ctx.stats
            log(
                f"  [{label}] Cmds={s.commands} Km={s.km_traveled:.1f}"
                f" Talks={len(s.creatures_talked)} Gifts={s.gifts_given}"
            )
        log_creatures(ctx, label)
    except Exception as e:
        log(f"  [{label}] Error: {e}")


async def session1_pilot(pilot):
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

    log("\n--- SESSION 1: PLAY AND SAVE ---")

    await pilot.pause(3.0)

    # New Game → Easy
    if await wait_ask(timeout=5.0):
        await respond("1", wait=2.0)
    if await wait_ask(timeout=5.0):
        await respond("1", wait=3.0)

    log("  Waiting for LLM...")
    await pilot.pause(15.0)

    _ctx_ready.wait(timeout=30)
    ctx = _game_ctx
    if not ctx:
        log("  ERROR: No game context")
        app.exit()
        return

    log_state(ctx, "START")

    # Explore
    await send("look", wait=3.0)
    await send("scan", wait=3.0)
    await send("scan", wait=3.0)
    await send("scan", wait=3.0)
    log_state(ctx, "EXPLORED")

    # Find reachable creatures
    known = ctx.player.known_locations
    reachable = [
        (c.location_name, c.name, c.archetype)
        for c in ctx.creatures
        if c.location_name in known and c.location_name != "Crash Site"
    ]
    log(f"  Reachable creatures: {reachable}")

    talked_to = []

    # Talk to creature 1
    if reachable:
        loc1, name1, arch1 = reachable[0]
        log(f"\n  --- Visiting {name1} ({arch1}) at {loc1} ---")
        await send(f"travel {loc1}", wait=3.0)
        if await wait_ask(timeout=3.0):
            await respond("y", wait=5.0)

        await send(f"talk {name1}", wait=5.0)
        if await wait_ask(timeout=5.0):
            await respond("hello, I crashed and need help fixing my ship", wait=12.0)
        if await wait_ask(timeout=5.0):
            await respond("what do you know about this area?", wait=12.0)
        if await wait_ask(timeout=5.0):
            await respond("bye", wait=3.0)
        talked_to.append(name1)
        log_state(ctx, f"AFTER_{name1}")

        # Pick up items
        loc_obj = ctx.current_location()
        for item in list(loc_obj.items)[:2]:
            await send(f"take {item.replace('_', ' ').title()}", wait=3.0)

        # Give a gift if we have items
        if ctx.player.inventory:
            item = list(ctx.player.inventory.keys())[0]
            await send(f"give {item.replace('_', ' ').title()} to {name1}", wait=3.0)
            log_state(ctx, f"AFTER_GIVE_{name1}")

    # Talk to creature 2
    if len(reachable) > 1:
        loc2, name2, arch2 = reachable[1]
        log(f"\n  --- Visiting {name2} ({arch2}) at {loc2} ---")
        await send(f"travel {loc2}", wait=3.0)
        if await wait_ask(timeout=3.0):
            await respond("y", wait=5.0)

        await send(f"talk {name2}", wait=5.0)
        if await wait_ask(timeout=5.0):
            await respond("can you help me or trade supplies?", wait=12.0)
        if await wait_ask(timeout=5.0):
            await respond("bye", wait=3.0)
        talked_to.append(name2)
        log_state(ctx, f"AFTER_{name2}")

        # Pick up items
        loc_obj = ctx.current_location()
        for item in list(loc_obj.items)[:2]:
            await send(f"take {item.replace('_', ' ').title()}", wait=3.0)

    # Return to crash site and install what we can
    await send("travel Crash Site", wait=3.0)
    if await wait_ask(timeout=3.0):
        await respond("y", wait=5.0)

    await send("ship repair", wait=3.0)
    if await wait_ask(timeout=3.0):
        await respond("y", wait=5.0)

    # Save — pass slot name as argument (cmd_save uses args, not prompt)
    log("\n  --- Saving game ---")
    await send("save walkthrough", wait=3.0)

    log_state(ctx, "SAVED")
    log_db()

    log(f"\n  Talked to: {talked_to}")
    log("  Session 1 complete — quitting")

    # Quit
    await send("quit", wait=2.0)
    if await wait_ask(timeout=5.0):
        await respond("y", wait=2.0)

    await pilot.pause(3.0)
    app.exit()


if __name__ == "__main__":
    from src import game

    _original_game_loop = game.game_loop
    game.game_loop = _patched_game_loop

    app = MoonTravelerApp()
    app.run(auto_pilot=session1_pilot)
