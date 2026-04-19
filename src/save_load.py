"""Save and load game state using SQLite with key-value storage."""

import json
import sqlite3
from pathlib import Path

from src import ui
from src.config import get_save_dir
from src.creatures import Creature
from src.drone import Drone
from src.player import Player
from src.world import Location

SAVE_VERSION = 4


def _saves_dir() -> Path:
    return get_save_dir()


def _db_path() -> Path:
    return _saves_dir() / "moon_traveler.db"


def _get_db() -> sqlite3.Connection:
    """Get a connection to the save database, creating tables if needed."""
    saves_dir = _saves_dir()
    saves_dir.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(_db_path()))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saves (
            slot TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (slot, key)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS save_meta (
            slot TEXT PRIMARY KEY,
            save_version INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            slot TEXT NOT NULL,
            creature_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            PRIMARY KEY (slot, creature_id, seq)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS creature_memory (
            slot TEXT NOT NULL,
            creature_id TEXT NOT NULL,
            memory TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (slot, creature_id)
        )
    """)
    conn.commit()
    return conn


def ensure_saves_dir():
    _saves_dir().mkdir(exist_ok=True)


def list_saves() -> list[str]:
    """List all available save slots."""
    ensure_saves_dir()
    slots = []
    db = _db_path()
    saves_dir = _saves_dir()

    # Check SQLite database
    if db.exists():
        try:
            conn = _get_db()
            cursor = conn.execute("SELECT slot FROM save_meta ORDER BY updated_at DESC")
            slots.extend(row[0] for row in cursor.fetchall())
            conn.close()
        except Exception:
            pass

    # Also check for legacy JSON saves (backwards compat)
    for f in saves_dir.glob("*.json"):
        if f.stem not in slots:
            slots.append(f.stem)

    return slots


def save_game(
    slot: str,
    player: Player,
    drone: Drone,
    locations: list[Location],
    creatures: list[Creature],
    world_seed: int,
    world_mode: str,
    repair_checklist: dict,
    ship_ai=None,
    tutorial=None,
    quiet: bool = False,
):
    """Save the entire game state to SQLite as key-value pairs."""
    try:
        conn = _get_db()
    except Exception as e:
        if not quiet:
            ui.error(f"Could not open save database: {e}")
        return

    try:
        _save_to_db(
            conn, slot, player, drone, locations, creatures, world_seed, world_mode, repair_checklist, ship_ai, tutorial
        )
        conn.commit()
        conn.close()
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        if not quiet:
            ui.error(f"Save failed: {e}")
        return

    if not quiet:
        ui.success(f"Game saved to slot '{slot}'.")


def _save_to_db(
    conn, slot, player, drone, locations, creatures, world_seed, world_mode, repair_checklist, ship_ai, tutorial
):
    """Write game state to the database (no commit)."""
    # Build state as key-value pairs
    kv = {
        "world_seed": json.dumps(world_seed),
        "world_mode": json.dumps(world_mode),
        "player": json.dumps(player.to_dict()),
        "drone": json.dumps(drone.to_dict()),
        "locations": json.dumps([loc.to_dict() for loc in locations]),
        "creatures": json.dumps([c.to_dict() for c in creatures]),
        "repair_checklist": json.dumps(repair_checklist),
    }
    if ship_ai is not None:
        kv["ship_ai"] = json.dumps(ship_ai.to_dict())
    if tutorial is not None:
        kv["tutorial"] = json.dumps(tutorial.to_dict())

    # Write all key-value pairs in a transaction
    conn.execute("DELETE FROM saves WHERE slot = ?", (slot,))
    conn.executemany(
        "INSERT INTO saves (slot, key, value) VALUES (?, ?, ?)",
        [(slot, k, v) for k, v in kv.items()],
    )
    conn.execute(
        """
        INSERT INTO save_meta (slot, save_version, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(slot) DO UPDATE SET
            save_version = excluded.save_version,
            updated_at = CURRENT_TIMESTAMP
    """,
        (slot, SAVE_VERSION),
    )

    # Save chat history separately for each creature
    conn.execute("DELETE FROM chat_history WHERE slot = ?", (slot,))
    chat_rows = []
    for creature in creatures:
        for seq, msg in enumerate(creature.conversation_history):
            chat_rows.append((slot, creature.id, seq, msg["role"], msg["content"]))
    if chat_rows:
        conn.executemany(
            "INSERT INTO chat_history (slot, creature_id, seq, role, content) VALUES (?, ?, ?, ?, ?)",
            chat_rows,
        )

    # Save creature memory
    conn.execute("DELETE FROM creature_memory WHERE slot = ?", (slot,))
    mem_rows = [(slot, c.id, c.memory) for c in creatures if c.memory]
    if mem_rows:
        conn.executemany(
            "INSERT INTO creature_memory (slot, creature_id, memory) VALUES (?, ?, ?)",
            mem_rows,
        )


def _load_kv(conn: sqlite3.Connection, slot: str) -> dict | None:
    """Load all key-value pairs for a slot. Returns dict or None."""
    cursor = conn.execute("SELECT key, value FROM saves WHERE slot = ?", (slot,))
    rows = cursor.fetchall()
    if not rows:
        return None
    return {k: json.loads(v) for k, v in rows}


def load_game(slot: str) -> dict | None:
    """Load game state from SQLite or legacy JSON. Returns state dict or None."""
    db = _db_path()
    saves_dir = _saves_dir()

    # Try SQLite first
    if db.exists():
        try:
            conn = _get_db()
            kv = _load_kv(conn, slot)
            if kv:
                # Check save version compatibility
                try:
                    row = conn.execute("SELECT save_version FROM save_meta WHERE slot = ?", (slot,)).fetchone()
                    if row and row[0] > SAVE_VERSION:
                        ui.warn(f"Save '{slot}' was created by a newer game version (v{row[0]} > v{SAVE_VERSION}).")
                        ui.warn("Some features may not load correctly.")
                    elif row and row[0] < 3:
                        ui.warn(f"Save '{slot}' is from an old version (v{row[0]}). Some data may be missing.")
                except Exception:
                    pass
                # Load chat history from dedicated table
                chat = _load_chat_history(conn, slot)
                memories = _load_creature_memory(conn, slot)
                conn.close()
                return _reconstruct_state(kv, chat, memories)
            conn.close()
        except Exception as e:
            ui.error(f"Failed to load from database: {e}")

    # Fall back to legacy JSON
    json_path = saves_dir / f"{slot}.json"
    if json_path.exists():
        return _load_legacy_json(json_path)

    ui.error(f"Save slot '{slot}' not found.")
    return None


def _load_chat_history(conn: sqlite3.Connection, slot: str) -> dict[str, list[dict]]:
    """Load chat history for all creatures in a slot. Returns {creature_id: [messages]}."""
    cursor = conn.execute(
        "SELECT creature_id, role, content FROM chat_history WHERE slot = ? ORDER BY creature_id, seq",
        (slot,),
    )
    history: dict[str, list[dict]] = {}
    for creature_id, role, content in cursor.fetchall():
        if creature_id not in history:
            history[creature_id] = []
        history[creature_id].append({"role": role, "content": content})
    return history


def _load_creature_memory(conn: sqlite3.Connection, slot: str) -> dict[str, str]:
    """Load creature memory for all creatures in a slot. Returns {creature_id: memory_md}."""
    try:
        cursor = conn.execute(
            "SELECT creature_id, memory FROM creature_memory WHERE slot = ?",
            (slot,),
        )
        return {cid: mem for cid, mem in cursor.fetchall()}
    except sqlite3.OperationalError:
        return {}  # Table may not exist in old saves


def _validate_chat_history(chat: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Validate chat history — ensure roles alternate and content is sane."""
    validated = {}
    for creature_id, messages in chat.items():
        clean = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            # Only allow valid roles
            if role not in ("user", "assistant"):
                continue
            # Cap content length (prevent memory bombs)
            if len(content) > 4096:
                content = content[:4096]
            clean.append({"role": role, "content": content})
        # Cap total messages per creature
        if len(clean) > 100:
            clean = clean[-100:]
        validated[creature_id] = clean
    return validated


def _validate_creature_memory(memories: dict[str, str]) -> dict[str, str]:
    """Validate creature memories — cap length and strip injection patterns."""
    from src.llm import _sanitize_memory

    validated = {}
    for creature_id, memory in memories.items():
        # Cap memory length
        if len(memory) > 4096:
            memory = memory[:4096]
        # Strip instruction-like patterns
        memory = _sanitize_memory(memory)
        validated[creature_id] = memory
    return validated


def _reconstruct_state(
    kv: dict, chat: dict[str, list[dict]] | None = None, memories: dict[str, str] | None = None
) -> dict:
    """Reconstruct game objects from key-value pairs."""
    state = {}
    state["world_seed"] = kv["world_seed"]
    state["world_mode"] = kv["world_mode"]
    state["player"] = Player.from_dict(kv["player"])
    state["drone"] = Drone.from_dict(kv["drone"])
    state["locations"] = [Location.from_dict(d) for d in kv["locations"]]
    state["creatures"] = [Creature.from_dict(d) for d in kv["creatures"]]
    state["repair_checklist"] = kv["repair_checklist"]

    # Restore chat history from dedicated table (validated on load)
    if chat:
        chat = _validate_chat_history(chat)
        for creature in state["creatures"]:
            if creature.id in chat:
                creature.conversation_history = chat[creature.id]

    # Restore creature memories (validated — caps length, strips injection patterns)
    if memories:
        memories = _validate_creature_memory(memories)
        for creature in state["creatures"]:
            if creature.id in memories:
                creature.memory = memories[creature.id]

    # Optional fields
    if "ship_ai" in kv:
        from src.ship_ai import ShipAI

        state["ship_ai"] = ShipAI.from_dict(kv["ship_ai"])
    else:
        from src.ship_ai import ShipAI

        ai = ShipAI()
        ai.boot_complete = True
        state["ship_ai"] = ai

    if "tutorial" in kv:
        from src.tutorial import TutorialManager

        state["tutorial"] = TutorialManager.from_dict(kv["tutorial"])
    else:
        from src.tutorial import TutorialManager, TutorialStep

        t = TutorialManager()
        t.step = TutorialStep.COMPLETED
        state["tutorial"] = t

    ui.success("Game loaded.")
    return state


def _load_legacy_json(path: Path) -> dict | None:
    """Load from a legacy JSON save file (v1/v2 format)."""
    try:
        with open(path) as f:
            state = json.load(f)

        state["player"] = Player.from_dict(state["player"])
        state["drone"] = Drone.from_dict(state["drone"])
        state["locations"] = [Location.from_dict(d) for d in state["locations"]]
        state["creatures"] = [Creature.from_dict(d) for d in state["creatures"]]

        if "ship_ai" in state and isinstance(state["ship_ai"], dict):
            from src.ship_ai import ShipAI

            state["ship_ai"] = ShipAI.from_dict(state["ship_ai"])
        else:
            from src.ship_ai import ShipAI

            ai = ShipAI()
            ai.boot_complete = True
            state["ship_ai"] = ai

        if "tutorial" in state and isinstance(state["tutorial"], dict):
            from src.tutorial import TutorialManager

            state["tutorial"] = TutorialManager.from_dict(state["tutorial"])
        else:
            from src.tutorial import TutorialManager, TutorialStep

            t = TutorialManager()
            t.step = TutorialStep.COMPLETED
            state["tutorial"] = t

        ui.success("Game loaded (legacy format).")
        return state
    except Exception as e:
        ui.error(f"Failed to load legacy save: {e}")
        return None


def delete_save(slot: str) -> bool:
    """Delete a save slot."""
    deleted = False
    db = _db_path()
    if db.exists():
        try:
            conn = _get_db()
            conn.execute("DELETE FROM saves WHERE slot = ?", (slot,))
            conn.execute("DELETE FROM save_meta WHERE slot = ?", (slot,))
            conn.execute("DELETE FROM chat_history WHERE slot = ?", (slot,))
            conn.execute("DELETE FROM creature_memory WHERE slot = ?", (slot,))
            conn.commit()
            conn.close()
            deleted = True
        except Exception:
            pass

    # Also remove legacy JSON if it exists
    json_path = _saves_dir() / f"{slot}.json"
    if json_path.exists():
        json_path.unlink()
        deleted = True

    return deleted


def auto_save(
    player: Player,
    drone: Drone,
    locations: list[Location],
    creatures: list[Creature],
    world_seed: int,
    world_mode: str,
    repair_checklist: dict,
    ship_ai=None,
    tutorial=None,
):
    """Auto-save to a dedicated slot (silent)."""
    save_game(
        "autosave",
        player,
        drone,
        locations,
        creatures,
        world_seed,
        world_mode,
        repair_checklist,
        ship_ai,
        tutorial,
        quiet=True,
    )
