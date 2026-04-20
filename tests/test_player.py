"""Tests for Player state management."""

from src.player import Player


class TestInventory:
    def test_add_item(self):
        p = Player()
        p.add_item("ice_crystal")
        assert p.inventory["ice_crystal"] == 1

    def test_add_item_stacks(self):
        p = Player()
        p.add_item("ice_crystal", 3)
        assert p.inventory["ice_crystal"] == 3
        p.add_item("ice_crystal", 2)
        assert p.inventory["ice_crystal"] == 5

    def test_remove_item(self):
        p = Player()
        p.add_item("bio_gel", 2)
        assert p.remove_item("bio_gel") is True
        assert p.inventory["bio_gel"] == 1

    def test_remove_item_deletes_at_zero(self):
        p = Player()
        p.add_item("metal_shard")
        p.remove_item("metal_shard")
        assert "metal_shard" not in p.inventory

    def test_remove_item_fails_if_missing(self):
        p = Player()
        assert p.remove_item("ice_crystal") is False

    def test_remove_item_fails_if_insufficient(self):
        p = Player()
        p.add_item("bio_gel", 1)
        assert p.remove_item("bio_gel", 2) is False
        assert p.inventory["bio_gel"] == 1

    def test_has_item(self):
        p = Player()
        assert p.has_item("ice_crystal") is False
        p.add_item("ice_crystal", 3)
        assert p.has_item("ice_crystal") is True
        assert p.has_item("ice_crystal", 3) is True
        assert p.has_item("ice_crystal", 4) is False

    def test_total_items(self):
        p = Player()
        assert p.total_items == 0
        p.add_item("ice_crystal", 2)
        p.add_item("bio_gel", 3)
        assert p.total_items == 5


class TestShipStorage:
    def test_stash_item(self):
        p = Player()
        p.add_item("ice_crystal", 3)
        assert p.stash_item("ice_crystal") is True
        assert p.inventory["ice_crystal"] == 2
        assert p.ship_storage["ice_crystal"] == 1

    def test_stash_item_fails_if_missing(self):
        p = Player()
        assert p.stash_item("bio_gel") is False

    def test_retrieve_item(self):
        p = Player()
        p.ship_storage["metal_shard"] = 2
        assert p.retrieve_item("metal_shard") is True
        assert p.ship_storage["metal_shard"] == 1
        assert p.inventory["metal_shard"] == 1

    def test_retrieve_item_removes_key_at_zero(self):
        p = Player()
        p.ship_storage["bio_gel"] = 1
        p.retrieve_item("bio_gel")
        assert "bio_gel" not in p.ship_storage
        assert p.inventory["bio_gel"] == 1

    def test_retrieve_item_fails_if_missing(self):
        p = Player()
        assert p.retrieve_item("ice_crystal") is False

    def test_stash_and_retrieve_round_trip(self):
        p = Player()
        p.add_item("power_cell", 2)
        p.stash_item("power_cell", 2)
        assert p.total_items == 0
        assert p.ship_storage["power_cell"] == 2
        p.retrieve_item("power_cell", 2)
        assert p.total_items == 2
        assert "power_cell" not in p.ship_storage


class TestResources:
    def test_consume_resources(self):
        p = Player()
        p.consume_resources(5)
        assert p.food == 90.0  # 100 - 5*2
        assert p.water == 85.0  # 100 - 5*3
        assert p.suit_integrity == 89.5  # 92 - 5*0.5
        assert p.hours_elapsed == 5

    def test_consume_resources_floors_at_zero(self):
        p = Player()
        p.consume_resources(200)  # enough to deplete everything
        assert p.food == 0
        assert p.water == 0
        assert p.suit_integrity == 0

    def test_replenish_food(self):
        p = Player()
        p.food = 30.0
        p.food_warning_given = True
        p.replenish_food()
        assert p.food == 100.0
        assert p.food_warning_given is False

    def test_replenish_water(self):
        p = Player()
        p.water = 20.0
        p.water_warning_given = True
        p.replenish_water()
        assert p.water == 100.0
        assert p.water_warning_given is False


class TestSerialization:
    def test_round_trip(self):
        p = Player()
        p.add_item("ice_crystal", 2)
        p.ship_storage = {"bio_gel": 1}
        p.food = 75.0
        p.discover_location("Frost Ridge")
        d = p.to_dict()
        p2 = Player.from_dict(d)
        assert p2.inventory == {"ice_crystal": 2}
        assert p2.ship_storage == {"bio_gel": 1}
        assert p2.food == 75.0
        assert "Frost Ridge" in p2.known_locations

    def test_from_dict_backwards_compat_no_suit(self):
        d = {
            "location_name": "Crash Site",
            "inventory": {},
            "food": 100.0,
            "water": 100.0,
            "hours_elapsed": 0,
            "known_locations": ["Crash Site"],
            "food_warning_given": False,
            "water_warning_given": False,
        }
        p = Player.from_dict(d)
        assert p.suit_integrity == 92.0
        assert p.ship_storage == {}

    def test_round_trip_preserves_name(self):
        p = Player()
        p.name = "Ripley"
        d = p.to_dict()
        assert d["name"] == "Ripley"
        p2 = Player.from_dict(d)
        assert p2.name == "Ripley"

    def test_from_dict_backwards_compat_no_name(self):
        """Old saves without name field get default 'Commander'."""
        d = {
            "location_name": "Crash Site",
            "inventory": {},
            "ship_storage": {},
            "food": 100.0,
            "water": 100.0,
            "suit_integrity": 92.0,
            "hours_elapsed": 0,
            "known_locations": ["Crash Site"],
            "food_warning_given": False,
            "water_warning_given": False,
        }
        p = Player.from_dict(d)
        assert p.name == "Commander"

    def test_default_name(self):
        p = Player()
        assert p.name == "Commander"

    def test_from_dict_backwards_compat_no_storage(self):
        d = {
            "location_name": "Crash Site",
            "inventory": {},
            "food": 100.0,
            "water": 100.0,
            "suit_integrity": 80.0,
            "hours_elapsed": 5,
            "known_locations": ["Crash Site"],
            "food_warning_given": False,
            "water_warning_given": False,
        }
        p = Player.from_dict(d)
        assert p.ship_storage == {}
        assert p.suit_integrity == 80.0
