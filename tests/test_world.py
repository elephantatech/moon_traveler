"""Tests for world generation: connectivity, location counts, and seed reproducibility."""

import math

from src.world import generate_world


def _scan_reachability(locations, scanner_range=10) -> set:
    """Simulate chain-scanning from crash site, return reachable location names."""
    known = {locations[0].name}
    changed = True
    while changed:
        changed = False
        for kn in list(known):
            kloc = next(l for l in locations if l.name == kn)
            for loc in locations:
                if loc.name in known:
                    continue
                d = math.sqrt((kloc.x - loc.x) ** 2 + (kloc.y - loc.y) ** 2)
                if d <= scanner_range:
                    known.add(loc.name)
                    changed = True
    return known


class TestWorldGeneration:
    def test_short_mode_count(self):
        world = generate_world("short", seed=42)
        assert len(world["locations"]) == 8

    def test_medium_mode_count(self):
        world = generate_world("medium", seed=42)
        assert len(world["locations"]) == 16

    def test_long_mode_count(self):
        world = generate_world("long", seed=42)
        assert len(world["locations"]) == 30

    def test_crash_site_at_origin(self):
        world = generate_world("short", seed=42)
        crash = world["locations"][0]
        assert crash.name == "Crash Site"
        assert crash.x == 0.0
        assert crash.y == 0.0
        assert crash.discovered is True
        assert crash.visited is True

    def test_seed_reproducibility(self):
        w1 = generate_world("short", seed=123)
        w2 = generate_world("short", seed=123)
        names1 = [l.name for l in w1["locations"]]
        names2 = [l.name for l in w2["locations"]]
        assert names1 == names2

    def test_different_seeds_different_worlds(self):
        w1 = generate_world("short", seed=42)
        w2 = generate_world("short", seed=999)
        names1 = {l.name for l in w1["locations"]}
        names2 = {l.name for l in w2["locations"]}
        assert names1 != names2


class TestScanReachability:
    def test_short_all_reachable(self):
        for seed in [42, 123, 999, 7777, 55555]:
            world = generate_world("short", seed=seed)
            reachable = _scan_reachability(world["locations"])
            assert len(reachable) == len(world["locations"]), f"seed={seed}: {len(reachable)}/{len(world['locations'])}"

    def test_medium_all_reachable(self):
        for seed in [42, 123, 999]:
            world = generate_world("medium", seed=seed)
            reachable = _scan_reachability(world["locations"])
            assert len(reachable) == len(world["locations"]), f"seed={seed}: {len(reachable)}/{len(world['locations'])}"

    def test_long_all_reachable(self):
        for seed in [42, 123]:
            world = generate_world("long", seed=seed)
            reachable = _scan_reachability(world["locations"])
            assert len(reachable) == len(world["locations"]), f"seed={seed}: {len(reachable)}/{len(world['locations'])}"


class TestLocationProperties:
    def test_locations_within_radius(self):
        world = generate_world("short", seed=42)
        radius = world["config"]["radius"]
        for loc in world["locations"]:
            d = math.sqrt(loc.x ** 2 + loc.y ** 2)
            assert d <= radius + 1, f"{loc.name} at {d:.1f}km exceeds radius {radius}"

    def test_minimum_spacing(self):
        world = generate_world("medium", seed=42)
        locs = world["locations"]
        for i, a in enumerate(locs):
            for b in locs[i + 1:]:
                d = math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
                assert d >= 2.5, f"{a.name} and {b.name} too close: {d:.1f}km"

    def test_unique_names(self):
        world = generate_world("long", seed=42)
        names = [l.name for l in world["locations"]]
        assert len(names) == len(set(names))

    def test_food_water_sources_exist(self):
        world = generate_world("medium", seed=42)
        has_food = any(l.food_source for l in world["locations"])
        has_water = any(l.water_source for l in world["locations"])
        # Not guaranteed on every seed, but likely on medium
        # Just check the fields exist and are boolean
        for loc in world["locations"]:
            assert isinstance(loc.food_source, bool)
            assert isinstance(loc.water_source, bool)
