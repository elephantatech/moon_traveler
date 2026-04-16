"""ARIA — the ship's onboard AI. Narrates, warns, and tracks status."""

# Warning thresholds (descending) — each fires once until resource is replenished
THRESHOLDS = [50, 30, 15, 5]

FOOD_WARNINGS = {
    50: "Commander, food reserves have dropped below 50%. Consider locating a food source.",
    30: "Nutritional reserves at 30%. I strongly recommend prioritizing a food source.",
    15: "Food reserves critical — 15%. Starvation will impair your judgment, Commander.",
    5: "Commander, you are starving. Locate food immediately or this mission ends here.",
}

WATER_WARNINGS = {
    50: "Hydration reserves below 50%. Keep an eye out for water sources.",
    30: "Water at 30%. Dehydration on Enceladus is... inadvisable, Commander.",
    15: "Water reserves critical — 15%. Your body cannot sustain this much longer.",
    5: "Commander, you are severely dehydrated. Find water now.",
}

BATTERY_WARNINGS = {
    50: "Drone battery below 50%. Return to the crash site to recharge when convenient.",
    30: "Drone battery at 30%. Scanner and travel capability will be limited soon.",
    15: "Drone battery critical — 15%. I recommend an immediate return to recharge.",
    5: "Battery nearly depleted. I can barely maintain sensor contact, Commander.",
}

SUIT_WARNINGS = {
    50: "Suit integrity dropping below 50%. The environment is taking its toll, Commander.",
    30: "Suit integrity at 30%. Thermal regulation is degrading. Be careful out there.",
    15: "Suit integrity critical — 15%. Exposure risk is climbing. Limit travel.",
    5: "Commander, your suit is barely holding. Any further damage could be fatal.",
}

OBJECTIVE_INTERVAL = 10  # commands between objective reminders


class ShipAI:
    """ARIA: the ship's embedded AI companion."""

    def __init__(self):
        self.name = "ARIA"
        self.warnings_given: dict[str, set[int]] = {
            "food": set(),
            "water": set(),
            "battery": set(),
            "suit": set(),
        }
        self.command_count = 0
        self.boot_complete = False

    # --- Formatted speech ---

    def speak(self, message: str) -> str:
        """Format a message as ARIA speech."""
        return f"[bold bright_white]ARIA:[/bold bright_white] [white]{message}[/white]"

    # --- Proactive status checks (called after every command) ---

    def status_report(self, player, drone) -> str | None:
        """Check food/water/battery/suit against thresholds. Returns warning or None."""
        msg = self._check_resource("food", player.food, FOOD_WARNINGS)
        if msg:
            return msg
        msg = self._check_resource("water", player.water, WATER_WARNINGS)
        if msg:
            return msg
        msg = self._check_resource("suit", player.suit_integrity, SUIT_WARNINGS)
        if msg:
            return msg
        msg = self._check_resource("battery", drone.battery, BATTERY_WARNINGS)
        if msg:
            return msg
        return None

    def _check_resource(self, key: str, value: float, warnings: dict) -> str | None:
        for threshold in THRESHOLDS:
            if value <= threshold and threshold not in self.warnings_given[key]:
                self.warnings_given[key].add(threshold)
                return self.speak(warnings[threshold])
        return None

    def reset_warnings(self, key: str):
        """Call when a resource is replenished to re-arm warnings."""
        self.warnings_given[key] = set()

    # --- Post-travel summary ---

    def post_travel_summary(
        self, player, drone,
        food_before: float = 0, water_before: float = 0,
        suit_before: float = 0, batt_before: float = 0,
    ) -> str:
        food_lost = food_before - player.food
        water_lost = water_before - player.water
        suit_lost = suit_before - player.suit_integrity
        batt_lost = batt_before - drone.battery
        return self.speak(
            f"Arrived at {player.location_name}. "
            f"Food: {player.food:.0f}% (-{food_lost:.0f}) | "
            f"Water: {player.water:.0f}% (-{water_lost:.0f}) | "
            f"Suit: {player.suit_integrity:.0f}% (-{suit_lost:.0f}) | "
            f"Battery: {drone.battery:.0f}% (-{batt_lost:.0f})"
        )

    # --- Objective reminder (periodic) ---

    def objective_reminder(self, repair_checklist: dict) -> str | None:
        """Fires every OBJECTIVE_INTERVAL commands with repair progress."""
        self.command_count += 1
        if self.command_count % OBJECTIVE_INTERVAL != 0:
            return None
        done = sum(1 for v in repair_checklist.values() if v)
        total = len(repair_checklist)
        if done == total:
            return self.speak("All repairs complete. You should be able to launch, Commander.")
        return self.speak(
            f"Repair progress: {done}/{total}. Materials and crew assistance are still needed."
        )

    # --- Serialization ---

    def to_dict(self) -> dict:
        return {
            "warnings_given": {k: list(v) for k, v in self.warnings_given.items()},
            "command_count": self.command_count,
            "boot_complete": self.boot_complete,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShipAI":
        ai = cls()
        # Merge loaded warnings into defaults so all keys exist (old saves may be missing some)
        loaded = {k: set(v) for k, v in d.get("warnings_given", {}).items()}
        ai.warnings_given = {**ai.warnings_given, **loaded}
        ai.command_count = d.get("command_count", 0)
        ai.boot_complete = d.get("boot_complete", True)
        return ai
