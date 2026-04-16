"""Companion drone system: scanning, upgrades, speech, translation, advice."""

import random
from dataclasses import dataclass, field

from src.data.prompts import (
    DRONE_ARCHETYPE_TIPS,
    DRONE_DISPOSITION_TIPS,
    DRONE_TRANSLATION_FRAMES,
    DRONE_TRAVEL_MUSINGS,
    DRONE_TRUST_TIPS,
)

UPGRADE_EFFECTS = {
    "range_module": {"scanner_range": 10},
    "translator_chip": {"translation_quality_bump": 1},  # low -> medium -> high
    "cargo_rack": {"cargo_capacity": 5},
    "thruster_pack": {"speed_boost": 5},
    "battery_cell": {"battery_max": 25},
}

UPGRADE_DESCRIPTIONS = {
    "range_module": "Extends scanner range by 10 km",
    "translator_chip": "Improves translation quality by one level",
    "cargo_rack": "Adds 5 cargo slots",
    "thruster_pack": "Adds +5 km/h travel speed",
    "battery_cell": "Adds 25% battery capacity",
}

TRANSLATION_LEVELS = ["low", "medium", "high"]


@dataclass
class Drone:
    scanner_range: int = 10
    translation_quality: str = "low"
    cargo_capacity: int = 10
    speed_boost: int = 0
    battery: float = 100.0
    battery_max: float = 100.0
    upgrades_installed: list[str] = field(default_factory=list)

    def scan_cost(self) -> float:
        return 10.0

    def travel_battery_cost(self, distance: float) -> float:
        return distance * 0.5

    def can_scan(self) -> bool:
        return self.battery >= self.scan_cost()

    def use_battery(self, amount: float):
        self.battery = max(0, self.battery - amount)

    def recharge(self):
        self.battery = self.battery_max

    # --- Speech ---

    def speak(self, message: str) -> str:
        """Format a message as drone speech."""
        return f"[bold magenta]DRONE:[/bold magenta] [white]{message}[/white]"

    def whisper(self, message: str) -> str:
        """Format a private message only the player sees (not creatures)."""
        return f"  [dim magenta]< DRONE >[/dim magenta] [dim italic]{message}[/dim italic]"

    # --- Travel musings ---

    def get_travel_musing(self, rng: random.Random) -> str | None:
        """Pick a travel musing. Returns None if battery depleted."""
        if self.battery <= 0:
            return None
        return self.speak(rng.choice(DRONE_TRAVEL_MUSINGS))

    # --- Interaction advice ---

    def get_interaction_advice(self, creature, rng: random.Random) -> str | None:
        """Pick a coaching tip based on creature archetype/trust/disposition.
        Returns None if battery depleted."""
        if self.battery <= 0:
            return None
        pool: list[str] = []
        tips = DRONE_ARCHETYPE_TIPS.get(creature.archetype, [])
        pool.extend(tips)
        trust_tips = DRONE_TRUST_TIPS.get(creature.trust_level, [])
        pool.extend(trust_tips)
        disp_tips = DRONE_DISPOSITION_TIPS.get(creature.disposition, [])
        pool.extend(disp_tips)
        if not pool:
            return None
        return self.whisper(rng.choice(pool))

    def get_smart_advice(self, creature, player, repair_checklist: dict, rng: random.Random) -> str | None:
        """Context-aware drone hint: tries LLM first, then smart templates, then static pools.
        Returns None if battery depleted."""
        if self.battery <= 0:
            return None

        # Try LLM-powered hint first
        from src import llm
        if llm.is_available():
            hint = llm.generate_drone_hint(creature, player, repair_checklist)
            if hint:
                return self.whisper(hint)

        # Smart template fallback based on context
        from src.creatures import ROLE_CAPABILITIES
        caps = ROLE_CAPABILITIES.get(creature.archetype, {})
        thresholds = caps.get("trust_threshold", {})

        hints: list[str] = []

        # What does this creature have that the player needs?
        needed = [k.replace("material_", "") for k, v in repair_checklist.items() if not v]
        role_inv = getattr(creature, "role_inventory", []) or creature.can_give_materials
        available = [m for m in role_inv if m in needed]

        if available:
            mat_threshold = thresholds.get("materials", thresholds.get("trade", 50))
            if creature.trust < mat_threshold:
                hints.append(
                    f"This {creature.archetype} has materials we need, "
                    f"but trust must reach {mat_threshold}. Currently at {creature.trust}."
                )
            else:
                mat_name = available[0].replace("_", " ").title()
                hints.append(f"Trust is high enough. Try asking about {mat_name} — they should be willing to share.")

        if creature.archetype == "Healer" and (player.food < 50 or player.water < 50 or player.suit_integrity < 80):
            hints.append("This Healer can help with your vitals. Ask about healing — they help even at low trust.")

        if creature.archetype == "Merchant":
            trade_wants = getattr(creature, "trade_wants", [])
            player_has = [w for w in trade_wants if player.has_item(w)]
            if player_has:
                item_name = player_has[0].replace("_", " ").title()
                hints.append(f"This Merchant wants {item_name}. Try offering a trade.")
            else:
                hints.append("This Merchant trades items. Check what they want and bring it back.")

        if creature.archetype == "Enforcer":
            hints.append("This Enforcer knows everyone in the area. Ask who can help fix your ship.")

        if creature.archetype == "Wanderer" and (player.food < 40 or player.water < 40):
            hints.append("Wanderers share travel supplies. Ask about food or water for the road.")

        if hints:
            return self.whisper(rng.choice(hints))

        # Fall back to static pools
        return self.get_interaction_advice(creature, rng)

    def get_translation_frame(self, rng: random.Random) -> str | None:
        """Pick a translation quality flavor line."""
        if self.battery <= 0:
            return None
        frames = DRONE_TRANSLATION_FRAMES.get(self.translation_quality, [])
        if not frames:
            return None
        return self.speak(f"[dim]{rng.choice(frames)}[/dim]")

    # --- Periodic status whispers (every 10% interval) ---

    def __post_init__(self):
        self._last_reported: dict | None = None

    def _init_tracking(self):
        if self._last_reported is None:
            self._last_reported = {
                "food": None,
                "water": None,
                "suit": None,
                "battery": None,
            }

    def check_vitals(self, player) -> str | None:
        """Check if any resource crossed a 10% boundary. Returns a whisper or None.

        Fires once per 10% bracket (90, 80, 70...) per resource.
        Only reports when away from crash site (caller should gate this).
        """
        if self.battery <= 0:
            return None
        self._init_tracking()

        resources = {
            "food": player.food,
            "water": player.water,
            "suit": player.suit_integrity,
            "battery": self.battery,
        }
        alerts = []
        for key, value in resources.items():
            bracket = int(value // 10) * 10  # 73% -> 70, 45% -> 40
            last = self._last_reported[key]
            if last is None:
                self._last_reported[key] = bracket
                continue
            if bracket < last:
                # Crossed downward into a new bracket
                self._last_reported[key] = bracket
                label = key.replace("_", " ").title()
                if value <= 10:
                    alerts.append(f"[red]{label}: {value:.0f}% — critical![/red]")
                elif value <= 30:
                    alerts.append(f"[yellow]{label}: {value:.0f}%[/yellow]")
                else:
                    alerts.append(f"{label}: {value:.0f}%")
            elif bracket > last:
                # Resource was replenished, update silently
                self._last_reported[key] = bracket

        if alerts:
            return self.whisper("Status update — " + ", ".join(alerts))
        return None

    def reset_vital_tracking(self):
        """Reset tracking after full replenish (e.g. arriving at crash site)."""
        self._last_reported = None

    # --- Upgrades ---

    def apply_upgrade(self, upgrade: str) -> str | None:
        """Apply an upgrade. Returns description of effect, or None if invalid."""
        if upgrade not in UPGRADE_EFFECTS:
            return None

        effects = UPGRADE_EFFECTS[upgrade]
        result_parts = []

        if "scanner_range" in effects:
            self.scanner_range += effects["scanner_range"]
            result_parts.append(f"Scanner range: {self.scanner_range} km")

        if "translation_quality_bump" in effects:
            idx = TRANSLATION_LEVELS.index(self.translation_quality)
            if idx < len(TRANSLATION_LEVELS) - 1:
                self.translation_quality = TRANSLATION_LEVELS[idx + 1]
                result_parts.append(f"Translation: {self.translation_quality}")
            else:
                result_parts.append("Translation already at maximum")

        if "cargo_capacity" in effects:
            self.cargo_capacity += effects["cargo_capacity"]
            result_parts.append(f"Cargo capacity: {self.cargo_capacity}")

        if "speed_boost" in effects:
            self.speed_boost += effects["speed_boost"]
            result_parts.append(f"Speed boost: +{self.speed_boost} km/h")

        if "battery_max" in effects:
            self.battery_max += effects["battery_max"]
            self.battery = min(self.battery + effects["battery_max"], self.battery_max)
            result_parts.append(f"Battery max: {self.battery_max:.0f}%")

        self.upgrades_installed.append(upgrade)
        return ", ".join(result_parts)

    def to_dict(self) -> dict:
        result = {
            "scanner_range": self.scanner_range,
            "translation_quality": self.translation_quality,
            "cargo_capacity": self.cargo_capacity,
            "speed_boost": self.speed_boost,
            "battery": self.battery,
            "battery_max": self.battery_max,
            "upgrades_installed": list(self.upgrades_installed),
        }
        if self._last_reported is not None:
            result["_last_reported"] = self._last_reported
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "Drone":
        last_reported = d.pop("_last_reported", None)
        # Strip unknown keys for forward compatibility
        valid_fields = {f.name for f in __import__("dataclasses").fields(cls)}
        d = {k: v for k, v in d.items() if k in valid_fields}
        drone = cls(**d)
        drone._last_reported = last_reported
        return drone
