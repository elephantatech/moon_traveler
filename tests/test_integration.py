"""Integration tests — full gameplay flows with MockBridge.

These tests run the actual game logic (dispatch, commands, save/load)
with a mock UI bridge that provides scripted responses. No TUI, no
async, no timing dependencies.
"""

import os
import tempfile

import pytest

from src import ui
from src.commands import dispatch
from src.game import REPAIR_MATERIALS, apply_super_mode, check_win, init_game

# Features from PR #46 (escort + leaderboard) — skip until merged
try:
    from src.game import ESCORT_REQUIREMENTS  # noqa: F401

    _HAS_ESCORT = True
except ImportError:
    _HAS_ESCORT = False

try:
    from src.save_load import get_top_scores, record_score  # noqa: F401

    _HAS_LEADERBOARD = True
except ImportError:
    _HAS_LEADERBOARD = False


class MockBridge:
    """Minimal UIBridge mock for headless integration testing."""

    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self._response_idx = 0
        self._output: list = []
        self._app = self

    def call_from_thread(self, fn, *args):
        fn(*args)

    def print(self, *args, **kwargs):
        for a in args:
            self._output.append(str(a))

    def input(self, prompt=""):
        if self._response_idx < len(self._responses):
            resp = self._responses[self._response_idx]
            self._response_idx += 1
            return resp
        return ""

    def get_command(self, location):
        return self.input()

    def update_status_bar(self, markup):
        pass

    def update_header(self, text):
        pass

    def clear(self):
        self._output.clear()

    def push_response(self, text):
        pass

    def set_suggester(self, ctx):
        pass

    def enter_ask_mode(self, prompt):
        pass

    def exit_ask_mode(self):
        pass

    @property
    def output_text(self):
        return "\n".join(str(o) for o in self._output)


def _setup(responses=None):
    """Install MockBridge and return it."""
    bridge = MockBridge(responses)
    ui._bridge = bridge
    ui.console = ui._BridgeConsoleShim()
    return bridge


def _teardown():
    """Restore default console."""
    from rich.console import Console

    ui._bridge = None
    ui.console = Console()


class TestDispatchIntegration:
    def test_look_command(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            dispatch(ctx, "look")
            assert ctx.player.location_name == "Crash Site"
            assert ctx.stats.commands == 1
        finally:
            _teardown()

    def test_scan_discovers_locations(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            initial = len(ctx.player.known_locations)
            dispatch(ctx, "scan")
            assert len(ctx.player.known_locations) > initial
        finally:
            _teardown()

    def test_help_command(self):
        bridge = _setup()
        try:
            ctx = init_game("short", seed=42)
            dispatch(ctx, "help")
            assert "drone" in bridge.output_text.lower()
        finally:
            _teardown()

    def test_status_command(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            dispatch(ctx, "status")
            assert ctx.stats.commands == 1
        finally:
            _teardown()

    def test_stats_command(self):
        bridge = _setup()
        try:
            ctx = init_game("short", seed=42)
            ctx.stats.commands = 10
            dispatch(ctx, "stats")
            assert "10" in bridge.output_text
        finally:
            _teardown()

    def test_inventory_empty(self):
        bridge = _setup()
        try:
            ctx = init_game("short", seed=42)
            dispatch(ctx, "inventory")
            assert "empty" in bridge.output_text.lower()
        finally:
            _teardown()

    def test_unknown_command(self):
        bridge = _setup()
        try:
            ctx = init_game("short", seed=42)
            dispatch(ctx, "asdfgh")
            assert "unknown" in bridge.output_text.lower()
            assert ctx.stats.commands == 0  # invalid commands not counted
        finally:
            _teardown()


class TestSuperModeIntegration:
    def test_super_mode_has_all_materials(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            apply_super_mode(ctx)
            for mat in REPAIR_MATERIALS["short"]:
                assert ctx.player.has_item(mat), f"Missing: {mat}"
        finally:
            _teardown()

    def test_super_mode_max_trust(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            apply_super_mode(ctx)
            for c in ctx.creatures:
                assert c.trust == 100
        finally:
            _teardown()

    def test_super_mode_full_resources(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            apply_super_mode(ctx)
            assert ctx.player.food == 100.0
            assert ctx.player.water == 100.0
            assert ctx.player.suit_integrity == 100.0
        finally:
            _teardown()


@pytest.mark.skipif(not _HAS_ESCORT, reason="Escort features not merged (PR #46)")
class TestEscortIntegration:
    def test_repair_installs_with_escort(self):
        _setup(["y"])
        try:
            ctx = init_game("short", seed=42)
            apply_super_mode(ctx)
            ctx.escorts_completed = 1
            from src.commands import _bay_repair

            _bay_repair(ctx)
            assert check_win(ctx)
        finally:
            _teardown()

    def test_repair_blocked_without_escort(self):
        bridge = _setup()
        try:
            ctx = init_game("short", seed=42)
            apply_super_mode(ctx)
            ctx.escorts_completed = 0
            from src.commands import _bay_repair

            _bay_repair(ctx)
            assert not check_win(ctx)
            assert "escort" in bridge.output_text.lower()
        finally:
            _teardown()


class TestSaveLoadIntegration:
    def test_save_load_round_trip(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            apply_super_mode(ctx)

            with tempfile.TemporaryDirectory() as tmpdir:
                os.environ["MOON_TRAVELER_SAVE_DIR"] = tmpdir
                try:
                    from src.save_load import load_game, save_game

                    save_game(
                        "test",
                        ctx.player,
                        ctx.drone,
                        ctx.locations,
                        ctx.creatures,
                        ctx.world_seed,
                        ctx.world_mode,
                        ctx.repair_checklist,
                        ctx.ship_ai,
                        ctx.tutorial,
                    )
                    state = load_game("test")
                    assert state is not None
                    assert state["world_seed"] == ctx.world_seed
                    assert state["player"].food == ctx.player.food
                finally:
                    os.environ.pop("MOON_TRAVELER_SAVE_DIR", None)
        finally:
            _teardown()


@pytest.mark.skipif(not _HAS_LEADERBOARD, reason="Leaderboard not merged (PR #46)")
class TestLeaderboardIntegration:
    def test_record_and_retrieve(self):
        from src.save_load import get_top_scores, record_score

        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["MOON_TRAVELER_SAVE_DIR"] = tmpdir
            try:
                record_score(750, "A", True, "short", 15, 900, 3, 42)
                scores = get_top_scores(10)
                assert any(s["score"] == 750 for s in scores)
            finally:
                os.environ.pop("MOON_TRAVELER_SAVE_DIR", None)


class TestGiveIntegration:
    def test_give_increases_trust(self):
        _setup()
        try:
            ctx = init_game("short", seed=42)
            creature = ctx.creatures[0]
            creature.location_name = ctx.player.location_name
            creature.disposition = "friendly"
            ctx.player.add_item("ice_crystal")
            initial_trust = creature.trust

            dispatch(ctx, f"give Ice Crystal to {creature.name}")
            assert creature.trust > initial_trust
            assert ctx.stats.gifts_given == 1
        finally:
            _teardown()


class TestTravelIntegration:
    def test_travel_tracks_distance(self):
        _setup(["y"])
        try:
            ctx = init_game("short", seed=42)
            dispatch(ctx, "scan")

            destinations = [loc for loc in ctx.locations if loc.name != "Crash Site" and loc.discovered]
            if destinations:
                dest = destinations[0]
                dispatch(ctx, f"travel {dest.name}")
                assert ctx.stats.km_traveled > 0
                assert ctx.player.location_name == dest.name
        finally:
            _teardown()

    def test_travel_drains_resources(self):
        _setup(["y"])
        try:
            ctx = init_game("short", seed=42)
            dispatch(ctx, "scan")
            initial_food = ctx.player.food

            destinations = [loc for loc in ctx.locations if loc.name != "Crash Site" and loc.discovered]
            if destinations:
                dispatch(ctx, f"travel {destinations[0].name}")
                assert ctx.player.food < initial_food
        finally:
            _teardown()
