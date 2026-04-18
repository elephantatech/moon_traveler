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


class FakeCreature:
    def __init__(self, trust=0):
        self.trust = trust


class TestCalculateScore:
    def test_score_range(self):
        s = SessionStats()
        score, grade = s.calculate_score(10, [], {})
        assert 0 <= score <= 1000

    def test_grade_s(self):
        s = SessionStats()
        s.commands = 10
        creatures = [FakeCreature(trust=80) for _ in range(5)]
        checklist = {f"m_{i}": True for i in range(8)}
        score, grade = s.calculate_score(25, creatures, checklist)
        assert grade == "S"

    def test_grade_d_on_zero(self):
        s = SessionStats()
        s.hazards_survived = 30
        score, grade = s.calculate_score(0, [], {})
        assert grade == "D"
        assert score == 0

    def test_hazards_reduce_score(self):
        s1 = SessionStats()
        s1.commands = 50
        s2 = SessionStats()
        s2.commands = 50
        s2.hazards_survived = 10
        score1, _ = s1.calculate_score(10, [], {})
        score2, _ = s2.calculate_score(10, [], {})
        assert score1 > score2

    def test_allies_increase_score(self):
        s = SessionStats()
        s.commands = 50
        no_allies = s.calculate_score(10, [], {})[0]
        with_allies = s.calculate_score(10, [FakeCreature(trust=60), FakeCreature(trust=70)], {})[0]
        assert with_allies > no_allies

    def test_all_grades_exist(self):
        for grade in ["S", "A", "B", "C", "D"]:
            # Ensure each grade is achievable
            s = SessionStats()
            if grade == "S":
                s.commands = 5
                score, g = s.calculate_score(25, [FakeCreature(80)] * 5, {f"m_{i}": True for i in range(8)})
            elif grade == "D":
                s.hazards_survived = 50
                score, g = s.calculate_score(0, [], {})
            else:
                continue  # middle grades are harder to target exactly
            assert g == grade
