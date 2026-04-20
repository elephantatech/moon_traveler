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

    def test_grade_a(self):
        s = SessionStats()
        s.commands = 200
        # base=400 + allies=250 + efficiency=100 = 750 => A
        _, grade = s.calculate_score(20, [FakeCreature(80)] * 5, {})
        assert grade == "A"

    def test_grade_b(self):
        s = SessionStats()
        s.commands = 250
        # base=400 + efficiency=50 + allies=100 + repairs=50 = 600 => B
        _, grade = s.calculate_score(20, [FakeCreature(60)] * 2, {"m_0": True})
        assert grade == "B"

    def test_grade_c(self):
        s = SessionStats()
        s.commands = 300
        # base=400 + efficiency=0 + allies=50 = 450 => C
        _, grade = s.calculate_score(20, [FakeCreature(60)], {})
        assert grade == "C"

    def test_score_capped_at_1000(self):
        s = SessionStats()
        s.commands = 5
        # base=500 + allies=500 + repairs=400 + efficiency=200 = 1600 => clamped to 1000
        score, grade = s.calculate_score(25, [FakeCreature(80)] * 10, {f"m_{i}": True for i in range(8)})
        assert score == 1000
        assert grade == "S"

    def test_score_capped_at_zero(self):
        s = SessionStats()
        s.hazards_survived = 100
        score, _ = s.calculate_score(0, [], {})
        assert score == 0

    def test_score_ignores_sentinel_keys_in_checklist(self):
        """_escorts_completed sentinel in checklist must not inflate repair count."""
        s = SessionStats()
        s.commands = 50
        # Clean checklist: 2 repairs done
        clean = {"m_0": True, "m_1": True, "m_2": False}
        score_clean, _ = s.calculate_score(10, [], clean)
        # With sentinel: should produce same score (sentinel is truthy int, would inflate if not filtered)
        dirty = {"m_0": True, "m_1": True, "m_2": False, "_escorts_completed": 2}
        score_dirty, _ = s.calculate_score(10, [], dirty)
        assert score_clean == score_dirty

    def test_allies_threshold_is_gte_50(self):
        """Creatures at exactly trust=50 should count as allies."""
        s = SessionStats()
        s.commands = 50
        score_49, _ = s.calculate_score(10, [FakeCreature(49)], {})
        score_50, _ = s.calculate_score(10, [FakeCreature(50)], {})
        assert score_50 > score_49  # trust=50 counts, trust=49 does not

    def test_grade_verdicts_exist_for_all_grades(self):
        from src.data.prompts import GRADE_VERDICTS

        for grade in ["S", "A", "B", "C", "D"]:
            assert grade in GRADE_VERDICTS, f"Missing verdicts for grade {grade}"
            assert len(GRADE_VERDICTS[grade]) >= 1, f"Empty verdicts for grade {grade}"
