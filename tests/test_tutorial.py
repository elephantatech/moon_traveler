"""Tests for the Tutorial module."""

from src.tutorial import TutorialManager, TutorialStep


class TestTutorialStep:
    def test_step_ordering(self):
        assert TutorialStep.NOT_STARTED < TutorialStep.BOOT_SEQUENCE
        assert TutorialStep.BOOT_SEQUENCE < TutorialStep.COMPLETED

    def test_completed_is_last(self):
        assert TutorialStep.COMPLETED == max(TutorialStep)


class TestTutorialManager:
    def test_initial_state(self):
        t = TutorialManager()
        assert t.step == TutorialStep.NOT_STARTED
        assert not t.completed

    def test_completed_property(self):
        t = TutorialManager()
        t.step = TutorialStep.COMPLETED
        assert t.completed

    def test_check_progress_advances_on_look(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_LOOK
        hint = t.check_progress("look", None)
        assert hint is not None
        assert "scan" in hint.lower()
        assert t.step == TutorialStep.PROMPT_SCAN

    def test_check_progress_advances_on_scan(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_SCAN
        hint = t.check_progress("scan", None)
        assert hint is not None
        assert "gps" in hint.lower()
        assert t.step == TutorialStep.PROMPT_GPS

    def test_check_progress_advances_on_gps(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_GPS
        hint = t.check_progress("gps", None)
        assert hint is not None
        assert "travel" in hint.lower()

    def test_check_progress_advances_on_travel(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_TRAVEL
        hint = t.check_progress("travel Frost Ridge", None)
        assert hint is not None
        assert "talk" in hint.lower()

    def test_check_progress_advances_on_talk(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_TALK
        hint = t.check_progress("talk", None)
        assert hint is not None
        assert "own" in hint.lower()
        assert t.step == TutorialStep.COMPLETED

    def test_no_hint_when_completed(self):
        t = TutorialManager()
        t.step = TutorialStep.COMPLETED
        assert t.check_progress("look", None) is None

    def test_no_nagging_on_wrong_command(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_LOOK
        hint = t.check_progress("help", None)
        assert hint is None
        assert t.step == TutorialStep.PROMPT_LOOK  # not advanced

    def test_aliases_work(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_LOOK
        hint = t.check_progress("l", None)
        assert hint is not None

    def test_map_alias_works(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_GPS
        hint = t.check_progress("map", None)
        assert hint is not None


class TestTutorialSerialization:
    def test_round_trip(self):
        t = TutorialManager()
        t.step = TutorialStep.PROMPT_GPS
        data = t.to_dict()
        restored = TutorialManager.from_dict(data)
        assert restored.step == TutorialStep.PROMPT_GPS

    def test_from_dict_defaults_to_completed(self):
        restored = TutorialManager.from_dict({})
        assert restored.step == TutorialStep.COMPLETED
        assert restored.completed
