"""Tests for the input_handler module (GameSuggester — TUI autocomplete)."""

from src.input_handler import GameSuggester


class FakeLocation:
    def __init__(self, name="Crash Site", items=None):
        self.name = name
        self.items = items or []


class FakePlayer:
    def __init__(self):
        self.location_name = "Crash Site"
        self.known_locations = {"Crash Site", "Crystal Ridge", "Frost Canyon"}
        self.inventory = {"ice_crystal": 1, "metal_shard": 2}

    def has_item(self, item, qty=1):
        return self.inventory.get(item, 0) >= qty


class FakeDrone:
    pass


class FakeCreature:
    def __init__(self, name="Kael", location="Crash Site", following=False):
        self.name = name
        self.location_name = location
        self.following = following


class FakeCtx:
    def __init__(self):
        self.player = FakePlayer()
        self.drone = FakeDrone()
        self.creatures = [FakeCreature("Kael", "Crystal Ridge")]
        self.locations = [
            FakeLocation("Crash Site", ["bio_gel"]),
            FakeLocation("Crystal Ridge"),
        ]

    def current_location(self):
        for loc in self.locations:
            if loc.name == self.player.location_name:
                return loc
        return self.locations[0]

    def creature_at_location(self, location_name):
        for c in self.creatures:
            if c.location_name == location_name:
                return c
        return None


def get_suggestions(suggester, text):
    """Helper to get all suggestions for a given input."""
    return suggester._get_all_suggestions(text)


class TestCommandCompletion:
    def test_partial_command(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "tra")
        assert any("travel" in r for r in results)

    def test_scan_completes(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "sc")
        assert any("scan" in r for r in results)

    def test_empty_returns_nothing(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "")
        assert results == []


class TestTravelCompletion:
    def test_travel_shows_known_locations(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "travel ")
        names = [r.split(" ", 1)[1] for r in results]
        assert "Crystal Ridge" in names
        assert "Crash Site" in names

    def test_travel_partial_match(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "travel Cry")
        names = [r.split(" ", 1)[1] for r in results]
        assert "Crystal Ridge" in names
        assert "Frost Canyon" not in names


class TestTalkCompletion:
    def test_talk_shows_creature_at_location(self):
        ctx = FakeCtx()
        ctx.player.location_name = "Crystal Ridge"
        s = GameSuggester(ctx)
        results = get_suggestions(s, "talk ")
        names = [r.split(" ", 1)[1] for r in results]
        assert "Kael" in names

    def test_talk_no_creature_at_location(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "talk ")
        assert results == []


class TestTakeCompletion:
    def test_take_shows_items_at_location(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "take ")
        names = [r.split(" ", 1)[1] for r in results]
        assert "Bio Gel" in names


class TestGiveCompletion:
    def test_give_shows_inventory(self):
        ctx = FakeCtx()
        s = GameSuggester(ctx)
        results = get_suggestions(s, "give ")
        names = [r.split(" ", 1)[1] for r in results]
        assert "Ice Crystal" in names
        assert "Metal Shard" in names

    def test_give_after_to_shows_creature(self):
        ctx = FakeCtx()
        ctx.player.location_name = "Crystal Ridge"
        s = GameSuggester(ctx)
        results = get_suggestions(s, "give Ice Crystal to ")
        creature_names = [r.rsplit(" ", 1)[-1] for r in results]
        assert "Kael" in creature_names
