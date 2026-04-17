"""Tests for super mode, CLI flags, and new commands."""

import random

from src.commands import GameContext
from src.drone import Drone
from src.game import REPAIR_MATERIALS, apply_super_mode, build_repair_checklist
from src.player import Player
from src.ship_ai import ShipAI
from src.tutorial import TutorialManager
from src.world import generate_world


def _make_ctx(mode="short"):
    world = generate_world(mode, seed=42)
    rng = random.Random(42)
    from src.creatures import generate_creatures

    creatures = generate_creatures(world, rng, required_materials=REPAIR_MATERIALS[mode])
    player = Player()
    drone = Drone()
    checklist = build_repair_checklist(mode, creatures)
    return GameContext(
        player=player,
        drone=drone,
        locations=world["locations"],
        creatures=creatures,
        world_seed=42,
        world_mode=mode,
        repair_checklist=checklist,
        rng=rng,
        ship_ai=ShipAI(),
        tutorial=TutorialManager(),
    )


class TestApplySuperMode:
    def test_all_creatures_max_trust(self):
        ctx = _make_ctx()
        apply_super_mode(ctx)
        for c in ctx.creatures:
            assert c.trust == 100
            assert c.disposition == "friendly"

    def test_all_repair_materials_in_inventory(self):
        ctx = _make_ctx()
        apply_super_mode(ctx)
        for key in ctx.repair_checklist:
            mat = key.replace("material_", "")
            assert ctx.player.has_item(mat), f"Missing {mat}"

    def test_drone_fully_upgraded(self):
        ctx = _make_ctx()
        apply_super_mode(ctx)
        assert ctx.drone.voice_enabled is True
        assert ctx.drone.autopilot_enabled is True
        assert ctx.drone.charge_module_installed is True
        assert ctx.drone.scanner_range > 10
        assert ctx.drone.cargo_capacity > 10
        assert ctx.drone.speed_boost > 0

    def test_resources_maxed(self):
        ctx = _make_ctx()
        ctx.player.food = 50.0
        ctx.player.water = 30.0
        apply_super_mode(ctx)
        assert ctx.player.food == 100.0
        assert ctx.player.water == 100.0
        assert ctx.player.suit_integrity == 100.0

    def test_skips_materials_already_in_storage(self):
        ctx = _make_ctx()
        mat = REPAIR_MATERIALS["short"][0]
        ctx.player.ship_storage[mat] = 1
        apply_super_mode(ctx)
        # Should not add duplicate to inventory
        assert ctx.player.inventory.get(mat, 0) == 0

    def test_skips_materials_already_in_inventory(self):
        ctx = _make_ctx()
        mat = REPAIR_MATERIALS["short"][0]
        ctx.player.add_item(mat)
        apply_super_mode(ctx)
        # Should still have exactly 1
        assert ctx.player.inventory[mat] == 1

    def test_brutal_mode(self):
        ctx = _make_ctx("brutal")
        apply_super_mode(ctx)
        for key in ctx.repair_checklist:
            mat = key.replace("material_", "")
            assert ctx.player.has_item(mat), f"Missing {mat} in brutal"

    def test_double_apply_does_not_duplicate(self):
        ctx = _make_ctx()
        apply_super_mode(ctx)
        count_before = ctx.player.total_items
        apply_super_mode(ctx)
        assert ctx.player.total_items == count_before


class TestEasterEggAnnounced:
    def test_flag_starts_false(self):
        ctx = _make_ctx()
        assert ctx.easter_egg_announced is False

    def test_flag_can_be_set(self):
        ctx = _make_ctx()
        ctx.easter_egg_announced = True
        assert ctx.easter_egg_announced is True
