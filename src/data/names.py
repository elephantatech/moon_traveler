"""Name generation pools for locations, creatures, and species."""

import random

LOCATION_PREFIXES = [
    "Frost",
    "Crystal",
    "Shadow",
    "Geyser",
    "Silent",
    "Frozen",
    "Deep",
    "Bright",
    "Hollow",
    "Shattered",
    "Ancient",
    "Pale",
    "Iron",
    "Salt",
    "Ember",
    "Drift",
    "Storm",
    "Vapor",
    "Glass",
    "Obsidian",
    "Lunar",
    "Cobalt",
    "Azure",
    "Ashen",
    "Veiled",
    "Sunken",
    "Titan",
    "Crest",
]

LOCATION_SUFFIXES = {
    "plains": ["Flats", "Expanse", "Plains", "Field", "Reach", "Stretch"],
    "ridge": ["Ridge", "Spine", "Crest", "Bluff", "Escarpment", "Edge"],
    "cave": ["Cavern", "Grotto", "Hollow", "Depths", "Tunnel", "Warren"],
    "geyser_field": ["Vents", "Geysers", "Spouts", "Plumes", "Jets", "Blowhole"],
    "ice_lake": ["Lake", "Pool", "Basin", "Mere", "Reservoir", "Mirror"],
    "ruins": ["Ruins", "Remnants", "Relics", "Foundations", "Wreckage", "Fragments"],
    "forest": ["Spires", "Pillars", "Columns", "Thicket", "Grove", "Stands"],
    "canyon": ["Canyon", "Gorge", "Ravine", "Chasm", "Rift", "Cleft"],
    "settlement": ["Outpost", "Haven", "Camp", "Station", "Shelter", "Depot"],
    "crash_site": ["Crater", "Impact Zone", "Wreck Site"],
}

SPECIES_NAMES = [
    "Crystallith",
    "Vapormaw",
    "Glacien",
    "Thermovore",
    "Silicarn",
    "Cryoform",
    "Lumivex",
    "Echoshell",
    "Driftspore",
    "Plumecrest",
    "Geotherm",
    "Frostweaver",
    "Tidecrawler",
    "Shardwing",
    "Nebulite",
    "Coralith",
    "Voltspine",
    "Mirrorscale",
    "Boilback",
    "Icemantis",
]

CREATURE_NAMES = [
    "Kael",
    "Threnn",
    "Mivari",
    "Ossek",
    "Yuleth",
    "Drenn",
    "Xochi",
    "Pallax",
    "Zirren",
    "Quelth",
    "Bivorn",
    "Tessik",
    "Aurren",
    "Feyth",
    "Gorran",
    "Lissel",
    "Nahren",
    "Pyreth",
    "Sarvik",
    "Torvun",
    "Vessen",
    "Wyndle",
    "Arlox",
    "Crynn",
    "Dakren",
    "Elthis",
    "Fikken",
    "Halvex",
    "Iyren",
    "Jassik",
]

PERSONALITY_ARCHETYPES = [
    "Wise Elder",
    "Trickster",
    "Guardian",
    "Healer",
    "Builder",
    "Wanderer",
    "Hermit",
    "Warrior",
    "Merchant",
    "Enforcer",
]


def generate_location_name(location_type: str, rng: random.Random) -> str:
    prefix = rng.choice(LOCATION_PREFIXES)
    suffixes = LOCATION_SUFFIXES.get(location_type, ["Place"])
    suffix = rng.choice(suffixes)
    return f"{prefix} {suffix}"


def pick_creature_name(used: set, rng: random.Random) -> str:
    available = [n for n in CREATURE_NAMES if n not in used]
    if not available:
        return f"Creature-{rng.randint(100, 999)}"
    return rng.choice(available)


def pick_species(used: set, rng: random.Random) -> str:
    available = [s for s in SPECIES_NAMES if s not in used]
    if not available:
        return rng.choice(SPECIES_NAMES)
    return rng.choice(available)
