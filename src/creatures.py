"""Creature generation, trust tracking, and dialogue state."""

import random
from dataclasses import dataclass, field

from src.data.names import PERSONALITY_ARCHETYPES, pick_creature_name, pick_species

# Role-based capabilities: what each archetype can provide and at what trust level
ROLE_CAPABILITIES = {
    "Healer": {
        "provides": ["heal", "repair_suit", "food", "water"],
        "materials": [],
        "trust_threshold": {"heal": 0, "repair_suit": 0, "food": 10, "water": 10},
        "description": "Heals freely — it's their calling",
    },
    "Builder": {
        "provides": ["materials"],
        "materials": ["metal_shard", "hull_patch", "circuit_board", "thermal_paste"],
        "trust_threshold": {"materials": 35},
        "description": "Provides repair materials at medium trust",
    },
    "Wise Elder": {
        "provides": ["materials", "creature_intel"],
        "materials": ["circuit_board", "antenna_array", "power_cell"],
        "trust_threshold": {"materials": 50, "creature_intel": 35},
        "description": "Strategic materials and knowledge about other creatures",
    },
    "Guardian": {
        "provides": ["materials"],
        "materials": ["power_cell", "hull_patch", "metal_shard"],
        "trust_threshold": {"materials": 70},
        "description": "Protects resources, shares only at high trust",
    },
    "Hermit": {
        "provides": ["materials"],
        "materials": ["antenna_array", "bio_gel", "thermal_paste"],
        "trust_threshold": {"materials": 80},
        "description": "Rare materials, very high trust needed",
    },
    "Wanderer": {
        "provides": ["food", "water", "location_reveal"],
        "materials": ["ice_crystal"],
        "trust_threshold": {"food": 25, "water": 25, "location_reveal": 35, "materials": 50},
        "description": "Knows the terrain, provides travel supplies",
    },
    "Trickster": {
        "provides": ["materials", "food", "water"],
        "materials": ["ice_crystal", "bio_gel", "circuit_board"],
        "trust_threshold": {"materials": 35, "food": 25, "water": 25},
        "description": "Unpredictable — may give or trick",
    },
    "Warrior": {
        "provides": ["materials"],
        "materials": ["metal_shard", "power_cell", "hull_patch"],
        "trust_threshold": {"materials": 50},
        "description": "Respects sustained effort, gives materials as reward",
    },
    "Merchant": {
        "provides": ["trade"],
        "materials": ["circuit_board", "thermal_paste", "antenna_array", "power_cell"],
        "trust_threshold": {"trade": 20},
        "description": "Trades item-for-item, never gives free",
    },
    "Enforcer": {
        "provides": ["creature_intel", "escort_verify"],
        "materials": ["hull_patch", "metal_shard"],
        "trust_threshold": {"creature_intel": 15, "escort_verify": 25, "materials": 60},
        "description": "Authority figure — advises who to talk to for ship repairs",
    },
}

# Archetypes that must appear at least once per game
GUARANTEED_ARCHETYPES = ["Merchant", "Builder", "Healer"]

# Backstory building blocks
_BACKSTORY_FAMILY = [
    "You have two young ones back at the settlement who depend on you.",
    "Your mate works as a Builder in the eastern outpost.",
    "You lost your family to a geyser surge years ago. The memory still haunts you.",
    "Your elder taught you everything you know before passing last season.",
    "You are raising your sibling's children after they went missing on the ice.",
    "Your family has lived in this region for generations.",
    "You are the last of your line. That weighs on you sometimes.",
    "Your partner is expecting. You worry about providing for them.",
]

_BACKSTORY_CONCERN = [
    "The geyser activity has been unpredictable lately — it worries you.",
    "Food has been scarce this season. Your community is struggling.",
    "Strange tremors have been shaking the ice. Something is changing underground.",
    "You have noticed fewer creatures passing through. Migration patterns are shifting.",
    "The ice is thinning in places it never did before.",
    "A sickness has been spreading through the nearby settlement.",
    "You have heard rumors of outsiders causing trouble in the north.",
    "The weather has been harsher than any season you can remember.",
]

_BACKSTORY_OPINION = [
    "You think the settlement elders are too cautious about outsiders.",
    "You believe the ancient ruins hold secrets that could help your people.",
    "You distrust anyone who arrives without warning.",
    "You think trade between communities could solve many problems.",
    "You believe the geyser fields are sacred and should not be disturbed.",
    "You think the younger generation does not respect the old ways.",
    "You believe cooperation, even with strangers, is the only way to survive.",
    "You think the Enforcers overstep their authority too often.",
]

# Items Merchants want in trade
TRADE_WANTS_POOL = [
    "ice_crystal",
    "bio_gel",
    "metal_shard",
    "range_module",
    "translator_chip",
    "cargo_rack",
    "thruster_pack",
    "battery_cell",
]


@dataclass
class Creature:
    id: str
    name: str
    species: str
    archetype: str
    disposition: str  # friendly, neutral, hostile
    location_name: str
    trust: int = 0  # 0-100
    knowledge: list[str] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)
    has_helped_repair: bool = False
    can_give_materials: list[str] = field(default_factory=list)
    knows_food_source: str | None = None
    knows_water_source: str | None = None
    color: str = "green"
    following: bool = False  # currently traveling with the player
    home_location: str | None = None  # original location, set when they start following
    helped_at_ship: bool = False  # has already helped at crash site (prevents repeat)
    # New fields for creature-centric redesign
    role_inventory: list[str] = field(default_factory=list)
    given_items: list[str] = field(default_factory=list)
    backstory: str = ""
    trade_wants: list[str] = field(default_factory=list)  # Merchant only
    memory: str = ""  # Structured markdown memory of the player and world

    @property
    def trust_level(self) -> str:
        if self.trust >= 70:
            return "high"
        elif self.trust >= 35:
            return "medium"
        return "low"

    def add_trust(self, amount: int):
        self.trust = max(0, min(100, self.trust + amount))

    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def trust_meets(self, action: str) -> bool:
        """Check if trust meets the threshold for this action based on archetype."""
        caps = ROLE_CAPABILITIES.get(self.archetype, {})
        threshold = caps.get("trust_threshold", {}).get(action, 35)
        return self.trust >= threshold

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "species": self.species,
            "archetype": self.archetype,
            "disposition": self.disposition,
            "location_name": self.location_name,
            "trust": self.trust,
            "knowledge": list(self.knowledge),
            "conversation_history": list(self.conversation_history),
            "has_helped_repair": self.has_helped_repair,
            "can_give_materials": list(self.can_give_materials),
            "knows_food_source": self.knows_food_source,
            "knows_water_source": self.knows_water_source,
            "color": self.color,
            "following": self.following,
            "home_location": self.home_location,
            "helped_at_ship": self.helped_at_ship,
            "role_inventory": list(self.role_inventory),
            "given_items": list(self.given_items),
            "backstory": self.backstory,
            "trade_wants": list(self.trade_wants),
            "memory": self.memory,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Creature":
        d.pop("chased_away", None)
        d.pop("_helped_at_ship", None)
        if "following" not in d:
            d["following"] = False
        if "home_location" not in d:
            d["home_location"] = None
        if "helped_at_ship" not in d:
            d["helped_at_ship"] = False
        # Backwards compat: map can_give_materials to role_inventory for old saves
        if "role_inventory" not in d:
            d["role_inventory"] = list(d.get("can_give_materials", []))
        if "given_items" not in d:
            d["given_items"] = []
        if "backstory" not in d:
            d["backstory"] = ""
        if "trade_wants" not in d:
            d["trade_wants"] = []
        # Strip unknown keys for forward compatibility
        valid_fields = {f.name for f in __import__("dataclasses").fields(cls)}
        d = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**d)


# Knowledge pools that creatures can have
KNOWLEDGE_POOL = [
    "knows the location of rare metal deposits",
    "understands the geyser eruption patterns",
    "can identify safe paths through the ice",
    "remembers the old settlement locations",
    "knows where the ancient ruins hold power cells",
    "understands the crystal growth patterns",
    "knows which caves are safe to shelter in",
    "can read the ice formations to predict weather",
    "knows the migration patterns of other creatures",
    "remembers how the old builders constructed shelters",
    "knows where bio-gel pools form naturally",
    "understands the subsurface water currents",
    "knows the deepest canyon paths",
    "can identify edible organisms in the ice",
    "remembers trade routes between settlements",
]

MATERIALS_POOL = [
    "ice_crystal",
    "metal_shard",
    "bio_gel",
    "circuit_board",
    "power_cell",
    "thermal_paste",
    "hull_patch",
    "antenna_array",
]


def _generate_backstory(rng: random.Random) -> str:
    """Build a short backstory from family, concern, and opinion pools."""
    family = rng.choice(_BACKSTORY_FAMILY)
    concern = rng.choice(_BACKSTORY_CONCERN)
    opinion = rng.choice(_BACKSTORY_OPINION)
    return f"{family} {concern} {opinion}"


def _ensure_guaranteed_archetypes(archetypes: list[str], num_creatures: int, rng: random.Random):
    """Ensure GUARANTEED_ARCHETYPES appear in the first num_creatures slots."""
    assigned = archetypes[:num_creatures]
    for idx, required in enumerate(GUARANTEED_ARCHETYPES):
        if idx >= len(assigned):
            break  # More guaranteed archetypes than creature slots
        if required not in assigned:
            # Find a slot that isn't itself a guaranteed archetype and swap
            swapped = False
            for i in range(len(assigned)):
                if assigned[i] not in GUARANTEED_ARCHETYPES:
                    assigned[i] = required
                    swapped = True
                    break
            if not swapped:
                # All slots are guaranteed archetypes — force-assign by index
                assigned[idx] = required
    archetypes[:num_creatures] = assigned


def _ensure_material_coverage(creatures: list["Creature"], required_materials: list[str], rng: random.Random):
    """Ensure every required material is available from at least one creature."""
    covered = set()
    for c in creatures:
        covered.update(c.role_inventory)

    for mat in required_materials:
        if mat in covered:
            continue
        # Find a creature whose archetype can naturally provide this material
        candidates = [
            c
            for c in creatures
            if mat in ROLE_CAPABILITIES.get(c.archetype, {}).get("materials", []) and mat not in c.role_inventory
        ]
        if candidates:
            chosen = rng.choice(candidates)
            chosen.role_inventory.append(mat)
        else:
            # Fallback: add to the creature with the fewest role_inventory items
            fewest = min(creatures, key=lambda c: len(c.role_inventory))
            if mat not in fewest.role_inventory:
                fewest.role_inventory.append(mat)
        covered.add(mat)


def generate_creatures(
    world: dict,
    rng: random.Random,
    required_materials: list[str] | None = None,
) -> list[Creature]:
    """Generate creatures and place them in the world."""
    config = world["config"]
    num_creatures = config["creatures"]
    hostile_count = config["hostile_count"]
    locations = world["locations"]

    # Eligible locations (not crash site)
    eligible = [loc for loc in locations if loc.loc_type != "crash_site"]
    rng.shuffle(eligible)

    used_names: set[str] = set()
    used_species: set[str] = set()
    creatures = []

    # Determine dispositions
    dispositions = (
        ["hostile"] * hostile_count
        + ["neutral"] * (num_creatures // 3)
        + ["friendly"] * (num_creatures - hostile_count - num_creatures // 3)
    )
    rng.shuffle(dispositions)

    archetypes = list(PERSONALITY_ARCHETYPES)
    rng.shuffle(archetypes)

    # Guarantee at least 1 Merchant, 1 Builder/Wise Elder, 1 Healer
    _ensure_guaranteed_archetypes(archetypes, min(num_creatures, len(eligible)), rng)

    for i in range(min(num_creatures, len(eligible))):
        loc = eligible[i]
        name = pick_creature_name(used_names, rng)
        used_names.add(name)
        species = pick_species(used_species, rng)
        used_species.add(species)
        archetype = archetypes[i % len(archetypes)]
        disposition = dispositions[i] if i < len(dispositions) else "neutral"

        # Guaranteed archetypes should not be hostile (player needs access)
        if archetype in GUARANTEED_ARCHETYPES and disposition == "hostile":
            disposition = "neutral"

        # Assign knowledge (1-3 pieces)
        knowledge = rng.sample(KNOWLEDGE_POOL, rng.randint(1, 3))

        # Role-based inventory: pull from archetype's material pool
        caps = ROLE_CAPABILITIES.get(archetype, {})
        archetype_materials = caps.get("materials", [])
        if archetype_materials:
            max_inv = min(4, len(archetype_materials))
            inv_count = rng.randint(1, max_inv)
            role_inv = rng.sample(archetype_materials, inv_count)
        else:
            role_inv = []

        # Legacy field — keep in sync for backwards compat
        can_give = list(role_inv) if role_inv else rng.sample(MATERIALS_POOL, rng.randint(1, 2))

        # Trade wants (Merchant only)
        trade_wants = []
        if archetype == "Merchant":
            trade_wants = rng.sample(TRADE_WANTS_POOL, rng.randint(2, 3))

        # Some creatures know about food/water sources
        food_locs = [x for x in locations if x.food_source and x.name != loc.name]
        water_locs = [x for x in locations if x.water_source and x.name != loc.name]
        knows_food = rng.choice(food_locs).name if food_locs and rng.random() < 0.4 else None
        knows_water = rng.choice(water_locs).name if water_locs and rng.random() < 0.4 else None

        # Initial trust based on disposition
        initial_trust = {"friendly": 25, "neutral": 10, "hostile": 0}[disposition]

        # Generate backstory
        backstory = _generate_backstory(rng)

        from src.ui import get_creature_color

        creature = Creature(
            id=f"creature_{i}",
            name=name,
            species=species,
            archetype=archetype,
            disposition=disposition,
            location_name=loc.name,
            trust=initial_trust,
            knowledge=knowledge,
            can_give_materials=can_give,
            knows_food_source=knows_food,
            knows_water_source=knows_water,
            color=get_creature_color(i),
            role_inventory=role_inv,
            backstory=backstory,
            trade_wants=trade_wants,
        )
        creatures.append(creature)

        # Link creature to location
        loc.creature_id = creature.id

    # Ensure every required repair material is available from at least one creature
    if required_materials and creatures:
        _ensure_material_coverage(creatures, required_materials, rng)

    return creatures
