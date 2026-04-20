"""Boot sequence and guided tutorial for new players."""

from enum import IntEnum


class TutorialStep(IntEnum):
    NOT_STARTED = 0
    BOOT_SEQUENCE = 1
    PROMPT_LOOK = 2
    PROMPT_SCAN = 3
    PROMPT_GPS = 4
    PROMPT_TRAVEL = 5
    PROMPT_TALK = 6
    COMPLETED = 7


# Map: which command advances which step, and what hint follows
_STEP_TRIGGERS = {
    TutorialStep.PROMPT_LOOK: {
        "triggers": {"look", "l"},
        "next_hint": "Good. Now use [cyan]scan[/cyan] to deploy my sensors and discover nearby locations.",
    },
    TutorialStep.PROMPT_SCAN: {
        "triggers": {"scan"},
        "next_hint": "Use [cyan]gps[/cyan] to review the locations I've mapped.",
    },
    TutorialStep.PROMPT_GPS: {
        "triggers": {"gps", "map"},
        "next_hint": "Travel to the nearest location with [cyan]travel <name>[/cyan].",
    },
    TutorialStep.PROMPT_TRAVEL: {
        "triggers": {"travel", "go"},
        "next_hint": "If there's a life form here, try [cyan]talk[/cyan] to make contact.",
    },
    TutorialStep.PROMPT_TALK: {
        "triggers": {"talk", "speak"},
        "next_hint": (
            "You're on your own now. Try [cyan]give[/cyan] to build trust, "
            "[cyan]trade[/cyan] with Merchants, [cyan]escort[/cyan] allies to your ship, "
            "and [cyan]ship[/cyan] to manage repairs. Good luck, Commander."
        ),
    },
}


class TutorialManager:
    """Tracks tutorial progression and produces the boot sequence."""

    def __init__(self):
        self.step = TutorialStep.NOT_STARTED

    @property
    def completed(self) -> bool:
        return self.step >= TutorialStep.COMPLETED

    def run_boot_sequence(self, ship_ai, player, drone, locations, repair_checklist, mode: str, replay: bool = False):
        """Print the ARIA boot diagnostics and begin the tutorial.

        Runs the full boot sequence on first play. On subsequent launches,
        shows a short welcome and skips straight to gameplay.
        Set replay=True when called from the 'tutorial' command mid-game.
        """
        from src import ui
        from src.config import is_tutorial_completed

        if not replay:
            ui.show_title()
            ui.console.print()

            # Returning player — short welcome, skip boot sequence
            if is_tutorial_completed():
                ui.console.print(drone.speak("Systems online. Welcome back, Commander."))
                ui.console.print()
                self.step = TutorialStep.COMPLETED
                ship_ai.boot_complete = True
                return

        ui.show_crash()
        ui.console.print()
        ui.console.print("[dim]You've crash-landed on Enceladus, Saturn's icy moon.[/dim]")
        ui.console.print("[dim]Your ship is damaged. You'll need to find materials and allies to repair it.[/dim]")
        ui.console.print()

        # --- System boot ---
        ui.console.print("[bold bright_white]ARIA SYSTEM v4.2.1 — INITIALIZING[/bold bright_white]")
        ui.console.print()

        import time

        time.sleep(0.4)

        # Ship diagnostics
        ui.console.print("[bold]═══ SHIP DIAGNOSTICS ═══[/bold]")
        _boot_line("Hull Integrity", "CRITICAL — 23%", "red")
        _boot_line("Life Support", "ONLINE — Degraded", "yellow")
        _boot_line("Propulsion", "OFFLINE", "red")
        _boot_line("Navigation", "OFFLINE", "red")
        _boot_line("Communications", "OFFLINE", "red")
        _boot_line("Power Grid", "BACKUP ONLY", "yellow")
        ui.console.print()
        time.sleep(0.3)

        # Environment scan
        ui.console.print("[bold]═══ ENVIRONMENT SCAN ═══[/bold]")
        _boot_line("Surface Temp", "-201\u00b0C", "cyan")
        _boot_line("Gravity", "0.0113g", "cyan")
        _boot_line("Atmosphere", "Trace — Not breathable", "yellow")
        _boot_line("Radiation", "Low (suit adequate)", "green")
        ui.console.print()
        time.sleep(0.3)

        # Crew vitals
        ui.console.print("[bold]═══ CREW VITALS ═══[/bold]")
        _boot_line("Food Reserves", f"{player.food:.0f}%", "green")
        _boot_line("Water Reserves", f"{player.water:.0f}%", "green")
        suit_color = "green" if player.suit_integrity > 60 else "yellow"
        _boot_line("Suit Integrity", f"{player.suit_integrity:.0f}%", suit_color)
        ui.console.print()
        time.sleep(0.3)

        # Repair status
        done = sum(1 for k, v in repair_checklist.items() if not k.startswith("_") and v)
        total = sum(1 for k in repair_checklist if not k.startswith("_"))
        ui.console.print("[bold]═══ REPAIR ASSESSMENT ═══[/bold]")
        _boot_line("Components Needed", str(total), "yellow")
        _boot_line("Components Found", str(done), "red" if done == 0 else "yellow")
        mode_label = {"short": "Emergency", "medium": "Standard", "long": "Full Overhaul"}
        _boot_line("Repair Class", mode_label.get(mode, mode.title()), "yellow")
        ui.console.print()
        time.sleep(0.3)

        # Drone deployment
        ui.console.print("[dim]Deploying ARIA Scout Drone...[/dim]")
        time.sleep(0.6)
        ui.console.print("[bold green]═══════ CONNECTION ESTABLISHED ═══════[/bold green]")
        ui.console.print()

        # Drone introduction
        intro = "Online and operational. I'll handle translation, scanning, and keeping you alive."
        ui.console.print(drone.speak(intro))
        ui.console.print()

        # First ARIA line + tutorial hint
        ui.console.print(ship_ai.speak("Systems online. I've assessed the damage — it's significant but recoverable."))
        ui.console.print(ship_ai.speak("I recommend observing our surroundings. Try [cyan]look[/cyan]."))
        ui.console.print()

        self.step = TutorialStep.PROMPT_LOOK
        ship_ai.boot_complete = True

    def check_progress(self, command: str, ctx) -> str | None:
        """After a command, advance tutorial and return next hint or None.

        Non-blocking: if the player skips steps, no nagging.
        """
        if self.completed:
            return None

        cmd = command.lower().split()[0] if command.strip() else ""

        step_info = _STEP_TRIGGERS.get(self.step)
        if not step_info:
            return None

        if cmd in step_info["triggers"]:
            hint = step_info["next_hint"]
            # Advance to next step
            next_step = TutorialStep(self.step + 1)
            self.step = next_step
            if next_step >= TutorialStep.COMPLETED:
                self.step = TutorialStep.COMPLETED
                from src.config import set_tutorial_completed

                set_tutorial_completed()
            return hint
        return None

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {"step": int(self.step)}

    @classmethod
    def from_dict(cls, d: dict) -> "TutorialManager":
        t = cls()
        try:
            t.step = TutorialStep(d.get("step", TutorialStep.COMPLETED))
        except ValueError:
            t.step = TutorialStep.COMPLETED
        return t


def _boot_line(label: str, value: str, color: str):
    """Print a single diagnostics readout line."""
    import time

    from src import ui

    padded = f"{label} {'.' * (24 - len(label))} "
    ui.console.print(f"  {padded}[{color}]{value}[/{color}]")
    time.sleep(0.12)
