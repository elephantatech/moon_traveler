"""Tests for the input_handler module."""

from unittest.mock import MagicMock

from prompt_toolkit.document import Document

from src.input_handler import BASE_COMMANDS, GameCompleter


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


def get_completions(completer, text):
    """Helper to get completion text list from a document."""
    doc = Document(text, len(text))
    return [c.text for c in completer.get_completions(doc, MagicMock())]


class TestCommandCompletion:
    def test_empty_returns_all_commands(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "")
        assert len(results) == len(BASE_COMMANDS)

    def test_partial_command(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "tra")
        assert "travel" in results

    def test_scan_completes(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "sc")
        assert "scan" in results


class TestTravelCompletion:
    def test_travel_shows_known_locations(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "travel ")
        assert "Crystal Ridge" in results
        assert "Crash Site" in results

    def test_travel_partial_match(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "travel Cry")
        assert "Crystal Ridge" in results
        assert "Frost Canyon" not in results


class TestTalkCompletion:
    def test_talk_shows_creature_at_location(self):
        ctx = FakeCtx()
        ctx.player.location_name = "Crystal Ridge"
        completer = GameCompleter(ctx)
        results = get_completions(completer, "talk ")
        assert "Kael" in results

    def test_talk_no_creature_at_location(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "talk ")
        assert results == []


class TestTakeCompletion:
    def test_take_shows_items_at_location(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "take ")
        assert "Bio Gel" in results


class TestGiveCompletion:
    def test_give_shows_inventory(self):
        ctx = FakeCtx()
        completer = GameCompleter(ctx)
        results = get_completions(completer, "give ")
        assert "Ice Crystal" in results
        assert "Metal Shard" in results

    def test_give_after_to_shows_creature(self):
        ctx = FakeCtx()
        ctx.player.location_name = "Crystal Ridge"
        completer = GameCompleter(ctx)
        results = get_completions(completer, "give Ice Crystal to ")
        assert "Kael" in results
