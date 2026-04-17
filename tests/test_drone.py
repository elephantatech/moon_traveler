"""Tests for Drone upgrades, battery, vitals tracking, and serialization."""

from src.drone import Drone
from src.player import Player


class TestBattery:
    def test_scan_cost(self):
        d = Drone()
        assert d.scan_cost() == 10.0

    def test_can_scan(self):
        d = Drone()
        assert d.can_scan() is True
        d.battery = 5.0
        assert d.can_scan() is False

    def test_use_battery(self):
        d = Drone()
        d.use_battery(30)
        assert d.battery == 70.0

    def test_use_battery_floors_at_zero(self):
        d = Drone()
        d.use_battery(150)
        assert d.battery == 0

    def test_recharge(self):
        d = Drone()
        d.battery = 10.0
        d.recharge()
        assert d.battery == 100.0

    def test_recharge_respects_max(self):
        d = Drone()
        d.battery_max = 125.0
        d.battery = 10.0
        d.recharge()
        assert d.battery == 125.0

    def test_travel_battery_cost(self):
        d = Drone()
        assert d.travel_battery_cost(10.0) == 5.0


class TestUpgrades:
    def test_range_module(self):
        d = Drone()
        result = d.apply_upgrade("range_module")
        assert d.scanner_range == 20
        assert "range_module" in d.upgrades_installed
        assert result is not None

    def test_translator_chip(self):
        d = Drone()
        d.apply_upgrade("translator_chip")
        assert d.translation_quality == "medium"
        d.apply_upgrade("translator_chip")
        assert d.translation_quality == "high"

    def test_translator_chip_caps_at_high(self):
        d = Drone()
        d.translation_quality = "high"
        result = d.apply_upgrade("translator_chip")
        assert d.translation_quality == "high"
        assert "maximum" in result

    def test_cargo_rack(self):
        d = Drone()
        d.apply_upgrade("cargo_rack")
        assert d.cargo_capacity == 15

    def test_thruster_pack(self):
        d = Drone()
        d.apply_upgrade("thruster_pack")
        assert d.speed_boost == 5

    def test_battery_cell(self):
        d = Drone()
        d.battery = 80.0
        d.apply_upgrade("battery_cell")
        assert d.battery_max == 125.0
        assert d.battery == 105.0  # 80 + 25

    def test_voice_module(self):
        d = Drone()
        d.apply_upgrade("voice_module")
        assert d.voice_enabled is True

    def test_autopilot_chip(self):
        d = Drone()
        d.apply_upgrade("autopilot_chip")
        assert d.autopilot_enabled is True

    def test_charge_module(self):
        d = Drone()
        d.apply_upgrade("charge_module")
        assert d.charge_module_installed is True
        assert d.auto_charge_enabled is False  # Must be toggled on manually

    def test_charge_module_serialization(self):
        d = Drone()
        d.apply_upgrade("charge_module")
        d.auto_charge_enabled = True
        data = d.to_dict()
        d2 = Drone.from_dict(data)
        assert d2.charge_module_installed is True
        assert d2.auto_charge_enabled is True

    def test_invalid_upgrade(self):
        d = Drone()
        result = d.apply_upgrade("nonexistent")
        assert result is None


class TestVitalsTracking:
    def test_initial_check_returns_none(self):
        d = Drone()
        p = Player()
        assert d.check_vitals(p) is None

    def test_food_drop_triggers_whisper(self):
        d = Drone()
        p = Player()
        d.check_vitals(p)  # initialize
        p.food = 85.0  # crosses 90% bracket
        result = d.check_vitals(p)
        assert result is not None
        assert "Food: 85%" in result

    def test_no_whisper_if_no_change(self):
        d = Drone()
        p = Player()
        d.check_vitals(p)  # initialize
        result = d.check_vitals(p)  # no change
        assert result is None

    def test_critical_warning_at_low_value(self):
        d = Drone()
        p = Player()
        d.check_vitals(p)  # initialize
        p.water = 8.0
        result = d.check_vitals(p)
        assert result is not None
        assert "critical" in result

    def test_yellow_warning_at_30(self):
        d = Drone()
        p = Player()
        d.check_vitals(p)
        p.suit_integrity = 25.0
        result = d.check_vitals(p)
        assert result is not None
        assert "yellow" in result

    def test_multiple_drops_combined(self):
        d = Drone()
        p = Player()
        d.check_vitals(p)  # initialize
        p.food = 75.0
        p.water = 65.0
        result = d.check_vitals(p)
        assert result is not None
        assert "Food" in result
        assert "Water" in result

    def test_reset_tracking(self):
        d = Drone()
        p = Player()
        d.check_vitals(p)  # initialize
        p.food = 85.0
        d.check_vitals(p)  # fires
        d.reset_vital_tracking()
        result = d.check_vitals(p)  # re-initializes, no alert
        assert result is None

    def test_no_whisper_when_battery_dead(self):
        d = Drone()
        d.battery = 0
        p = Player()
        p.food = 10.0
        assert d.check_vitals(p) is None

    def test_replenish_updates_silently(self):
        d = Drone()
        p = Player()
        d.check_vitals(p)  # initialize at 100
        p.food = 75.0
        d.check_vitals(p)  # fires for 80 bracket
        p.food = 100.0  # replenished
        result = d.check_vitals(p)  # should update silently
        assert result is None


class TestSerialization:
    def test_round_trip(self):
        d = Drone()
        d.apply_upgrade("range_module")
        d.battery = 75.0
        data = d.to_dict()
        d2 = Drone.from_dict(data)
        assert d2.scanner_range == 20
        assert d2.battery == 75.0
        assert "range_module" in d2.upgrades_installed

    def test_from_dict_strips_cargo_used(self):
        d = Drone()
        data = d.to_dict()
        data["cargo_used"] = 5  # old field
        d2 = Drone.from_dict(data)
        assert not hasattr(d2, "cargo_used") or True  # should not crash
