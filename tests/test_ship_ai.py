"""Tests for the ARIA Ship AI module."""

from src.ship_ai import ShipAI


class FakePlayer:
    def __init__(self, food=100.0, water=100.0, suit_integrity=92.0, location_name="Crash Site"):
        self.food = food
        self.water = water
        self.suit_integrity = suit_integrity
        self.location_name = location_name


class FakeDrone:
    def __init__(self, battery=100.0):
        self.battery = battery


class TestShipAISpeak:
    def test_speak_formats_message(self):
        ai = ShipAI()
        result = ai.speak("Hello Commander")
        assert "ARIA:" in result
        assert "Hello Commander" in result

    def test_speak_includes_rich_markup(self):
        ai = ShipAI()
        result = ai.speak("test")
        assert "[bold bright_white]" in result


class TestStatusReport:
    def test_no_warning_at_full_resources(self):
        ai = ShipAI()
        result = ai.status_report(FakePlayer(), FakeDrone())
        assert result is None

    def test_food_warning_at_50(self):
        ai = ShipAI()
        result = ai.status_report(FakePlayer(food=48), FakeDrone())
        assert result is not None
        assert "ARIA:" in result

    def test_water_warning_at_30(self):
        ai = ShipAI()
        # First clear the 50 threshold for water
        ai.warnings_given["water"].add(50)
        result = ai.status_report(FakePlayer(water=28), FakeDrone())
        assert result is not None

    def test_battery_warning(self):
        ai = ShipAI()
        result = ai.status_report(FakePlayer(), FakeDrone(battery=45))
        assert result is not None
        assert "battery" in result.lower() or "Battery" in result

    def test_warning_fires_only_once(self):
        ai = ShipAI()
        player = FakePlayer(food=48)
        drone = FakeDrone()
        first = ai.status_report(player, drone)
        second = ai.status_report(player, drone)
        assert first is not None
        assert second is None  # same threshold should not fire again

    def test_multiple_thresholds_fire_in_sequence(self):
        ai = ShipAI()
        drone = FakeDrone()
        # First at 48%
        r1 = ai.status_report(FakePlayer(food=48), drone)
        assert r1 is not None
        # Then at 28%
        r2 = ai.status_report(FakePlayer(food=28), drone)
        assert r2 is not None

    def test_reset_warnings_allows_refire(self):
        ai = ShipAI()
        player = FakePlayer(food=48)
        drone = FakeDrone()
        ai.status_report(player, drone)
        ai.reset_warnings("food")
        result = ai.status_report(player, drone)
        assert result is not None


class TestPostTravelSummary:
    def test_summary_contains_location_and_stats(self):
        ai = ShipAI()
        player = FakePlayer(food=80, water=70, location_name="Crystal Ridge")
        drone = FakeDrone(battery=60)
        result = ai.post_travel_summary(player, drone, 3, 15.5)
        assert "Crystal Ridge" in result
        assert "80%" in result
        assert "70%" in result
        assert "60%" in result


class TestObjectiveReminder:
    def test_no_reminder_before_interval(self):
        ai = ShipAI()
        checklist = {"a": False, "b": True}
        for _ in range(9):
            result = ai.objective_reminder(checklist)
        assert result is None

    def test_reminder_at_interval(self):
        ai = ShipAI()
        checklist = {"a": False, "b": True}
        result = None
        for _ in range(10):
            result = ai.objective_reminder(checklist)
        assert result is not None
        assert "1/2" in result

    def test_reminder_when_all_done(self):
        ai = ShipAI()
        ai.command_count = 9
        checklist = {"a": True, "b": True}
        result = ai.objective_reminder(checklist)
        assert result is not None
        assert "complete" in result.lower()


class TestSerialization:
    def test_round_trip(self):
        ai = ShipAI()
        ai.warnings_given["food"].add(50)
        ai.command_count = 7
        ai.boot_complete = True

        data = ai.to_dict()
        restored = ShipAI.from_dict(data)

        assert 50 in restored.warnings_given["food"]
        assert restored.command_count == 7
        assert restored.boot_complete is True

    def test_from_dict_defaults(self):
        restored = ShipAI.from_dict({})
        assert restored.command_count == 0
        assert restored.boot_complete is True  # default for loaded saves
