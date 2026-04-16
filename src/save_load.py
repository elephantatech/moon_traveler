"""Save and load game state to/from JSON files."""

import json
from pathlib import Path

from src import ui
from src.creatures import Creature
from src.drone import Drone
from src.player import Player
from src.world import Location

SAVES_DIR = Path(__file__).parent.parent / "saves"

SAVE_VERSION = 2


def ensure_saves_dir():
    SAVES_DIR.mkdir(exist_ok=True)


def list_saves() -> list[str]:
    ensure_saves_dir()
    return [f.stem for f in SAVES_DIR.glob("*.json")]


def save_game(
    slot: str,
    player: Player,
    drone: Drone,
    locations: list[Location],
    creatures: list[Creature],
    world_seed: int,
    world_mode: str,
    repair_checklist: dict,
    ship_ai=None,
    tutorial=None,
):
    """Save the entire game state to a JSON file."""
    ensure_saves_dir()
    state = {
        "version": SAVE_VERSION,
        "world_seed": world_seed,
        "world_mode": world_mode,
        "player": player.to_dict(),
        "drone": drone.to_dict(),
        "locations": [loc.to_dict() for loc in locations],
        "creatures": [c.to_dict() for c in creatures],
        "repair_checklist": repair_checklist,
    }
    if ship_ai is not None:
        state["ship_ai"] = ship_ai.to_dict()
    if tutorial is not None:
        state["tutorial"] = tutorial.to_dict()
    path = SAVES_DIR / f"{slot}.json"
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
    ui.success(f"Game saved to slot '{slot}'.")


def load_game(slot: str) -> dict | None:
    """Load game state from a JSON file. Returns state dict or None on failure."""
    path = SAVES_DIR / f"{slot}.json"
    if not path.exists():
        ui.error(f"Save slot '{slot}' not found.")
        return None
    try:
        with open(path) as f:
            state = json.load(f)

        # Reconstruct core objects
        state["player"] = Player.from_dict(state["player"])
        state["drone"] = Drone.from_dict(state["drone"])
        state["locations"] = [Location.from_dict(d) for d in state["locations"]]
        state["creatures"] = [Creature.from_dict(d) for d in state["creatures"]]

        # v2 fields — ship_ai and tutorial
        if "ship_ai" in state and isinstance(state["ship_ai"], dict):
            from src.ship_ai import ShipAI

            state["ship_ai"] = ShipAI.from_dict(state["ship_ai"])
        else:
            # v1 fallback: create fresh with boot_complete=True
            from src.ship_ai import ShipAI

            ai = ShipAI()
            ai.boot_complete = True
            state["ship_ai"] = ai

        if "tutorial" in state and isinstance(state["tutorial"], dict):
            from src.tutorial import TutorialManager

            state["tutorial"] = TutorialManager.from_dict(state["tutorial"])
        else:
            # v1 fallback: tutorial already completed
            from src.tutorial import TutorialManager, TutorialStep

            t = TutorialManager()
            t.step = TutorialStep.COMPLETED
            state["tutorial"] = t

        ui.success(f"Game loaded from slot '{slot}'.")
        return state
    except Exception as e:
        ui.error(f"Failed to load save: {e}")
        return None


def auto_save(
    player: Player,
    drone: Drone,
    locations: list[Location],
    creatures: list[Creature],
    world_seed: int,
    world_mode: str,
    repair_checklist: dict,
    ship_ai=None,
    tutorial=None,
):
    """Auto-save to a dedicated slot."""
    save_game(
        "autosave",
        player,
        drone,
        locations,
        creatures,
        world_seed,
        world_mode,
        repair_checklist,
        ship_ai,
        tutorial,
    )
