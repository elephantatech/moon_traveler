"""Tests for Creature state, trust, and serialization."""

from src.creatures import Creature


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
