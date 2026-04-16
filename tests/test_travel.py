"""Tests for travel mechanics: time calculation, resource costs, and route suggestions."""

from src.drone import Drone
from src.player import Player
from src.travel import calculate_travel_time, _find_closer_alternative
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
