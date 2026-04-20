#!/usr/bin/env python3
"""Full gameplay walkthrough — plays Easy mode naturally, talks to multiple creatures,
monitors database and game state throughout.

Usage: uv run python scripts/tui_walkthrough.py

Unlike tui_screenshots.py (which uses --super for quick screenshots), this script
plays the game organically: scan, explore, talk, build trust, escort, repair.
"""

import sqlite3
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.argv = ["play_tui.py"]  # Normal mode, no --super

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
    """Log SQLite database state."""
    try:
        from src.config import get_data_dir

        db_path = Path(get_data_dir()) / "saves" / "moon_traveler.db"
        if not db_path.exists():
            log("  [DB] No database yet")
            return

        with sqlite3.connect(str(db_path)) as conn:
            for tname in ["saves", "chat_history", "creature_memory", "leaderboard"]:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                    log(f"  [DB] {tname}: {count} rows")
                except sqlite3.OperationalError:
                    pass

            try:
                mems = conn.execute("SELECT creature_id, LENGTH(memory) FROM creature_memory LIMIT 5").fetchall()
                for m in mems:
                    log(f"  [DB]   memory: {m[0]} = {m[1]} chars")
            except sqlite3.OperationalError:
                pass

            try:
                chats = conn.execute(
                    "SELECT creature_id, COUNT(*) FROM chat_history GROUP BY creature_id LIMIT 5"
                ).fetchall()
                for c in chats:
                    log(f"  [DB]   chat: {c[0]} = {c[1]} msgs")
            except sqlite3.OperationalError:
                pass
    except Exception as e:
        log(f"  [DB] Error: {e}")


def log_state(ctx, label=""):
    """Log game state + all creature details."""
    if not ctx:
        log(f"  [{label}] No context")
        return
    try:
        p = ctx.player
        log(f"  [{label}] Location: {p.location_name}")
        log(f"  [{label}] Food={p.food:.0f}% Water={p.water:.0f}% Suit={p.suit_integrity:.0f}%")
        log(f"  [{label}] Inventory: {dict(p.inventory)}")
        log(f"  [{label}] Known: {len(p.known_locations)} locations")
        log(f"  [{label}] Hours: {p.hours_elapsed}")

        done = sum(1 for v in ctx.repair_checklist.values() if v)
        total = len(ctx.repair_checklist)
        log(f"  [{label}] Repair: {done}/{total}")
        log(f"  [{label}] Escorts: {ctx.escorts_completed}")

        if ctx.stats:
            s = ctx.stats
            log(
                f"  [{label}] Stats: cmds={s.commands} km={s.km_traveled:.1f}"
                f" talks={len(s.creatures_talked)} gifts={s.gifts_given}"
                f" hazards={s.hazards_survived}"
            )

        # All creatures
        for c in ctx.creatures:
            following = " [FOLLOWING]" if c.following else ""
            helped = " [HELPED]" if c.helped_at_ship else ""
            log(
                f"  [{label}] Creature: {c.name} ({c.archetype}) trust={c.trust}"
                f" disp={c.disposition} at={c.location_name}{following}{helped}"
                f" memory={len(c.memory) if c.memory else 0}chars"
                f" history={len(c.conversation_history)}msgs"
            )
    except Exception as e:
        log(f"  [{label}] Error: {e}")


async def walkthrough_pilot(pilot):
    """Play through Easy mode naturally."""

    LOG_FILE.write_text("")
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

    log("=" * 60)
    log("WALKTHROUGH — Easy mode, natural gameplay")
    log("=" * 60)

    # Wait for app to mount
    await pilot.pause(3.0)

    # New Game → Easy
    if await wait_ask(timeout=5.0):
        await respond("1", wait=2.0)
    if await wait_ask(timeout=5.0):
        await respond("1", wait=3.0)

    # LLM loading
    log("Waiting for LLM to load...")
    await pilot.pause(15.0)

    _ctx_ready.wait(timeout=30)
    ctx = _game_ctx
    if not ctx:
        log("ERROR: No game context")
        app.exit()
        return

    log("\n--- GAME STARTED ---")
    log_state(ctx, "START")
    log_db()

    # Phase 1: Explore
    log("\n--- PHASE 1: EXPLORE ---")
    await send("look", wait=3.0)
    await send("scan", wait=3.0)
    log_state(ctx, "AFTER_SCAN_1")

    await send("scan", wait=3.0)
    await send("scan", wait=3.0)
    log_state(ctx, "AFTER_SCAN_3")

    await send("gps", wait=3.0)

    # Find creatures at known locations
    known = ctx.player.known_locations
    creature_locs = []
    for c in ctx.creatures:
        if c.location_name in known and c.location_name != "Crash Site":
            creature_locs.append((c.location_name, c.name, c.archetype))
    log(f"\n  Reachable creatures: {creature_locs}")

    # Phase 2: Visit and talk to first creature
    talked_to = []
    if creature_locs:
        loc1, name1, arch1 = creature_locs[0]
        log(f"\n--- PHASE 2: VISIT {name1} ({arch1}) at {loc1} ---")

        await send(f"travel {loc1}", wait=3.0)
        if await wait_ask(timeout=3.0):
            await respond("y", wait=5.0)
        log_state(ctx, f"ARRIVED_{loc1}")

        await send("look", wait=3.0)

        # Talk — 3 exchanges
        await send(f"talk {name1}", wait=5.0)
        if await wait_ask(timeout=5.0):
            await respond(
                "hello, I crashed here and need help. Do you know where I can find repair materials?",
                wait=12.0,
            )
            log(f"  Response received from {name1}")

        if await wait_ask(timeout=5.0):
            await respond("what is your name and what do you do here?", wait=12.0)
            log(f"  Second exchange with {name1}")

        if await wait_ask(timeout=5.0):
            await respond("bye", wait=3.0)

        talked_to.append(name1)
        log_state(ctx, f"AFTER_TALK_{name1}")
        log_db()

        # Take any items here
        loc_obj = ctx.current_location()
        if loc_obj.items:
            for item in list(loc_obj.items)[:2]:
                display = item.replace("_", " ").title()
                await send(f"take {display}", wait=3.0)
            log_state(ctx, "AFTER_PICKUP")

    # Phase 3: Visit and talk to second creature
    if len(creature_locs) > 1:
        loc2, name2, arch2 = creature_locs[1]
        log(f"\n--- PHASE 3: VISIT {name2} ({arch2}) at {loc2} ---")

        await send(f"travel {loc2}", wait=3.0)
        if await wait_ask(timeout=3.0):
            await respond("y", wait=5.0)
        log_state(ctx, f"ARRIVED_{loc2}")

        await send("look", wait=3.0)

        # Talk — 2 exchanges
        await send(f"talk {name2}", wait=5.0)
        if await wait_ask(timeout=5.0):
            await respond("I need help fixing my ship. Can you help me or trade something?", wait=12.0)

        if await wait_ask(timeout=5.0):
            await respond("bye", wait=3.0)

        talked_to.append(name2)
        log_state(ctx, f"AFTER_TALK_{name2}")
        log_db()

        # Take items
        loc_obj = ctx.current_location()
        if loc_obj.items:
            for item in list(loc_obj.items)[:2]:
                display = item.replace("_", " ").title()
                await send(f"take {display}", wait=3.0)

    # Phase 4: Give a gift if we have items and a creature nearby
    if ctx.player.inventory and talked_to:
        items = list(ctx.player.inventory.keys())
        creature_here = None
        for c in ctx.creatures:
            if c.location_name == ctx.player.location_name and not c.following:
                creature_here = c
                break

        if creature_here and items:
            item = items[0]
            display = item.replace("_", " ").title()
            log(f"\n--- PHASE 4: GIVE {display} to {creature_here.name} ---")
            await send(f"give {display} to {creature_here.name}", wait=3.0)
            log_state(ctx, f"AFTER_GIVE_{creature_here.name}")
            log_db()

    # Phase 5: Check stats and return to crash site
    log("\n--- PHASE 5: STATS AND RETURN ---")
    await send("stats", wait=3.0)
    await send("drone", wait=3.0)
    await send("status", wait=3.0)

    await send("travel Crash Site", wait=3.0)
    if await wait_ask(timeout=3.0):
        await respond("y", wait=5.0)
    log_state(ctx, "BACK_AT_CRASH")

    await send("ship", wait=3.0)

    # Phase 6: Try repair (should fail — not enough materials or escorts)
    log("\n--- PHASE 6: ATTEMPT REPAIR ---")
    await send("ship repair", wait=3.0)
    if await wait_ask(timeout=3.0):
        await respond("y", wait=3.0)
    log_state(ctx, "AFTER_REPAIR_ATTEMPT")

    # Phase 7: Save the game
    log("\n--- PHASE 7: SAVE ---")
    await send("save", wait=3.0)
    if await wait_ask(timeout=5.0):
        await respond("walkthrough", wait=3.0)
    log_db()

    # Final state
    log("\n--- FINAL STATE ---")
    log_state(ctx, "FINAL")
    log_db()

    # Summary
    log("\n" + "=" * 60)
    log("WALKTHROUGH SUMMARY")
    log("=" * 60)
    log(f"  Creatures talked to: {talked_to}")
    log(f"  Total commands: {ctx.stats.commands}")
    log(f"  Distance traveled: {ctx.stats.km_traveled:.1f} km")
    log(f"  Items collected: {ctx.stats.items_collected}")
    log(f"  Gifts given: {ctx.stats.gifts_given}")
    log(f"  Hazards survived: {ctx.stats.hazards_survived}")
    log(f"  Hours elapsed: {ctx.player.hours_elapsed}")
    log(f"  Repair progress: {sum(1 for v in ctx.repair_checklist.values() if v)}/{len(ctx.repair_checklist)}")
    log(f"  Escorts completed: {ctx.escorts_completed}")

    for c in ctx.creatures:
        if c.name in talked_to:
            mem_len = len(c.memory) if c.memory else 0
            log(f"  {c.name}: trust={c.trust} memory={mem_len}chars history={len(c.conversation_history)}msgs")

    log("=" * 60)
    log("Done!")

    await pilot.pause(3.0)
    app.exit()


if __name__ == "__main__":
    from src import game

    _original_game_loop = game.game_loop
    game.game_loop = _patched_game_loop

    app = MoonTravelerApp()
    app.run(auto_pilot=walkthrough_pilot)
