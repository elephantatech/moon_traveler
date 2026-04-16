"""Procedural world generation for Enceladus."""

import math
import random
from dataclasses import dataclass, field

from src.data.names import generate_location_name


@dataclass
class Location:
    name: str
    loc_type: str
    x: float
    y: float
    items: list[str] = field(default_factory=list)
    creature_id: str | None = None
    discovered: bool = False
    visited: bool = False
    description: str = ""
    food_source: bool = False
    water_source: bool = False

    def distance_to(self, other_x: float, other_y: float) -> float:
        return math.sqrt((self.x - other_x) ** 2 + (self.y - other_y) ** 2)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "loc_type": self.loc_type,
            "x": self.x,
            "y": self.y,
            "items": list(self.items),
            "creature_id": self.creature_id,
            "discovered": self.discovered,
            "visited": self.visited,
            "description": self.description,
            "food_source": self.food_source,
            "water_source": self.water_source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Location":
        return cls(**d)


LOCATION_DESCRIPTIONS = {
    "crash_site": [
        "Your ship lies crumpled in a shallow crater, venting steam into the thin atmosphere. Debris is scattered across the ice.",
        "The impact crater is still warm. Your ship's hull is cracked but the cabin held. Emergency lights flicker weakly.",
    ],
    "plains": [
        "A vast expanse of smooth ice stretches in every direction. The surface shimmers under Saturn's pale light.",
        "Flat terrain covered in fine ice crystals. Wind-carved ridges pattern the ground like frozen waves.",
        "Open ice fields with excellent visibility. Distant geysers send plumes skyward on the horizon.",
    ],
    "ridge": [
        "A jagged ice ridge rises sharply, its surface lined with deep blue crystal formations.",
        "Towering walls of compacted ice and rock. Ancient fracture lines run through the formation.",
        "A high vantage point overlooking the surrounding terrain. The ice here is old and hard.",
    ],
    "cave": [
        "A dark opening in the ice wall leads to a cavern glittering with mineral deposits.",
        "Underground chambers carved by ancient water flows. Strange bioluminescent patches dot the walls.",
        "A deep cave system with surprisingly warm air. Mineral crystals grow in elaborate formations.",
    ],
    "geyser_field": [
        "Steam jets erupt unpredictably from cracks in the ice. The air is warm and humid here.",
        "A field of active geysers. The timing is almost rhythmic — you could navigate between eruptions.",
        "Hot vapor rises from dozens of vents. The ice here is thin and treacherous.",
    ],
    "ice_lake": [
        "A perfectly smooth frozen lake reflects Saturn above like a mirror. The ice is thick and safe.",
        "A vast frozen reservoir. Beneath the clear ice, you can see dark water moving slowly.",
        "Crystal-clear ice covers a deep lake. Strange shapes are frozen beneath the surface.",
    ],
    "ruins": [
        "Crumbling structures of unknown origin protrude from the ice. They are clearly artificial.",
        "Ancient foundations and collapsed walls, half-buried in ice. Something lived here, long ago.",
        "Remnants of technology too old to identify. Some pieces still hum with faint energy.",
    ],
    "forest": [
        "Tall crystalline spires rise like alien trees, refracting light into rainbow patterns.",
        "A dense grove of ice pillars, some reaching 20 meters high. Life clings to their surfaces.",
        "Towering mineral columns create a maze-like environment. Small creatures skitter between them.",
    ],
    "canyon": [
        "A deep rift in the ice, its walls striped with layers of ancient geological activity.",
        "A narrow canyon with walls so high they block most of the sky. Echoes carry far here.",
        "A winding gorge carved by subsurface water. The walls glitter with exposed minerals.",
    ],
    "settlement": [
        "A cluster of dome-shaped structures made from ice and local minerals. Someone lives here.",
        "A small outpost built into a sheltered alcove. Warm light glows from within.",
        "An organized camp with storage structures and a central gathering area. Well-maintained.",
    ],
}

# Items that can be found at locations
LOCATION_ITEMS = {
    "plains": ["ice_crystal", "metal_shard"],
    "ridge": ["metal_shard", "antenna_array"],
    "cave": ["bio_gel", "power_cell", "ice_crystal"],
    "geyser_field": ["thermal_paste", "bio_gel"],
    "ice_lake": ["ice_crystal", "circuit_board"],
    "ruins": ["circuit_board", "power_cell", "hull_patch"],
    "forest": ["bio_gel", "ice_crystal"],
    "canyon": ["metal_shard", "hull_patch", "thermal_paste"],
    "settlement": ["circuit_board", "antenna_array"],
    "crash_site": [],
}

# Drone upgrade components found at specific location types
DRONE_UPGRADES = {
    "ruins": ["range_module", "translator_chip"],
    "settlement": ["cargo_rack", "translator_chip"],
    "cave": ["battery_cell"],
    "ridge": ["thruster_pack"],
    "canyon": ["range_module"],
}

MODE_CONFIG = {
    "short": {"locations": 8, "creatures": 5, "radius": 20, "hostile_count": 0},
    "medium": {"locations": 16, "creatures": 12, "radius": 40, "hostile_count": 4},
    "long": {"locations": 30, "creatures": 20, "radius": 60, "hostile_count": 6},
}

# Location type distribution weights
TYPE_WEIGHTS = {
    "plains": 3,
    "ridge": 2,
    "cave": 2,
    "geyser_field": 2,
    "ice_lake": 1,
    "ruins": 2,
    "forest": 2,
    "canyon": 2,
    "settlement": 1,
}


def _weighted_type_pool() -> list[str]:
    pool = []
    for t, w in TYPE_WEIGHTS.items():
        pool.extend([t] * w)
    return pool


def generate_world(mode: str, seed: int | None = None) -> dict:
    """Generate a complete world. Returns dict with locations list."""
    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)
    config = MODE_CONFIG[mode]
    radius = config["radius"]
    num_locations = config["locations"]

    used_names = set()
    locations = []

    # Crash site always at origin
    crash = Location(
        name="Crash Site",
        loc_type="crash_site",
        x=0.0,
        y=0.0,
        discovered=True,
        visited=True,
        description=rng.choice(LOCATION_DESCRIPTIONS["crash_site"]),
    )
    locations.append(crash)

    type_pool = _weighted_type_pool()

    # Generate remaining locations with minimum spacing
    min_spacing = radius * 0.15
    attempts = 0
    while len(locations) < num_locations and attempts < 500:
        attempts += 1
        loc_type = rng.choice(type_pool)
        x = rng.uniform(-radius, radius)
        y = rng.uniform(-radius, radius)

        # Ensure minimum distance from all existing locations
        too_close = False
        for existing in locations:
            if existing.distance_to(x, y) < min_spacing:
                too_close = True
                break
        if too_close:
            continue

        # Ensure not too far from at least one existing location
        nearest = min(loc.distance_to(x, y) for loc in locations)
        if nearest > radius * 0.6:
            continue

        name = generate_location_name(loc_type, rng)
        while name in used_names:
            name = generate_location_name(loc_type, rng)
        used_names.add(name)

        # Assign items
        possible_items = LOCATION_ITEMS.get(loc_type, [])
        item_count = rng.randint(0, min(2, len(possible_items)))
        items = rng.sample(possible_items, item_count) if possible_items else []

        # Possible drone upgrade
        possible_upgrades = DRONE_UPGRADES.get(loc_type, [])
        if possible_upgrades and rng.random() < 0.4:
            items.append(rng.choice(possible_upgrades))

        # Food/water sources (some locations have renewable resources)
        food_source = loc_type in ("forest", "cave") and rng.random() < 0.5
        water_source = loc_type in ("ice_lake", "geyser_field") and rng.random() < 0.5

        desc = rng.choice(LOCATION_DESCRIPTIONS.get(loc_type, ["A mysterious place."]))

        loc = Location(
            name=name,
            loc_type=loc_type,
            x=round(x, 1),
            y=round(y, 1),
            items=items,
            description=desc,
            food_source=food_source,
            water_source=water_source,
        )
        locations.append(loc)

    return {
        "seed": seed,
        "mode": mode,
        "locations": locations,
        "config": config,
    }
