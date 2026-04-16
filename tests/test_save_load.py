"""Tests for save/load round-trip, SQLite storage, and backwards compatibility."""

import json
import sqlite3
from unittest.mock import patch

from src.creatures import Creature
from src.drone import Drone
from src.player import Player
from src.save_load import SAVE_VERSION, delete_save, list_saves, load_game, save_game
from src.ship_ai import ShipAI
from src.tutorial import TutorialManager
from src.world import Location


def _make_state():
    """Create a minimal game state for testing."""
    player = Player()
    player.add_item("ice_crystal", 2)
    player.ship_storage = {"bio_gel": 1}
    player.food = 80.0

    drone = Drone()
    drone.battery = 75.0

    locations = [
        Location(name="Crash Site", loc_type="crash_site", x=0, y=0, discovered=True, visited=True),
        Location(name="Frost Ridge", loc_type="ridge", x=5, y=3, items=["metal_shard"]),
    ]

    creatures = [
        Creature(
            id="creature_0", name="Kael", species="Crystallith",
            archetype="Healer", disposition="friendly",
            location_name="Frost Ridge", trust=40,
            can_give_materials=["bio_gel"],
        ),
    ]

    repair_checklist = {"material_ice_crystal": True, "material_metal_shard": False, "material_bio_gel": False}
    ship_ai = ShipAI()
    tutorial = TutorialManager()

    return player, drone, locations, creatures, repair_checklist, ship_ai, tutorial


def _patch_paths(tmp_path):
    """Patch the config to use tmp_path as the save directory."""
    return (
        patch("src.save_load.get_save_dir", return_value=tmp_path),
        patch("src.config.get_save_dir", return_value=tmp_path),
    )


class TestSaveLoad:
    def test_round_trip(self, tmp_path):
        player, drone, locations, creatures, checklist, ship_ai, tutorial = _make_state()

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            save_game("test", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)
            state = load_game("test")

        assert state is not None
        assert state["world_seed"] == 42
        assert state["world_mode"] == "short"
        assert state["player"].food == 80.0
        assert state["player"].has_item("ice_crystal", 2)
        assert state["player"].ship_storage == {"bio_gel": 1}
        assert state["drone"].battery == 75.0
        assert len(state["locations"]) == 2
        assert len(state["creatures"]) == 1
        assert state["creatures"][0].name == "Kael"
        assert state["repair_checklist"]["material_ice_crystal"] is True

    def test_sqlite_db_created(self, tmp_path):
        player, drone, locations, creatures, checklist, ship_ai, tutorial = _make_state()
        db_path = tmp_path / "moon_traveler.db"

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            save_game("test", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)

        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT key FROM saves WHERE slot = 'test'").fetchall()
        keys = {r[0] for r in rows}
        assert "player" in keys
        assert "drone" in keys
        assert "creatures" in keys
        conn.close()

    def test_save_version_in_meta(self, tmp_path):
        player, drone, locations, creatures, checklist, ship_ai, tutorial = _make_state()
        db_path = tmp_path / "moon_traveler.db"

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            save_game("test", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT save_version FROM save_meta WHERE slot = 'test'").fetchone()
        assert row[0] == SAVE_VERSION
        conn.close()

    def test_quiet_save_no_output(self, tmp_path, capsys):
        player, drone, locations, creatures, checklist, ship_ai, tutorial = _make_state()

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            save_game(
                "test", player, drone, locations, creatures,
                42, "short", checklist, ship_ai, tutorial, quiet=True,
            )

        captured = capsys.readouterr()
        assert "Game saved" not in captured.out

    def test_load_nonexistent_returns_none(self, tmp_path):
        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            assert load_game("nonexistent") is None

    def test_list_saves(self, tmp_path):
        player, drone, locations, creatures, checklist, ship_ai, tutorial = _make_state()

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            save_game("slot_a", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)
            save_game("slot_b", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)
            saves = list_saves()

        assert "slot_a" in saves
        assert "slot_b" in saves

    def test_delete_save(self, tmp_path):
        player, drone, locations, creatures, checklist, ship_ai, tutorial = _make_state()

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            save_game("deleteme", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)
            assert delete_save("deleteme") is True
            assert load_game("deleteme") is None

    def test_overwrite_save(self, tmp_path):
        player, drone, locations, creatures, checklist, ship_ai, tutorial = _make_state()

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            save_game("test", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)
            player.food = 50.0
            save_game("test", player, drone, locations, creatures, 42, "short", checklist, ship_ai, tutorial)
            state = load_game("test")

        assert state["player"].food == 50.0


class TestBackwardsCompat:
    def test_legacy_json_load(self, tmp_path):
        """Old JSON saves should still load."""
        player, drone, locations, creatures, checklist, _, _ = _make_state()

        state = {
            "save_version": 2,
            "world_seed": 42,
            "world_mode": "short",
            "player": player.to_dict(),
            "drone": drone.to_dict(),
            "locations": [loc.to_dict() for loc in locations],
            "creatures": [c.to_dict() for c in creatures],
            "repair_checklist": checklist,
        }

        path = tmp_path / "legacy.json"
        with open(path, "w") as f:
            json.dump(state, f)

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            loaded = load_game("legacy")

        assert loaded is not None
        assert loaded["world_seed"] == 42
        assert isinstance(loaded["player"], Player)

    def test_v1_save_missing_ship_ai_and_tutorial(self, tmp_path):
        """V1 saves don't have ship_ai or tutorial keys."""
        player, drone, locations, creatures, checklist, _, _ = _make_state()

        state = {
            "save_version": 1,
            "world_seed": 42,
            "world_mode": "short",
            "player": player.to_dict(),
            "drone": drone.to_dict(),
            "locations": [loc.to_dict() for loc in locations],
            "creatures": [c.to_dict() for c in creatures],
            "repair_checklist": checklist,
        }

        path = tmp_path / "v1.json"
        with open(path, "w") as f:
            json.dump(state, f)

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            loaded = load_game("v1")

        assert loaded is not None
        assert isinstance(loaded["ship_ai"], ShipAI)
        assert loaded["ship_ai"].boot_complete is True
        assert isinstance(loaded["tutorial"], TutorialManager)

    def test_list_saves_includes_legacy_json(self, tmp_path):
        """Legacy JSON saves should appear in list_saves."""
        path = tmp_path / "old_save.json"
        path.write_text("{}")

        p1, p2 = _patch_paths(tmp_path)
        with p1, p2:
            saves = list_saves()

        assert "old_save" in saves
