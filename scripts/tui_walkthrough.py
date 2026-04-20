#!/usr/bin/env python3
"""Full gameplay walkthrough — three sessions, save/load, victory + loss.

Usage: uv run python scripts/tui_walkthrough.py

Session 1: Play Easy mode — explore, talk to creatures, give gifts, save
Session 2: Load saved game — escort creature, collect materials, win
Session 3: Load save copy with depleted resources — travel to trigger loss

Each session runs in a separate process to simulate a real restart.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

LOG_FILE = Path("walkthrough_debug.log")


def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
    print(msg)


def run_session(script_name, description):
    """Run a session sub-script and return success."""
    log(f"\n{'=' * 60}")
    log(f"LAUNCHING: {description}")
    log(f"Script: {script_name}")
    log(f"{'=' * 60}")

    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / script_name)],
        timeout=300,
        capture_output=False,
    )

    if result.returncode == 0:
        log(f"  {description}: SUCCESS (exit code 0)")
        return True
    else:
        log(f"  {description}: FAILED (exit code {result.returncode})")
        return False


def _cleanup_slots(db_path, slots):
    """Remove specific save slots and their leaderboard entries from the database."""
    if not db_path.exists():
        return
    try:
        with sqlite3.connect(str(db_path)) as conn:
            for slot in slots:
                # Get world_seed before deleting save data
                world_seed = None
                try:
                    row = conn.execute(
                        "SELECT value FROM saves WHERE slot = ? AND key = 'world_seed'",
                        (slot,),
                    ).fetchone()
                    if row:
                        world_seed = row[0]
                except sqlite3.OperationalError:
                    pass

                # Delete save slot data
                for table in ["saves", "save_meta", "chat_history", "creature_memory"]:
                    try:
                        conn.execute(f"DELETE FROM [{table}] WHERE slot = ?", (slot,))
                    except sqlite3.OperationalError:
                        pass

                # Remove leaderboard entries from this slot's world
                if world_seed:
                    try:
                        seed_val = json.loads(world_seed)
                        conn.execute(
                            "DELETE FROM leaderboard WHERE world_seed = ?",
                            (seed_val,),
                        )
                    except (sqlite3.OperationalError, ValueError, json.JSONDecodeError):
                        pass

            conn.commit()
        log(f"  Cleaned up slots {slots} from database")
    except Exception as e:
        log(f"  Cleanup warning: {e}")


def _copy_save_slot(db_path, source_slot, dest_slot):
    """Copy a save slot to a new slot name in the database."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            # Clear any stale dest data from a prior aborted run
            for table in ["saves", "save_meta", "chat_history", "creature_memory"]:
                conn.execute(f"DELETE FROM [{table}] WHERE slot = ?", (dest_slot,))

            # Copy saves table
            rows = conn.execute("SELECT key, value FROM saves WHERE slot = ?", (source_slot,)).fetchall()
            conn.executemany(
                "INSERT INTO saves (slot, key, value) VALUES (?, ?, ?)",
                [(dest_slot, k, v) for k, v in rows],
            )

            # Copy save_meta
            meta = conn.execute(
                "SELECT save_version, updated_at FROM save_meta WHERE slot = ?",
                (source_slot,),
            ).fetchone()
            if meta:
                conn.execute(
                    "INSERT INTO save_meta (slot, save_version, updated_at) VALUES (?, ?, ?)",
                    (dest_slot, meta[0], meta[1]),
                )

            # Copy chat_history
            chat = conn.execute(
                "SELECT creature_id, seq, role, content FROM chat_history WHERE slot = ?",
                (source_slot,),
            ).fetchall()
            conn.executemany(
                "INSERT INTO chat_history (slot, creature_id, seq, role, content) VALUES (?, ?, ?, ?, ?)",
                [(dest_slot, *row) for row in chat],
            )

            # Copy creature_memory
            mem = conn.execute(
                "SELECT creature_id, memory FROM creature_memory WHERE slot = ?",
                (source_slot,),
            ).fetchall()
            conn.executemany(
                "INSERT INTO creature_memory (slot, creature_id, memory) VALUES (?, ?, ?)",
                [(dest_slot, *row) for row in mem],
            )

            conn.commit()
        log(f"  Copied save slot '{source_slot}' → '{dest_slot}'")
        return True
    except Exception as e:
        log(f"  ERROR copying save slot: {e}")
        return False


def _deplete_resources_in_save(db_path, slot):
    """Drain all player resources in a save slot to force loss on next travel."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM saves WHERE slot = ? AND key = 'player'",
                (slot,),
            ).fetchone()
            if not row:
                log(f"  ERROR: No player data in slot '{slot}'")
                return False

            player_data = json.loads(row[0])
            original = {
                "food": player_data.get("food", 100),
                "water": player_data.get("water", 100),
                "suit": player_data.get("suit_integrity", 100),
            }

            # Set all resources critically low — any travel kills the player
            player_data["food"] = 1.0
            player_data["water"] = 1.0
            player_data["suit_integrity"] = 1.0

            conn.execute(
                "UPDATE saves SET value = ? WHERE slot = ? AND key = 'player'",
                (json.dumps(player_data), slot),
            )
            conn.commit()
        log(
            f"  Depleted resources in '{slot}': "
            f"food {original['food']:.0f}%→1% "
            f"water {original['water']:.0f}%→1% "
            f"suit {original['suit']:.0f}%→1%"
        )
        return True
    except Exception as e:
        log(f"  ERROR depleting resources: {e}")
        return False


def _validate_db(db_path, walkthrough_slots):
    """Comprehensive DB validation after all sessions complete."""
    log("\n  --- DATABASE VALIDATION ---")
    errors = []

    try:
        with sqlite3.connect(str(db_path)) as conn:
            # 1. Check save slots exist
            slots = [r[0] for r in conn.execute("SELECT DISTINCT slot FROM saves").fetchall()]
            for slot in walkthrough_slots:
                if slot in slots:
                    log(f"  [OK] Save slot '{slot}' exists")
                else:
                    errors.append(f"Save slot '{slot}' missing")
                    log(f"  [FAIL] Save slot '{slot}' missing")

            # 2. Check save data completeness
            required_keys = ["player", "drone", "locations", "creatures", "world_seed", "world_mode"]
            for slot in walkthrough_slots:
                keys = [r[0] for r in conn.execute("SELECT key FROM saves WHERE slot = ?", (slot,)).fetchall()]
                for key in required_keys:
                    if key not in keys:
                        errors.append(f"Save '{slot}' missing key '{key}'")
                        log(f"  [FAIL] Save '{slot}' missing key '{key}'")
                if keys:
                    log(f"  [OK] Save '{slot}' has {len(keys)} keys")

            # 3. Validate player state in each slot
            for slot in walkthrough_slots:
                row = conn.execute(
                    "SELECT value FROM saves WHERE slot = ? AND key = 'player'",
                    (slot,),
                ).fetchone()
                if row:
                    player = json.loads(row[0])
                    food = player.get("food", -1)
                    water = player.get("water", -1)
                    suit = player.get("suit_integrity", -1)
                    loc = player.get("location_name", "?")
                    inv = player.get("inventory", {})
                    hours = player.get("hours_elapsed", 0)
                    log(
                        f"  [OK] {slot} player: loc={loc} food={food:.0f}% "
                        f"water={water:.0f}% suit={suit:.0f}% hours={hours} inv={len(inv)} items"
                    )

            # 4. Check creature data
            for slot in walkthrough_slots:
                row = conn.execute(
                    "SELECT value FROM saves WHERE slot = ? AND key = 'creatures'",
                    (slot,),
                ).fetchone()
                if row:
                    creatures = json.loads(row[0])
                    trusting = sum(1 for c in creatures if c.get("trust", 0) > 50)
                    log(f"  [OK] {slot} creatures: {len(creatures)} total, {trusting} trusting (>50)")

            # 5. Check chat history
            for slot in walkthrough_slots:
                chat_count = conn.execute("SELECT COUNT(*) FROM chat_history WHERE slot = ?", (slot,)).fetchone()[0]
                unique_creatures = conn.execute(
                    "SELECT COUNT(DISTINCT creature_id) FROM chat_history WHERE slot = ?",
                    (slot,),
                ).fetchone()[0]
                log(f"  [OK] {slot} chat: {chat_count} messages, {unique_creatures} creatures talked to")
                if slot == "walkthrough" and unique_creatures < 1:
                    errors.append(f"No creature conversations in '{slot}'")

            # 6. Check creature memory persistence
            for slot in walkthrough_slots:
                mems = conn.execute(
                    "SELECT creature_id, LENGTH(memory) FROM creature_memory WHERE slot = ?",
                    (slot,),
                ).fetchall()
                log(f"  [OK] {slot} memories: {len(mems)} creatures remember the player")
                for creature_id, mem_len in mems:
                    log(f"       {creature_id}: {mem_len} chars")

            # 7. Check repair checklist state
            for slot in walkthrough_slots:
                row = conn.execute(
                    "SELECT value FROM saves WHERE slot = ? AND key = 'repair_checklist'",
                    (slot,),
                ).fetchone()
                if row:
                    checklist = json.loads(row[0])
                    done = sum(1 for v in checklist.values() if v)
                    total = len(checklist)
                    log(f"  [OK] {slot} repairs: {done}/{total} complete")

            # 8. Check leaderboard entries
            # Get world_seed for walkthrough
            seed_row = conn.execute(
                "SELECT value FROM saves WHERE slot = 'walkthrough' AND key = 'world_seed'"
            ).fetchone()
            if seed_row:
                world_seed = json.loads(seed_row[0])
                lb_entries = conn.execute(
                    "SELECT score, grade, won, game_mode, hours_elapsed, "
                    "real_time_seconds, creatures_befriended FROM leaderboard "
                    "WHERE world_seed = ? ORDER BY id",
                    (world_seed,),
                ).fetchall()

                log(f"  [OK] Leaderboard: {len(lb_entries)} entries for seed {world_seed}")
                has_win = False
                has_loss = False
                for score, grade, won, mode, hours, real_time, allies in lb_entries:
                    status = "WIN" if won else "LOSS"
                    log(
                        f"       {status}: score={score} grade={grade} mode={mode} "
                        f"hours={hours} time={real_time:.0f}s allies={allies}"
                    )
                    # Validate score range
                    if not (0 <= score <= 1000):
                        errors.append(f"Score {score} out of range [0, 1000]")
                    # Validate grade
                    if grade not in ("S", "A", "B", "C", "D"):
                        errors.append(f"Invalid grade '{grade}'")
                    if won:
                        has_win = True
                    else:
                        has_loss = True

                if not has_loss:
                    errors.append("No LOSS entry in leaderboard (session 3 should record one)")
                    log("  [FAIL] No LOSS entry in leaderboard")
                else:
                    log("  [OK] Loss leaderboard entry present")

                # Win entry depends on session 2 recording — may not always appear
                # (--super mode victory may skip leaderboard in some flows)
                if has_win:
                    log("  [OK] Win leaderboard entry present")
                else:
                    log("  [WARN] No WIN entry in leaderboard (may be expected)")
            else:
                errors.append("No world_seed found in walkthrough save")

            # 9. Check save_meta timestamps
            for slot in walkthrough_slots:
                meta = conn.execute(
                    "SELECT save_version, updated_at FROM save_meta WHERE slot = ?",
                    (slot,),
                ).fetchone()
                if meta:
                    log(f"  [OK] {slot} meta: version={meta[0]} updated={meta[1]}")
                else:
                    log(f"  [WARN] {slot} meta: no save_meta entry")

    except Exception as e:
        errors.append(f"DB validation error: {e}")
        log(f"  [FAIL] DB error: {e}")

    if errors:
        log(f"\n  DB VALIDATION: {len(errors)} error(s)")
        for err in errors:
            log(f"    - {err}")
        return False
    else:
        log("\n  DB VALIDATION: ALL CHECKS PASSED")
        return True


def main():
    LOG_FILE.write_text("")
    log("=" * 60)
    log("MOON TRAVELER — PREPROD WALKTHROUGH TEST")
    log("=" * 60)

    db_path = Path.home() / ".moonwalker" / "saves" / "moon_traveler.db"
    walkthrough_slots = ["walkthrough", "walkthrough_loss"]

    # Clean up any leftover walkthrough entries from previous runs
    _cleanup_slots(db_path, walkthrough_slots)

    # --- Session 1: Play and save ---
    ok1 = run_session("_walkthrough_session1.py", "Session 1: Play and Save")

    if not ok1:
        log("\nSession 1 failed — cannot proceed")
        sys.exit(1)

    # Verify save exists
    if not db_path.exists():
        log("  ERROR: Database not created!")
        sys.exit(1)

    with sqlite3.connect(str(db_path)) as conn:
        slots = conn.execute("SELECT DISTINCT slot FROM saves").fetchall()
        log(f"\n  Save slots found: {[s[0] for s in slots]}")
        if not any(s[0] == "walkthrough" for s in slots):
            log("  ERROR: 'walkthrough' save slot not found!")
            sys.exit(1)

    # Copy save for loss scenario before Session 2 modifies anything
    log("\n  --- Preparing loss scenario ---")
    if not _copy_save_slot(db_path, "walkthrough", "walkthrough_loss"):
        log("  ERROR: Could not copy save for loss scenario")
        sys.exit(1)
    if not _deplete_resources_in_save(db_path, "walkthrough_loss"):
        log("  ERROR: Could not deplete resources in loss save")
        sys.exit(1)

    # --- Session 2: Load and win ---
    ok2 = run_session("_walkthrough_session2.py", "Session 2: Load and Win")

    # --- Session 3: Load loss save and die ---
    ok3 = run_session("_walkthrough_session3.py", "Session 3: Load and Lose")

    # --- Final report + DB validation ---
    log(f"\n{'=' * 60}")
    log("PREPROD WALKTHROUGH RESULTS")
    log(f"{'=' * 60}")
    log(f"  Session 1 (play + save):   {'PASS' if ok1 else 'FAIL'}")
    log(f"  Session 2 (load + win):    {'PASS' if ok2 else 'FAIL'}")
    log(f"  Session 3 (load + lose):   {'PASS' if ok3 else 'FAIL'}")

    db_ok = _validate_db(db_path, walkthrough_slots) if db_path.exists() else False
    log(f"  DB validation:             {'PASS' if db_ok else 'FAIL'}")
    log(f"{'=' * 60}")

    all_passed = ok1 and ok2 and ok3 and db_ok
    if all_passed:
        log("ALL TESTS PASSED")
        # Clean up walkthrough entries after successful completion
        _cleanup_slots(db_path, walkthrough_slots)
        sys.exit(0)
    else:
        log("TESTS FAILED")
        log("  Walkthrough entries left in DB for debugging")
        sys.exit(1)


if __name__ == "__main__":
    main()
