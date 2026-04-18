"""Tests for session stats tracking."""

import time

from src.stats import SessionStats


class TestSessionStats:
    def test_defaults(self):
        s = SessionStats()
        assert s.commands == 0
        assert s.km_traveled == 0.0
        assert s.creatures_talked == set()
        assert s.hazards_survived == 0
        assert s.trades == 0
        assert s.gifts_given == 0
        assert s.items_collected == 0

    def test_elapsed_seconds(self):
        s = SessionStats(session_start=time.time() - 10)
        assert s.elapsed_seconds >= 10

    def test_elapsed_display_seconds(self):
        s = SessionStats(session_start=time.time() - 30)
        assert "s" in s.elapsed_display

    def test_elapsed_display_minutes(self):
        s = SessionStats(session_start=time.time() - 125)
        assert "m" in s.elapsed_display

    def test_elapsed_display_hours(self):
        s = SessionStats(session_start=time.time() - 3700)
        assert "h" in s.elapsed_display

    def test_increment_commands(self):
        s = SessionStats()
        s.commands += 1
        s.commands += 1
        assert s.commands == 2

    def test_increment_km(self):
        s = SessionStats()
        s.km_traveled += 5.3
        s.km_traveled += 2.1
        assert abs(s.km_traveled - 7.4) < 0.01

    def test_creatures_talked_unique(self):
        s = SessionStats()
        s.creatures_talked.add("creature_1")
        s.creatures_talked.add("creature_2")
        s.creatures_talked.add("creature_1")  # duplicate
        assert len(s.creatures_talked) == 2

    def test_all_counters(self):
        s = SessionStats()
        s.hazards_survived = 3
        s.trades = 2
        s.gifts_given = 5
        s.items_collected = 8
        assert s.hazards_survived == 3
        assert s.trades == 2
        assert s.gifts_given == 5
        assert s.items_collected == 8
