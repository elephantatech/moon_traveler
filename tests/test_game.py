"""Tests for game initialization, win/lose conditions, and repair checklist."""

from src.commands import GameContext
from src.game import REPAIR_MATERIALS, build_repair_checklist, check_lose, check_win, init_game


def _make_ctx(mode="short", **overrides) -> GameContext:
    ctx = init_game(mode, seed=42)
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


class TestRepairChecklist:
    def test_short_has_3_materials(self):
        cl = build_repair_checklist("short")
        assert len(cl) == 3
        assert all(k.startswith("material_") for k in cl)
        assert all(v is False for v in cl.values())

    def test_medium_has_5_materials(self):
        cl = build_repair_checklist("medium")
        assert len(cl) == 5

    def test_long_has_8_materials(self):
        cl = build_repair_checklist("long")
        assert len(cl) == 8

    def test_materials_match_config(self):
        for mode in ("short", "medium", "long"):
            cl = build_repair_checklist(mode)
            for mat in REPAIR_MATERIALS[mode]:
                assert f"material_{mat}" in cl


class TestCheckWin:
    def test_not_won_initially(self):
        ctx = _make_ctx()
        assert check_win(ctx) is False

    def test_won_when_all_done(self):
        ctx = _make_ctx()
        for key in ctx.repair_checklist:
            ctx.repair_checklist[key] = True
        assert check_win(ctx) is True

    def test_not_won_with_one_remaining(self):
        ctx = _make_ctx()
        keys = list(ctx.repair_checklist.keys())
        for k in keys[:-1]:
            ctx.repair_checklist[k] = True
        assert check_win(ctx) is False


class TestCheckLose:
    def test_not_lost_initially(self):
        ctx = _make_ctx()
        assert check_lose(ctx) is False

    def test_lost_with_food_zero(self):
        ctx = _make_ctx()
        ctx.player.food = 0
        ctx.player.water = 50.0
        assert check_lose(ctx) is True

    def test_lost_with_water_zero(self):
        ctx = _make_ctx()
        ctx.player.food = 50.0
        ctx.player.water = 0
        assert check_lose(ctx) is True

    def test_lost_when_both_zero(self):
        ctx = _make_ctx()
        ctx.player.food = 0
        ctx.player.water = 0
        assert check_lose(ctx) is True

    def test_not_lost_with_low_but_nonzero(self):
        ctx = _make_ctx()
        ctx.player.food = 1.0
        ctx.player.water = 1.0
        assert check_lose(ctx) is False


class TestInitGame:
    def test_init_short(self):
        ctx = init_game("short", seed=42)
        assert ctx.world_mode == "short"
        assert ctx.world_seed == 42
        assert len(ctx.locations) == 8
        assert len(ctx.creatures) == 5
        assert ctx.player.location_name == "Crash Site"
        assert ctx.player.food == 100.0

    def test_init_creates_repair_checklist(self):
        ctx = init_game("short", seed=42)
        assert len(ctx.repair_checklist) == 3

    def test_init_different_seeds(self):
        c1 = init_game("short", seed=1)
        c2 = init_game("short", seed=2)
        names1 = {loc.name for loc in c1.locations}
        names2 = {loc.name for loc in c2.locations}
        assert names1 != names2
