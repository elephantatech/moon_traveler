"""Session stats tracking for gameplay metrics."""

import time
from dataclasses import dataclass, field


@dataclass
class SessionStats:
    """Tracks per-session gameplay statistics. Not persisted to save files."""

    session_start: float = field(default_factory=time.time)
    commands: int = 0
    km_traveled: float = 0.0
    creatures_talked: set = field(default_factory=set)
    hazards_survived: int = 0
    trades: int = 0
    gifts_given: int = 0
    items_collected: int = 0

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
