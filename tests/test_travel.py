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
            execute_travel(p, Drone(), dest, current, rng)
            if p.suit_integrity < 92.0:
                damage_occurred = True
                break
        assert damage_occurred, "At least one seed should trigger suit damage"


class TestLateGameThresholds:
    def test_thresholds_defined(self):
        assert "short" in LATE_GAME_THRESHOLDS
        assert "medium" in LATE_GAME_THRESHOLDS
        assert "long" in LATE_GAME_THRESHOLDS

    def test_late_game_threshold_values(self):
        """Late-game thresholds should be reasonable per mode."""
        assert LATE_GAME_THRESHOLDS["short"] < LATE_GAME_THRESHOLDS["medium"]
        assert LATE_GAME_THRESHOLDS["medium"] < LATE_GAME_THRESHOLDS["long"]
