"""Tests for Creature state, trust, and serialization."""

from src.creatures import GUARANTEED_ARCHETYPES, ROLE_CAPABILITIES, Creature


def _make_creature(**overrides) -> Creature:
    defaults = dict(
        id="creature_0",
        name="Kael",
        species="Crystallith",
        archetype="Wise Elder",
        disposition="friendly",
        location_name="Frost Ridge",
        trust=25,
    )
    defaults.update(overrides)
    return Creature(**defaults)


class TestTrustLevel:
    def test_low(self):
        c = _make_creature(trust=0)
        assert c.trust_level == "low"
        c.trust = 34
        assert c.trust_level == "low"

    def test_medium(self):
        c = _make_creature(trust=35)
        assert c.trust_level == "medium"
        c.trust = 69
        assert c.trust_level == "medium"

    def test_high(self):
        c = _make_creature(trust=70)
        assert c.trust_level == "high"
        c.trust = 100
        assert c.trust_level == "high"


class TestAddTrust:
    def test_add_trust(self):
        c = _make_creature(trust=50)
        c.add_trust(10)
        assert c.trust == 60

    def test_trust_caps_at_100(self):
        c = _make_creature(trust=95)
        c.add_trust(20)
        assert c.trust == 100

    def test_trust_floors_at_0(self):
        c = _make_creature(trust=5)
        c.add_trust(-10)
        assert c.trust == 0


class TestConversationHistory:
    def test_add_message(self):
        c = _make_creature()
        c.add_message("user", "Hello")
        assert len(c.conversation_history) == 1
        assert c.conversation_history[0] == {"role": "user", "content": "Hello"}

    def test_history_trimmed_at_20(self):
        c = _make_creature()
        for i in range(25):
            c.add_message("user", f"msg {i}")
        assert len(c.conversation_history) == 20
        assert c.conversation_history[0]["content"] == "msg 5"


class TestSerialization:
    def test_round_trip(self):
        c = _make_creature(
            trust=55,
            can_give_materials=["ice_crystal", "bio_gel"],
            knows_food_source="Frost Forest",
            following=True,
            home_location="Frost Ridge",
        )
        c.add_message("user", "Hello")
        d = c.to_dict()
        c2 = Creature.from_dict(d)
        assert c2.name == "Kael"
        assert c2.trust == 55
        assert c2.can_give_materials == ["ice_crystal", "bio_gel"]
        assert c2.knows_food_source == "Frost Forest"
        assert c2.following is True
        assert c2.home_location == "Frost Ridge"
        assert len(c2.conversation_history) == 1

    def test_from_dict_strips_chased_away(self):
        d = _make_creature().to_dict()
        d["chased_away"] = True
        c = Creature.from_dict(d)
        assert not hasattr(c, "chased_away") or c.following is False

    def test_from_dict_backwards_compat_no_following(self):
        d = _make_creature().to_dict()
        del d["following"]
        del d["home_location"]
        c = Creature.from_dict(d)
        assert c.following is False
        assert c.home_location is None

    def test_round_trip_new_fields(self):
        c = _make_creature(
            role_inventory=["circuit_board", "antenna_array"],
            given_items=["circuit_board"],
            backstory="A test backstory.",
            trade_wants=["ice_crystal"],
        )
        d = c.to_dict()
        c2 = Creature.from_dict(d)
        assert c2.role_inventory == ["circuit_board", "antenna_array"]
        assert c2.given_items == ["circuit_board"]
        assert c2.backstory == "A test backstory."
        assert c2.trade_wants == ["ice_crystal"]

    def test_from_dict_backwards_compat_no_role_inventory(self):
        """Old saves without role_inventory should map can_give_materials."""
        d = _make_creature(can_give_materials=["bio_gel", "metal_shard"]).to_dict()
        del d["role_inventory"]
        del d["given_items"]
        del d["backstory"]
        del d["trade_wants"]
        c = Creature.from_dict(d)
        assert c.role_inventory == ["bio_gel", "metal_shard"]
        assert c.given_items == []
        assert c.backstory == ""
        assert c.trade_wants == []


class TestTrustMeets:
    def test_healer_heals_at_zero_trust(self):
        c = _make_creature(archetype="Healer", trust=0)
        assert c.trust_meets("heal") is True
        assert c.trust_meets("repair_suit") is True

    def test_healer_needs_trust_for_food(self):
        c = _make_creature(archetype="Healer", trust=5)
        assert c.trust_meets("food") is False
        c.trust = 10
        assert c.trust_meets("food") is True

    def test_guardian_high_threshold_for_materials(self):
        c = _make_creature(archetype="Guardian", trust=50)
        assert c.trust_meets("materials") is False
        c.trust = 70
        assert c.trust_meets("materials") is True

    def test_hermit_very_high_threshold(self):
        c = _make_creature(archetype="Hermit", trust=79)
        assert c.trust_meets("materials") is False
        c.trust = 80
        assert c.trust_meets("materials") is True

    def test_merchant_trade_threshold(self):
        c = _make_creature(archetype="Merchant", trust=19)
        assert c.trust_meets("trade") is False
        c.trust = 20
        assert c.trust_meets("trade") is True


class TestRoleCapabilities:
    def test_all_archetypes_have_capabilities(self):
        from src.data.names import PERSONALITY_ARCHETYPES
        for archetype in PERSONALITY_ARCHETYPES:
            assert archetype in ROLE_CAPABILITIES, f"Missing ROLE_CAPABILITIES for {archetype}"

    def test_guaranteed_archetypes_defined(self):
        for arch in GUARANTEED_ARCHETYPES:
            assert arch in ROLE_CAPABILITIES


class TestGenerateCreatures:
    def test_guaranteed_spawns(self):
        import random

        from src.creatures import generate_creatures
        from src.world import generate_world
        world = generate_world("short", seed=42)
        rng = random.Random(42)
        creatures = generate_creatures(world, rng, required_materials=["ice_crystal", "metal_shard", "bio_gel"])
        archetypes = [c.archetype for c in creatures]
        for req in GUARANTEED_ARCHETYPES:
            assert req in archetypes, f"Missing guaranteed archetype: {req}"

    def test_guaranteed_archetypes_not_hostile(self):
        import random

        from src.creatures import generate_creatures
        from src.world import generate_world
        world = generate_world("medium", seed=99)
        rng = random.Random(99)
        creatures = generate_creatures(world, rng, required_materials=["ice_crystal", "metal_shard", "bio_gel"])
        for c in creatures:
            if c.archetype in GUARANTEED_ARCHETYPES:
                assert c.disposition != "hostile", f"{c.archetype} should not be hostile"

    def test_material_coverage(self):
        import random

        from src.creatures import generate_creatures
        from src.world import generate_world
        required = ["ice_crystal", "metal_shard", "bio_gel", "circuit_board", "power_cell"]
        world = generate_world("medium", seed=77)
        rng = random.Random(77)
        creatures = generate_creatures(world, rng, required_materials=required)
        covered = set()
        for c in creatures:
            covered.update(c.role_inventory)
        for mat in required:
            assert mat in covered, f"Missing material coverage: {mat}"
