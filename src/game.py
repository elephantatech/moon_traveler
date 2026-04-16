"""Main game loop: initialization, intro sequence, win/lose conditions."""

import random

from src import input_handler, llm, ui
from src.commands import GameContext, cmd_look, dispatch
from src.creatures import generate_creatures
from src.dev_mode import DevMode
from src.drone import Drone
from src.player import Player
from src.ship_ai import ShipAI
from src.tutorial import TutorialManager
from src.world import generate_world

# Ship repair requirements by mode
REPAIR_MATERIALS = {
    "short": ["ice_crystal", "metal_shard", "bio_gel"],
    "medium": ["ice_crystal", "metal_shard", "bio_gel", "circuit_board", "power_cell"],
    "long": [
        "ice_crystal",
        "metal_shard",
        "bio_gel",
        "circuit_board",
        "power_cell",
        "thermal_paste",
        "hull_patch",
        "antenna_array",
    ],
}

def build_repair_checklist(mode: str, creatures: list | None = None) -> dict:
    """Build the repair checklist: materials only."""
    checklist = {}
    for mat in REPAIR_MATERIALS[mode]:
        checklist[f"material_{mat}"] = False
    return checklist


def check_repair_materials(ctx: GameContext):
    """Check if player has delivered required materials to ship."""
    for mat in REPAIR_MATERIALS[ctx.world_mode]:
        key = f"material_{mat}"
        if key in ctx.repair_checklist and not ctx.repair_checklist[key]:
            if ctx.player.has_item(mat) and ctx.player.location_name == "Crash Site":
                ctx.player.remove_item(mat)
                ctx.repair_checklist[key] = True
                display = mat.replace("_", " ").title()
                ui.success(f"Applied {display} to ship repairs!")


def check_win(ctx: GameContext) -> bool:
    return all(ctx.repair_checklist.values())


def check_lose(ctx: GameContext) -> bool:
    return ctx.player.food <= 0 and ctx.player.water <= 0


def show_win_sequence(ctx: GameContext):
    """Show the victory sequence."""
    ui.console.print()
    ui.console.print("[bold green]" + "=" * 60 + "[/bold green]")
    win_lines = [
        "The final component clicks into place.",
        "Your ship groans, then hums with renewed energy.",
        "",
        "Systems online. Hull integrity: stable.",
        "Fuel cells: charged. Navigation: locked.",
        "",
        "You take one last look at the frozen landscape of Enceladus.",
        "The creatures who helped you watch from a distance.",
        "",
        "The thrusters ignite. The ice beneath you melts and steams.",
        "You rise — slowly at first, then faster, breaking free",
        "of the moon's gentle gravity.",
        "",
        "Enceladus shrinks below you, a pale jewel against Saturn's rings.",
        "",
        f"Time survived: {ctx.player.hours_elapsed} hours.",
        "",
        "You made it home.",
    ]
    ui.narrate_lines(win_lines, pause=0.5)
    ui.console.print("[bold green]" + "=" * 60 + "[/bold green]")
    ui.console.print("\n[bold]MISSION COMPLETE[/bold]\n")


def show_lose_sequence(ctx: GameContext):
    """Show the game over sequence."""
    ui.console.print()
    ui.console.print("[bold red]" + "=" * 60 + "[/bold red]")
    lose_lines = [
        "Your vision blurs. The cold seeps deeper.",
        "The drone chirps a warning you can barely hear.",
        "",
        "You collapse onto the ice, exhausted and depleted.",
        "The last thing you see is Saturn's rings, shimmering above.",
        "",
        f"Time survived: {ctx.player.hours_elapsed} hours.",
        "",
        "The ice claims another visitor.",
    ]
    ui.narrate_lines(lose_lines, pause=0.5)
    ui.console.print("[bold red]" + "=" * 60 + "[/bold red]")
    ui.console.print("\n[bold]GAME OVER[/bold]\n")


def init_game(mode: str, seed: int | None = None) -> GameContext:
    """Initialize a new game and return the context."""
    world = generate_world(mode, seed)
    rng = random.Random(world["seed"])
    creatures = generate_creatures(world, rng)
    player = Player()
    drone = Drone()
    repair_checklist = build_repair_checklist(mode, creatures)
    ship_ai = ShipAI()
    tutorial = TutorialManager()
    dev_mode = DevMode()

    return GameContext(
        player=player,
        drone=drone,
        locations=world["locations"],
        creatures=creatures,
        world_seed=world["seed"],
        world_mode=mode,
        repair_checklist=repair_checklist,
        rng=rng,
        ship_ai=ship_ai,
        tutorial=tutorial,
        dev_mode=dev_mode,
    )


def game_loop(ctx: GameContext):
    """Main game loop."""
    # Create prompt_toolkit session for autocomplete
    session = input_handler.create_prompt_session(ctx)

    # Initial look
    cmd_look(ctx, "")
    ui.console.print()

    while True:
        # Check win/lose
        if check_win(ctx):
            show_win_sequence(ctx)
            break

        if check_lose(ctx):
            show_lose_sequence(ctx)
            break

        # Check if materials can be applied at crash site
        check_repair_materials(ctx)

        # Prompt with autocomplete
        location = ctx.player.location_name
        raw = input_handler.get_input(session, location)

        if raw is None:
            ui.console.print()
            ui.warn("Use 'quit' to exit.")
            continue

        if not raw:
            continue

        dispatch(ctx, raw)

        # Tutorial hint
        if ctx.tutorial and not ctx.tutorial.completed:
            hint = ctx.tutorial.check_progress(raw, ctx)
            if hint:
                ui.console.print(ctx.ship_ai.speak(hint))

        # Proactive status warnings
        if ctx.ship_ai:
            warning = ctx.ship_ai.status_report(ctx.player, ctx.drone)
            if warning:
                ui.console.print(warning)

            # Periodic objective reminder
            reminder = ctx.ship_ai.objective_reminder(ctx.repair_checklist)
            if reminder:
                ui.console.print(reminder)

        # Dev mode overlay
        if ctx.dev_mode and ctx.dev_mode.enabled:
            ctx.dev_mode.render_panel(ctx)

        # Handle load
        if ctx.should_load and ctx.loaded_state:
            state = ctx.loaded_state
            ctx.player = state["player"]
            ctx.drone = state["drone"]
            ctx.locations = state["locations"]
            ctx.creatures = state["creatures"]
            ctx.world_seed = state["world_seed"]
            ctx.world_mode = state["world_mode"]
            ctx.repair_checklist = state["repair_checklist"]
            if "ship_ai" in state:
                ctx.ship_ai = state["ship_ai"]
            if "tutorial" in state:
                ctx.tutorial = state["tutorial"]
            ctx.should_load = False
            ctx.loaded_state = None
            # Rebuild autocomplete session with new state
            session = input_handler.create_prompt_session(ctx)
            cmd_look(ctx, "")

        if ctx.should_quit:
            ui.info("Goodbye, traveler.")
            break


def main():
    """Entry point."""
    ui.show_title()
    ui.console.print()

    # Check for existing saves
    from src.save_load import list_saves, load_game

    saves = list_saves()

    choice = "new"
    if saves:
        choice = ui.prompt_choice(
            "What would you like to do?",
            ["New Game", "Load Game"],
        )

    if choice == "Load Game":
        ui.info("Available saves: " + ", ".join(saves))
        try:
            slot = ui.console.input("[bold]Load which slot? > [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            return

        state = load_game(slot)
        if state:
            # GPU/CPU mode selection for loaded games too
            gpu_info = llm.detect_gpu()
            load_gpu_mode = "cpu"
            if gpu_info["available"]:
                gpu_choice = ui.prompt_choice(
                    f"GPU detected ({gpu_info['backend']}). Choose compute mode:",
                    ["CPU + GPU (Recommended)", "CPU Only"],
                )
                if "GPU" in gpu_choice and "Only" not in gpu_choice:
                    load_gpu_mode = "gpu"
            else:
                ui.dim("No GPU acceleration detected. Using CPU only.")

            llm.load_model(gpu_mode=load_gpu_mode)

            ship_ai = state.get("ship_ai", ShipAI())
            if isinstance(ship_ai, dict):
                ship_ai = ShipAI.from_dict(ship_ai)
            ship_ai.boot_complete = True

            tutorial = state.get("tutorial", TutorialManager())
            if isinstance(tutorial, dict):
                tutorial = TutorialManager.from_dict(tutorial)

            ctx = GameContext(
                player=state["player"],
                drone=state["drone"],
                locations=state["locations"],
                creatures=state["creatures"],
                world_seed=state["world_seed"],
                world_mode=state["world_mode"],
                repair_checklist=state["repair_checklist"],
                rng=random.Random(state["world_seed"]),
                ship_ai=ship_ai,
                tutorial=tutorial,
                dev_mode=DevMode(),
            )
            game_loop(ctx)
            return
        else:
            ui.error("Failed to load. Starting new game.")

    # New game
    mode = ui.prompt_choice(
        "Choose game length:",
        ["Short (~30 min)", "Medium (~1-2 hours)", "Long (~3+ hours)"],
    )
    mode_key = mode.split()[0].lower()

    # GPU/CPU mode selection
    gpu_info = llm.detect_gpu()
    gpu_mode = "cpu"
    if gpu_info["available"]:
        gpu_choice = ui.prompt_choice(
            f"GPU detected ({gpu_info['backend']}). Choose compute mode:",
            ["CPU + GPU (Recommended)", "CPU Only"],
        )
        if "GPU" in gpu_choice and "Only" not in gpu_choice:
            gpu_mode = "gpu"
    else:
        ui.dim("No GPU acceleration detected. Using CPU only.")

    # Load LLM
    llm.load_model(gpu_mode=gpu_mode)

    ctx = init_game(mode_key)

    # Run ARIA boot sequence (replaces old show_intro)
    ctx.tutorial.run_boot_sequence(
        ctx.ship_ai,
        ctx.player,
        ctx.drone,
        ctx.locations,
        ctx.repair_checklist,
        mode_key,
    )

    game_loop(ctx)
