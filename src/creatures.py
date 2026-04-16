"""Creature generation, trust tracking, and dialogue state."""

import random
from dataclasses import dataclass, field

from src.data.names import PERSONALITY_ARCHETYPES, pick_creature_name, pick_species


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
    chased_away: bool = False  # if hostile creature just chased player

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
        # Keep last 10 exchanges (20 messages)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

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
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Creature":
        d.pop("chased_away", None)
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


def generate_creatures(world: dict, rng: random.Random) -> list[Creature]:
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

    for i in range(min(num_creatures, len(eligible))):
        loc = eligible[i]
        name = pick_creature_name(used_names, rng)
        used_names.add(name)
        species = pick_species(used_species, rng)
        used_species.add(species)
        archetype = archetypes[i % len(archetypes)]
        disposition = dispositions[i] if i < len(dispositions) else "neutral"

        # Assign knowledge (1-3 pieces)
        knowledge = rng.sample(KNOWLEDGE_POOL, rng.randint(1, 3))

        # Materials this creature can give at high trust
        can_give = rng.sample(MATERIALS_POOL, rng.randint(1, 2))

        # Some creatures know about food/water sources
        food_locs = [x for x in locations if x.food_source and x.name != loc.name]
        water_locs = [x for x in locations if x.water_source and x.name != loc.name]
        knows_food = rng.choice(food_locs).name if food_locs and rng.random() < 0.4 else None
        knows_water = rng.choice(water_locs).name if water_locs and rng.random() < 0.4 else None

        # Initial trust based on disposition
        initial_trust = {"friendly": 25, "neutral": 10, "hostile": 0}[disposition]

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
        )
        creatures.append(creature)

        # Link creature to location
        loc.creature_id = creature.id

    return creatures
