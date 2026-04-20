"""Player state management: inventory, location, survival meters."""

from dataclasses import dataclass, field


@dataclass
class Player:
    name: str = "Commander"
    location_name: str = "Crash Site"
    inventory: dict[str, int] = field(default_factory=dict)
    ship_storage: dict[str, int] = field(default_factory=dict)
    food: float = 100.0
    water: float = 100.0
    suit_integrity: float = 92.0  # starts slightly damaged from crash
    hours_elapsed: int = 0
    known_locations: set[str] = field(default_factory=lambda: {"Crash Site"})
    food_warning_given: bool = False
    water_warning_given: bool = False

    def add_item(self, item: str, qty: int = 1):
        self.inventory[item] = self.inventory.get(item, 0) + qty

    def remove_item(self, item: str, qty: int = 1) -> bool:
        if self.inventory.get(item, 0) >= qty:
            self.inventory[item] -= qty
            if self.inventory[item] <= 0:
                del self.inventory[item]
            return True
        return False

    def has_item(self, item: str, qty: int = 1) -> bool:
        return self.inventory.get(item, 0) >= qty

    def consume_resources(self, hours: int):
        """Deplete food, water, and suit integrity over travel time."""
        # ~2% per hour for food, ~3% per hour for water
        self.food = max(0, self.food - hours * 2.0)
        self.water = max(0, self.water - hours * 3.0)
        # Suit degrades slowly: ~0.5% per hour of travel
        self.suit_integrity = max(0, self.suit_integrity - hours * 0.5)
        self.hours_elapsed += hours

    def replenish_food(self):
        self.food = 100.0
        self.food_warning_given = False

    def replenish_water(self):
        self.water = 100.0
        self.water_warning_given = False

    def discover_location(self, name: str):
        self.known_locations.add(name)

    @property
    def total_items(self) -> int:
        return sum(self.inventory.values())

    def stash_item(self, item: str, qty: int = 1) -> bool:
        """Move item from inventory to ship storage."""
        if self.inventory.get(item, 0) >= qty:
            self.remove_item(item, qty)
            self.ship_storage[item] = self.ship_storage.get(item, 0) + qty
            return True
        return False

    def retrieve_item(self, item: str, qty: int = 1) -> bool:
        """Move item from ship storage to inventory."""
        if self.ship_storage.get(item, 0) >= qty:
            self.ship_storage[item] -= qty
            if self.ship_storage[item] <= 0:
                del self.ship_storage[item]
            self.add_item(item, qty)
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "location_name": self.location_name,
            "inventory": dict(self.inventory),
            "ship_storage": dict(self.ship_storage),
            "food": self.food,
            "water": self.water,
            "suit_integrity": self.suit_integrity,
            "hours_elapsed": self.hours_elapsed,
            "known_locations": list(self.known_locations),
            "food_warning_given": self.food_warning_given,
            "water_warning_given": self.water_warning_given,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Player":
        d["known_locations"] = set(d["known_locations"])
        if "suit_integrity" not in d:
            d["suit_integrity"] = 92.0
        if "ship_storage" not in d:
            d["ship_storage"] = {}
        # Strip unknown keys for forward compatibility with old saves
        valid_fields = {f.name for f in __import__("dataclasses").fields(cls)}
        d = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**d)
