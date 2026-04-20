"""Session stats tracking for gameplay metrics."""

import time
from dataclasses import dataclass, field


@dataclass
class SessionStats:
    """Tracks per-session gameplay statistics. Not persisted to save files."""

    session_start: float = field(default_factory=time.time)
    commands: int = 0
    km_traveled: float = 0.0
    creatures_talked: set[str] = field(default_factory=set)
    hazards_survived: int = 0
    trades: int = 0
    gifts_given: int = 0
    items_collected: int = 0

    def calculate_score(self, hours_elapsed: int, creatures: list, repair_checklist: dict) -> tuple[int, str]:
        """Calculate final score and letter grade.

        Returns (score, grade) where score is 0-1000 and grade is S/A/B/C/D.
        """
        # Base: reward survival time
        base = min(500, hours_elapsed * 20)

        # Bonus: creature relationships and repair progress
        allies = sum(1 for c in creatures if c.trust > 50)
        repairs_done = sum(1 for v in repair_checklist.values() if v)
        bonus = allies * 50 + repairs_done * 50

        # Efficiency: reward concise play (baseline 100 commands, bonus for doing less)
        efficiency = min(200, max(0, 200 - max(0, self.commands - 100)))

        # Deductions
        deduction = self.hazards_survived * 15

        raw = base + bonus + efficiency - deduction
        score = max(0, min(1000, raw))

        if score >= 900:
            grade = "S"
        elif score >= 750:
            grade = "A"
        elif score >= 600:
            grade = "B"
        elif score >= 450:
            grade = "C"
        else:
            grade = "D"

        return score, grade

    @property
    def elapsed_seconds(self) -> float:
        """Real-world seconds since session started."""
        return time.time() - self.session_start

    @property
    def elapsed_display(self) -> str:
        """Human-readable elapsed time."""
        secs = int(self.elapsed_seconds)
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m {secs % 60}s"
        hours = mins // 60
        return f"{hours}h {mins % 60}m"
