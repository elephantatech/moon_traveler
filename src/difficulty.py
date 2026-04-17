"""Mode-specific difficulty scaling and junk item easter egg."""

# Difficulty settings per game mode
MODE_DIFFICULTY = {
    "short": {
        "trust_per_chat": 5,  # +5 per exchange (default 3)
        "trust_per_gift": 20,  # +20 from gifts (default 15)
        "trust_per_gift_hostile": 15,
        "item_find_chance": 0.30,  # 30% chance per trip (default 15%)
        "extra_drops": 2,  # +2 extra items at eligible locations
    },
    "medium": {
        "trust_per_chat": 4,  # slightly faster than default
        "trust_per_gift": 15,
        "trust_per_gift_hostile": 10,
        "item_find_chance": 0.20,  # 20% chance
        "extra_drops": 1,  # +1 extra item
    },
    "long": {
        "trust_per_chat": 3,  # default
        "trust_per_gift": 15,
        "trust_per_gift_hostile": 10,
        "item_find_chance": 0.15,  # default
        "extra_drops": 0,
    },
    "brutal": {
        "trust_per_chat": 2,  # very slow
        "trust_per_gift": 10,  # reduced
        "trust_per_gift_hostile": 5,  # barely registers
        "item_find_chance": 0.08,  # scarce
        "extra_drops": 0,
        "junk_find_chance": 0.03,  # 3% vs default 10% — easter egg is very hard to get
        "food_drain_mult": 1.5,  # 50% faster resource drain
        "water_drain_mult": 1.5,
        "suit_drain_mult": 1.5,
        "hazard_bonus": 0.05,  # extra hazard probability on top of late-game scaling
    },
}

# Junk items — useless collectibles that creatures mock you for
JUNK_ITEMS = [
    "old_transistor",
    "baseball",
    "rubber_duck",
    "broken_compass",
    "alien_coin",
    "fossilized_tooth",
    "faded_photograph",
    "rusty_key",
    "empty_canister",
    "cracked_lens",
]

JUNK_FIND_MESSAGES = {
    "old_transistor": "You find an old transistor half-buried in the ice. Ancient Earth tech.",
    "baseball": "A baseball? On Enceladus? How did this get here?",
    "rubber_duck": "A rubber duck, frozen solid. Someone had a sense of humor.",
    "broken_compass": "A broken compass. It spins lazily, pointing nowhere.",
    "alien_coin": "A strange coin with unfamiliar markings. Worthless, but pretty.",
    "fossilized_tooth": "A fossilized tooth from something very large. And very dead.",
    "faded_photograph": "A faded photograph. You can barely make out two figures smiling.",
    "rusty_key": "A rusty key. What could it possibly open out here?",
    "empty_canister": "An empty canister. Whatever was inside evaporated long ago.",
    "cracked_lens": "A cracked lens from some optical instrument. Useless now.",
}

# Creature reactions when player tries to give/trade junk
JUNK_REACTIONS = [
    "{name} looks at the {item} and lets out a strange bubbling sound. Laughter, maybe. 'Keep it. A souvenir from the ice.'",
    "{name} pushes the {item} back toward you. 'This is... interesting, but no. Perhaps save it for your collection.'",
    "{name} tilts their head at the {item}. 'Your species collects strange things. Hold onto it — you never know.'",
    "{name} snorts. 'You carry this across the ice? On purpose? Well, every explorer needs souvenirs.'",
    "{name} examines the {item} briefly. 'I have no use for this. But keep collecting — the ice rewards the curious.'",
    "{name} stares at the {item} for a long time. '...Why? Well, stash it somewhere safe. You might thank yourself later.'",
]

# Number of unique junk items needed in storage to trigger the easter egg
JUNK_EASTER_EGG_COUNT = 5

# Easter egg bonus: trust gain multiplier when activated
EASTER_EGG_TRUST_MULTIPLIER = 2.0


_MODE_ALIASES = {"easy": "short", "hard": "long"}

# Easter egg requires more junk in brutal mode
JUNK_EASTER_EGG_COUNT_BRUTAL = 7


def get_difficulty(mode: str) -> dict:
    """Get difficulty settings for a game mode."""
    key = _MODE_ALIASES.get(mode, mode)
    return MODE_DIFFICULTY.get(key, MODE_DIFFICULTY["long"])


def is_junk_item(item: str) -> bool:
    """Check if an item is a junk collectible."""
    return item in JUNK_ITEMS


def check_junk_easter_egg(player, mode: str = "") -> bool:
    """Check if the player has stashed enough unique junk items to trigger the easter egg."""
    junk_in_storage = sum(1 for item in player.ship_storage if item in JUNK_ITEMS)
    threshold = JUNK_EASTER_EGG_COUNT_BRUTAL if mode == "brutal" else JUNK_EASTER_EGG_COUNT
    return junk_in_storage >= threshold


# Item descriptions for the inspect command
ITEM_DESCRIPTIONS = {
    # Repair materials
    "ice_crystal": "A pure crystalline structure harvested from the ice. Used for ship hull repairs and can be processed into water at the Kitchen Bay.",
    "metal_shard": "A fragment of dense alien metal. Essential for structural ship repairs.",
    "bio_gel": "A bioluminescent organic compound. Used for ship bio-systems repair and can be cooked into food at the Kitchen Bay.",
    "circuit_board": "A complex circuit board scavenged from ancient ruins. Needed for ship navigation systems.",
    "power_cell": "A compact energy storage unit. Install in ship repairs or use at the Charging Bay for +10% permanent battery capacity.",
    "thermal_paste": "Heat-conductive compound from geyser vents. Critical for ship thermal regulation systems.",
    "hull_patch": "A pre-formed hull repair plate. Used to seal breaches in the ship exterior.",
    "antenna_array": "A communication antenna assembly. Needed to restore the ship's comms system.",
    # Drone upgrades
    "range_module": "Extends drone scanner range by 10 km. Install with 'upgrade Range Module'.",
    "translator_chip": "Improves translation quality by one level (low → medium → high). Install with 'upgrade Translator Chip'.",
    "cargo_rack": "Adds 5 cargo slots to the drone. Install with 'upgrade Cargo Rack'.",
    "thruster_pack": "Adds +5 km/h travel speed. Install with 'upgrade Thruster Pack'.",
    "battery_cell": "Adds 25% battery capacity to the drone. Install with 'upgrade Battery Cell'.",
    "voice_module": "Enables spoken voice announcements for game events. Install with 'upgrade Voice Module'.",
    "autopilot_chip": "Auto-scans and auto-looks when arriving at new locations. Install with 'upgrade Autopilot Chip'.",
    "charge_module": "Enables auto-charge: drone recovers battery during travel. Install with 'upgrade Charge Module'.",
    # Junk items
    "old_transistor": "An ancient transistor from Earth technology. No practical use here, but it's a piece of home.",
    "baseball": "A regulation baseball. How it ended up on Saturn's moon is anyone's guess.",
    "rubber_duck": "A yellow rubber duck, frozen solid. A relic of someone's bathtime.",
    "broken_compass": "A compass that spins aimlessly. Enceladus has no magnetic north.",
    "alien_coin": "A coin with strange markings. The creatures don't use currency.",
    "fossilized_tooth": "A large fossilized tooth. Whatever it came from is long gone.",
    "faded_photograph": "A photograph so faded you can barely make out the faces. Someone lost this.",
    "rusty_key": "A rusty old key. There are no locks on Enceladus.",
    "empty_canister": "An empty metal canister. Its contents evaporated ages ago.",
    "cracked_lens": "A cracked optical lens. Once part of something important.",
}
