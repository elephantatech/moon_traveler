"""Tests for travel mechanics: time calculation, resource costs, and route suggestions."""

import random

from src.drone import Drone
from src.player import Player
from src.travel import (
    HAZARD_EVENTS,
    LATE_GAME_THRESHOLDS,
    _find_closer_alternative,
    calculate_travel_time,
    execute_travel,
)
from src.world import Location


class TestTravelTime:
    def test_basic_speed(self):
        d = Drone()
        hours = calculate_travel_time(10.0, d)
        assert hours == 1.0  # 10km / 10km/h

    def test_with_speed_boost(self):
        d = Drone()
        d.speed_boost = 5
        hours = calculate_travel_time(15.0, d)
        assert hours == 1.0  # 15km / 15km/h

    def test_short_distance(self):
        d = Drone()
        hours = calculate_travel_time(2.0, d)
        assert hours == 0.2  # 2km / 10km/h


class TestFindCloserAlternative:
    def test_finds_closer_waypoint(self):
        dest = Location(name="Far Away", loc_type="plains", x=20, y=0, discovered=True)
        mid = Location(name="Midpoint", loc_type="ridge", x=15, y=0, discovered=True)
        crash = Location(name="Crash Site", loc_type="crash_site", x=0, y=0, discovered=True)
        locations = [crash, mid, dest]

        result = _find_closer_alternative(locations, dest)
        assert result == "Midpoint"

    def test_ignores_destination(self):
        dest = Location(name="Target", loc_type="plains", x=10, y=0, discovered=True)
        locations = [dest]
        result = _find_closer_alternative(locations, dest)
        assert result is None

    def test_ignores_undiscovered(self):
        dest = Location(name="Target", loc_type="plains", x=10, y=0, discovered=True)
        hidden = Location(name="Hidden", loc_type="cave", x=8, y=0, discovered=False)
        locations = [dest, hidden]
        result = _find_closer_alternative(locations, dest)
        assert result is None

    def test_ignores_current_location(self):
        dest = Location(name="Target", loc_type="plains", x=10, y=0, discovered=True)
        current = Location(name="Here", loc_type="ridge", x=8, y=0, discovered=True)
        locations = [dest, current]
        result = _find_closer_alternative(locations, dest, current=current)
        assert result is None

    def test_returns_none_if_too_far(self):
        dest = Location(name="Target", loc_type="plains", x=10, y=0, discovered=True)
        far = Location(name="TooFar", loc_type="cave", x=30, y=0, discovered=True)
        locations = [dest, far]
        result = _find_closer_alternative(locations, dest)
        assert result is None


class TestHazardEvents:
    def test_hazard_events_defined(self):
        assert len(HAZARD_EVENTS) >= 5
        for h in HAZARD_EVENTS:
            assert "message" in h
            assert "effect" in h
            assert "probability" in h
            assert 0 < h["probability"] < 1

    def test_hazards_can_damage_suit(self):
        """With a rigged RNG that always triggers, suit should take damage."""
        current = Location(name="Here", loc_type="plains", x=0, y=0, discovered=True, visited=True)
        dest = Location(name="There", loc_type="ridge", x=10, y=0, discovered=True)

        # Use a seed that produces low random values (more likely to trigger hazards)
        # Run multiple times to statistically ensure at least one hazard triggers
        damage_occurred = False
        for seed in range(100):
            p = Player(suit_integrity=92.0)
            rng = random.Random(seed)
            execute_travel(p, Drone(), dest, current, rng)  # side effects only
            if p.suit_integrity < 92.0:
                damage_occurred = True
                break
        assert damage_occurred, "At least one seed should trigger suit damage"


class TestLateGameThresholds:
    def test_thresholds_defined(self):
        assert "short" in LATE_GAME_THRESHOLDS
        assert "medium" in LATE_GAME_THRESHOLDS
        assert "long" in LATE_GAME_THRESHOLDS
        assert "brutal" in LATE_GAME_THRESHOLDS

    def test_late_game_threshold_values(self):
        """Late-game thresholds should be reasonable per mode."""
        assert LATE_GAME_THRESHOLDS["brutal"] < LATE_GAME_THRESHOLDS["short"]
        assert LATE_GAME_THRESHOLDS["short"] < LATE_GAME_THRESHOLDS["medium"]
        assert LATE_GAME_THRESHOLDS["medium"] < LATE_GAME_THRESHOLDS["long"]


class TestBrutalModeDrain:
    def test_brutal_drains_faster(self):
        """Brutal mode should drain food/water 1.5x faster."""
        origin = Location(
            name="A",
            loc_type="plains",
            x=0,
            y=0,
            items=[],
            description="",
            food_source=False,
            water_source=False,
        )
        dest = Location(
            name="B",
            loc_type="plains",
            x=10,
            y=0,
            items=[],
            description="",
            food_source=False,
            water_source=False,
        )
        # Normal mode
        p_normal = Player()
        d_normal = Drone()
        execute_travel(p_normal, d_normal, dest, origin, random.Random(42), game_mode="long")
        # Brutal mode
        p_brutal = Player()
        d_brutal = Drone()
        execute_travel(p_brutal, d_brutal, dest, origin, random.Random(42), game_mode="brutal")
        # Brutal should drain more food and water
        assert p_brutal.food < p_normal.food
        assert p_brutal.water < p_normal.water


class TestAutoCharge:
    def test_auto_charge_recovers_battery(self):
        """Auto-charge should recover battery during travel."""
        origin = Location(
            name="A",
            loc_type="plains",
            x=0,
            y=0,
            items=[],
            description="",
            food_source=False,
            water_source=False,
        )
        dest = Location(
            name="B",
            loc_type="plains",
            x=20,
            y=0,
            items=[],
            description="",
            food_source=False,
            water_source=False,
        )
        d = Drone()
        d.charge_module_installed = True
        d.auto_charge_enabled = True
        d.battery = 50.0
        p = Player()
        execute_travel(p, d, dest, origin, random.Random(42), game_mode="long")
        # Battery should be higher than if no auto-charge (travel costs 10% for 20km)
        # Without auto-charge: 50 - 10 = 40. With auto-charge: 40 + (2h * 5) = 50
        assert d.battery > 40.0

    def test_auto_charge_skipped_at_crash_site(self):
        """Auto-charge message should not fire when arriving at crash site."""
        origin = Location(
            name="A",
            loc_type="plains",
            x=0,
            y=0,
            items=[],
            description="",
            food_source=False,
            water_source=False,
        )
        crash = Location(
            name="Crash Site",
            loc_type="crash_site",
            x=5,
            y=0,
            items=[],
            description="",
            food_source=False,
            water_source=False,
            discovered=True,
            visited=True,
        )
        d = Drone()
        d.charge_module_installed = True
        d.auto_charge_enabled = True
        d.battery = 50.0
        p = Player()
        messages, _, _ = execute_travel(p, d, crash, origin, random.Random(42), game_mode="long")
        # No auto-recharge at crash site — player must use ship charging bay
        msg_text = " ".join(messages)
        assert "Auto-charge" not in msg_text
        assert d.battery < d.battery_max  # Battery NOT auto-recharged
        assert "ship charging" in msg_text  # Tip to recharge manually
