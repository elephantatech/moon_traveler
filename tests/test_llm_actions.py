"""Tests for LLM action tag parsing and application."""

from src.creatures import Creature
from src.drone import Drone
from src.llm import apply_actions, parse_actions
from src.player import Player


def _make_creature(**overrides) -> Creature:
    defaults = dict(
        id="creature_0",
        name="Kael",
        species="Crystallith",
        archetype="Healer",
        disposition="friendly",
        location_name="Frost Ridge",
        trust=50,
        can_give_materials=["ice_crystal", "bio_gel"],
    )
    defaults.update(overrides)
    return Creature(**defaults)


class TestParseActions:
    def test_give_water(self):
        text, actions = parse_actions("Here, drink this. [GIVE_WATER]")
        assert text == "Here, drink this."
        assert actions == [{"action": "GIVE_WATER"}]

    def test_give_food(self):
        text, actions = parse_actions("Eat this. [GIVE_FOOD]")
        assert text == "Eat this."
        assert actions == [{"action": "GIVE_FOOD"}]

    def test_heal(self):
        text, actions = parse_actions("Let me tend to you. [HEAL]")
        assert text == "Let me tend to you."
        assert actions == [{"action": "HEAL"}]

    def test_repair_suit(self):
        text, actions = parse_actions("Your covering is damaged. [REPAIR_SUIT]")
        assert text == "Your covering is damaged."
        assert actions == [{"action": "REPAIR_SUIT"}]

    def test_give_material(self):
        text, actions = parse_actions("Take this crystal. [GIVE_MATERIAL:ice_crystal]")
        assert text == "Take this crystal."
        assert actions == [{"action": "GIVE_MATERIAL", "item": "ice_crystal"}]

    def test_give_material_case_insensitive(self):
        _, actions = parse_actions("[GIVE_MATERIAL:Ice_Crystal]")
        assert actions[0]["item"] == "ice_crystal"

    def test_no_actions(self):
        text, actions = parse_actions("I do not trust you yet.")
        assert text == "I do not trust you yet."
        assert actions == []

    def test_mid_sentence_tag_collapses_spaces(self):
        text, _ = parse_actions("Here, take this [GIVE_WATER] to help you.")
        assert "  " not in text
        assert text == "Here, take this to help you."

    def test_multiple_tags_only_first_matters(self):
        _, actions = parse_actions("Take both. [GIVE_WATER] [GIVE_FOOD]")
        assert len(actions) == 2
        assert actions[0]["action"] == "GIVE_WATER"
        assert actions[1]["action"] == "GIVE_FOOD"

    def test_case_insensitive_action(self):
        _, actions = parse_actions("[give_water]")
        assert actions[0]["action"] == "GIVE_WATER"


class TestApplyActions:
    def test_give_water(self):
        p = Player(water=50.0)
        c = _make_creature(trust=50)
        msgs = apply_actions([{"action": "GIVE_WATER"}], p, Drone(), c, {})
        assert p.water == 100.0
        assert len(msgs) == 1
        assert "Water fully restored" in msgs[0]

    def test_give_food(self):
        p = Player(food=30.0)
        c = _make_creature(trust=50)
        apply_actions([{"action": "GIVE_FOOD"}], p, Drone(), c, {})
        assert p.food == 100.0

    def test_heal(self):
        p = Player(food=50.0, water=40.0)
        c = _make_creature(trust=50)
        apply_actions([{"action": "HEAL"}], p, Drone(), c, {})
        assert p.food == 80.0
        assert p.water == 70.0

    def test_heal_caps_at_100(self):
        p = Player(food=90.0, water=85.0)
        c = _make_creature(trust=50)
        apply_actions([{"action": "HEAL"}], p, Drone(), c, {})
        assert p.food == 100.0
        assert p.water == 100.0

    def test_repair_suit(self):
        p = Player(suit_integrity=60.0)
        c = _make_creature(trust=50)
        msgs = apply_actions([{"action": "REPAIR_SUIT"}], p, Drone(), c, {})
        assert p.suit_integrity == 85.0  # 60 + 25
        assert len(msgs) == 1

    def test_repair_suit_caps_at_100(self):
        p = Player(suit_integrity=90.0)
        c = _make_creature(trust=50)
        apply_actions([{"action": "REPAIR_SUIT"}], p, Drone(), c, {})
        assert p.suit_integrity == 100.0

    def test_repair_suit_does_nothing_at_100(self):
        p = Player(suit_integrity=100.0)
        c = _make_creature(trust=50)
        msgs = apply_actions([{"action": "REPAIR_SUIT"}], p, Drone(), c, {})
        assert len(msgs) == 0

    def test_give_material_legacy_path(self):
        """Legacy path: role_inventory empty, falls back to can_give_materials."""
        p = Player()
        c = _make_creature(trust=50, can_give_materials=["ice_crystal", "bio_gel"])
        msgs = apply_actions([{"action": "GIVE_MATERIAL", "item": "ice_crystal"}], p, Drone(), c, {})
        assert p.has_item("ice_crystal")
        assert "ice_crystal" not in c.can_give_materials
        assert len(msgs) == 1

    def test_give_material_role_inventory_path(self):
        """Primary path: role_inventory populated, used instead of can_give_materials."""
        p = Player()
        c = _make_creature(
            trust=50, archetype="Builder",
            role_inventory=["metal_shard", "hull_patch"],
            can_give_materials=["metal_shard", "hull_patch"],
        )
        msgs = apply_actions([{"action": "GIVE_MATERIAL", "item": "metal_shard"}], p, Drone(), c, {})
        assert p.has_item("metal_shard")
        assert "metal_shard" not in c.role_inventory
        assert "metal_shard" not in c.can_give_materials  # synced
        assert "metal_shard" in c.given_items
        assert len(msgs) == 1

    def test_give_material_unknown_item_ignored(self):
        p = Player()
        c = _make_creature(trust=50, can_give_materials=["bio_gel"])
        msgs = apply_actions([{"action": "GIVE_MATERIAL", "item": "power_cell"}], p, Drone(), c, {})
        assert not p.has_item("power_cell")
        assert len(msgs) == 0

    def test_trust_guard_blocks_low_trust(self):
        p = Player(water=50.0)
        # Guardian has water threshold of 35 (default), so trust=10 blocks
        c = _make_creature(trust=10, archetype="Guardian")
        msgs = apply_actions([{"action": "GIVE_WATER"}], p, Drone(), c, {})
        assert p.water == 50.0  # unchanged
        assert len(msgs) == 0

    def test_healer_can_give_water_at_low_trust(self):
        """Healers have trust threshold 10 for water — it's their calling."""
        p = Player(water=50.0)
        c = _make_creature(trust=10, archetype="Healer")
        msgs = apply_actions([{"action": "GIVE_WATER"}], p, Drone(), c, {})
        assert p.water == 100.0
        assert len(msgs) == 1

    def test_medium_trust_allows_actions(self):
        p = Player(water=50.0)
        c = _make_creature(trust=40)  # medium — meets default threshold 35
        apply_actions([{"action": "GIVE_WATER"}], p, Drone(), c, {})
        assert p.water == 100.0

    def test_guardian_blocks_materials_below_70(self):
        p = Player()
        c = _make_creature(trust=60, archetype="Guardian", role_inventory=["power_cell"])
        msgs = apply_actions([{"action": "GIVE_MATERIAL", "item": "power_cell"}], p, Drone(), c, {})
        assert not p.has_item("power_cell")
        assert len(msgs) == 0

    def test_guardian_allows_materials_at_70(self):
        p = Player()
        c = _make_creature(trust=70, archetype="Guardian", role_inventory=["power_cell"])
        msgs = apply_actions([{"action": "GIVE_MATERIAL", "item": "power_cell"}], p, Drone(), c, {})
        assert p.has_item("power_cell")
        assert len(msgs) == 1

    def test_give_material_tracks_given_items(self):
        p = Player()
        c = _make_creature(trust=50, archetype="Builder", role_inventory=["metal_shard"])
        apply_actions([{"action": "GIVE_MATERIAL", "item": "metal_shard"}], p, Drone(), c, {})
        assert "metal_shard" in c.given_items
        assert "metal_shard" not in c.role_inventory


class TestTradeActions:
    def test_parse_trade_tag(self):
        _, actions = parse_actions("Let us trade. [TRADE:circuit_board:ice_crystal]")
        assert len(actions) == 1
        assert actions[0]["action"] == "TRADE"
        assert actions[0]["offered"] == "circuit_board"
        assert actions[0]["wanted"] == "ice_crystal"

    def test_trade_applies(self):
        p = Player()
        p.add_item("ice_crystal")
        c = _make_creature(trust=25, archetype="Merchant", role_inventory=["circuit_board"])
        msgs = apply_actions(
            [{"action": "TRADE", "offered": "circuit_board", "wanted": "ice_crystal"}],
            p, Drone(), c, {},
        )
        assert p.has_item("circuit_board")
        assert not p.has_item("ice_crystal")
        assert "circuit_board" not in c.role_inventory
        assert len(msgs) == 1

    def test_trade_blocked_below_trust(self):
        p = Player()
        p.add_item("ice_crystal")
        c = _make_creature(trust=15, archetype="Merchant", role_inventory=["circuit_board"])
        msgs = apply_actions(
            [{"action": "TRADE", "offered": "circuit_board", "wanted": "ice_crystal"}],
            p, Drone(), c, {},
        )
        assert not p.has_item("circuit_board")
        assert p.has_item("ice_crystal")
        assert len(msgs) == 0
