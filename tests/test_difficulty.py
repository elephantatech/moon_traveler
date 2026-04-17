"""Tests for difficulty scaling, junk items, and easter egg."""

from src.difficulty import (
    JUNK_EASTER_EGG_COUNT,
    JUNK_EASTER_EGG_COUNT_BRUTAL,
    JUNK_ITEMS,
    MODE_DIFFICULTY,
    check_junk_easter_egg,
    get_difficulty,
    is_junk_item,
)
from src.player import Player


class TestGetDifficulty:
    def test_short_mode(self):
        d = get_difficulty("short")
        assert d["trust_per_chat"] == 5
        assert d["extra_drops"] == 2

    def test_medium_mode(self):
        d = get_difficulty("medium")
        assert d["trust_per_chat"] == 4

    def test_long_mode(self):
        d = get_difficulty("long")
        assert d["trust_per_chat"] == 3

    def test_brutal_mode(self):
        d = get_difficulty("brutal")
        assert d["trust_per_chat"] == 2
        assert d["food_drain_mult"] == 1.5
        assert d["hazard_bonus"] == 0.05
        assert d["junk_find_chance"] == 0.03

    def test_easy_alias(self):
        d = get_difficulty("easy")
        assert d == get_difficulty("short")

    def test_hard_alias(self):
        d = get_difficulty("hard")
        assert d == get_difficulty("long")

    def test_unknown_falls_back_to_long(self):
        d = get_difficulty("unknown")
        assert d == MODE_DIFFICULTY["long"]

    def test_all_modes_have_required_keys(self):
        required = {"trust_per_chat", "trust_per_gift", "trust_per_gift_hostile", "item_find_chance", "extra_drops"}
        for mode in ("short", "medium", "long", "brutal"):
            d = MODE_DIFFICULTY[mode]
            for key in required:
                assert key in d, f"Missing '{key}' in {mode} difficulty"


class TestJunkItems:
    def test_is_junk_item(self):
        assert is_junk_item("baseball")
        assert is_junk_item("rubber_duck")
        assert not is_junk_item("ice_crystal")
        assert not is_junk_item("metal_shard")

    def test_junk_list_has_10_items(self):
        assert len(JUNK_ITEMS) == 10


class TestEasterEgg:
    def test_not_triggered_with_zero_junk(self):
        p = Player()
        assert not check_junk_easter_egg(p)

    def test_triggered_at_threshold(self):
        p = Player()
        for junk in JUNK_ITEMS[:JUNK_EASTER_EGG_COUNT]:
            p.ship_storage[junk] = 1
        assert check_junk_easter_egg(p)

    def test_not_triggered_below_threshold(self):
        p = Player()
        for junk in JUNK_ITEMS[: JUNK_EASTER_EGG_COUNT - 1]:
            p.ship_storage[junk] = 1
        assert not check_junk_easter_egg(p)

    def test_brutal_needs_more_junk(self):
        p = Player()
        for junk in JUNK_ITEMS[:JUNK_EASTER_EGG_COUNT]:
            p.ship_storage[junk] = 1
        # Normal threshold met
        assert check_junk_easter_egg(p, "short")
        # Brutal threshold NOT met
        assert not check_junk_easter_egg(p, "brutal")

    def test_brutal_threshold_met(self):
        p = Player()
        for junk in JUNK_ITEMS[:JUNK_EASTER_EGG_COUNT_BRUTAL]:
            p.ship_storage[junk] = 1
        assert check_junk_easter_egg(p, "brutal")

    def test_non_junk_in_storage_ignored(self):
        p = Player()
        p.ship_storage["ice_crystal"] = 5
        p.ship_storage["metal_shard"] = 3
        assert not check_junk_easter_egg(p)
