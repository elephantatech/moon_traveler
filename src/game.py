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


def check_win(ctx: GameContext) -> bool:
    return all(ctx.repair_checklist.values())


def check_lose(ctx: GameContext) -> bool:
    return ctx.player.food <= 0 or ctx.player.water <= 0 or ctx.player.suit_integrity <= 0


def show_win_sequence(ctx: GameContext):
    """Show the victory sequence."""
    try:
        from src import sound
        sound.play("victory")
    except Exception:
        pass
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
    ]
    ui.narrate_lines(win_lines, pause=0.5)

    # Ship launch art
    ui.console.print(ui.LAUNCH_ART)

    launch_lines = [
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
    ui.narrate_lines(launch_lines, pause=0.5)

    # Personalized creature recognition
    allies = [c for c in ctx.creatures if c.trust >= 50]
    if allies:
        ui.console.print("[bold]Those who helped you:[/bold]")
        for c in allies:
            role = c.archetype
            if c.helped_at_ship:
                ui.console.print(f"  [{c.color}]{c.name}[/{c.color}] [dim]the {role} — came to the ship[/dim]")
            elif c.trust >= 70:
                ui.console.print(f"  [{c.color}]{c.name}[/{c.color}] [dim]the {role} — a true ally[/dim]")
            else:
                ui.console.print(f"  [{c.color}]{c.name}[/{c.color}] [dim]the {role} — a friend[/dim]")
        ui.console.print()

    ui.console.print("[bold green]" + "=" * 60 + "[/bold green]")
    ui.console.print("\n[bold]MISSION COMPLETE[/bold]\n")


def show_lose_sequence(ctx: GameContext):
    """Show the game over sequence."""
    try:
        from src import sound
        sound.play("game_over")
    except Exception:
        pass
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
    creatures = generate_creatures(world, rng, required_materials=REPAIR_MATERIALS[mode])
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
            if ctx.dev_mode:
                ctx.dev_mode.debug("game_win", hours=ctx.player.hours_elapsed)
            show_win_sequence(ctx)
            break

        if check_lose(ctx):
            if ctx.dev_mode:
                ctx.dev_mode.debug("game_lose",
                    food=ctx.player.food, water=ctx.player.water,
                    suit=ctx.player.suit_integrity, hours=ctx.player.hours_elapsed)
            show_lose_sequence(ctx)
            break

        # Status bar
        loc = ctx.current_location()
        creature_here = ctx.creature_at_location(loc.name)
        followers = [c for c in ctx.creatures if c.following]
        ui.render_status_bar(
            ctx.player, ctx.drone, ctx.repair_checklist, loc.loc_type, creature_here, followers
        )

        # Prompt with autocomplete
        location = ctx.player.location_name
        raw = input_handler.get_input(session, location)

        if raw is None:
            ui.console.print()
            ui.warn("Use 'quit' to exit.")
            continue

        if not raw:
            continue

        if ctx.dev_mode:
            ctx.dev_mode.debug("command_input", raw=raw, location=ctx.player.location_name)

        dispatch(ctx, raw)

        # Tutorial hint
        if ctx.tutorial and not ctx.tutorial.completed:
            hint = ctx.tutorial.check_progress(raw, ctx)
            if hint:
                ui.console.print(ctx.ship_ai.speak(hint))

        # Proactive status warnings (ARIA — critical thresholds)
        if ctx.ship_ai:
            warning = ctx.ship_ai.status_report(ctx.player, ctx.drone)
            if warning:
                ui.console.print(warning)

            # Periodic objective reminder
            reminder = ctx.ship_ai.objective_reminder(ctx.repair_checklist)
            if reminder:
                ui.console.print(reminder)

        # Drone vitals whisper (every 10% drop, only when exploring)
        cur_loc = ctx.current_location()
        if cur_loc.loc_type != "crash_site":
            vital_msg = ctx.drone.check_vitals(ctx.player)
            if vital_msg:
                ui.console.print(vital_msg)
        else:
            # Reset tracking at crash site so it re-arms for next outing
            ctx.drone.reset_vital_tracking()

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
            import time as _time
            ctx.rng = random.Random(state["world_seed"] ^ int(_time.time()))
            if "ship_ai" in state:
                ctx.ship_ai = state["ship_ai"]
            if "tutorial" in state:
                ctx.tutorial = state["tutorial"]
            ctx.should_load = False
            ctx.loaded_state = None
            # Rebuild autocomplete session with new state
            session = input_handler.create_prompt_session(ctx)
            # Sync sound voice state with drone
            from src import sound
            sound.set_voice(ctx.drone.voice_enabled)
            cmd_look(ctx, "")

        if ctx.should_quit:
            ctx.do_auto_save()
            ui.info("Goodbye, traveler.")
            break


def main():
    """Entry point."""
    # Restore sound preference from config
    try:
        from src.config import get_sound_enabled
        if not get_sound_enabled():
            from src import sound as _snd
            _snd.disable()
    except Exception:
        pass

    ui.show_title()
    ui.console.print()

    # First-run: prompt for save location
    from src.config import is_first_run, prompt_save_location

    if is_first_run():
        prompt_save_location()

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
            # GPU/CPU mode — auto-detect from config
            from src.config import get_gpu_mode
            gpu_setting = get_gpu_mode()
            if gpu_setting == "auto":
                gpu_info = llm.detect_gpu()
                load_gpu_mode = "gpu" if gpu_info["available"] else "cpu"
            else:
                load_gpu_mode = gpu_setting

            llm.maybe_download_model()
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
                rng=random.Random(state["world_seed"] ^ int(__import__("time").time())),
                ship_ai=ship_ai,
                tutorial=tutorial,
                dev_mode=DevMode(),
            )
            # Sync sound voice state with loaded drone
            try:
                from src import sound
                sound.set_voice(ctx.drone.voice_enabled)
            except Exception:
                pass
            # Persist tutorial completion if the loaded save had it done
            if tutorial.completed:
                from src.config import set_tutorial_completed
                set_tutorial_completed()
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

    # GPU/CPU mode — auto-detect from config, no prompt
    from src.config import get_gpu_mode
    gpu_setting = get_gpu_mode()
    if gpu_setting == "auto":
        gpu_info = llm.detect_gpu()
        gpu_mode = "gpu" if gpu_info["available"] else "cpu"
    else:
        gpu_mode = gpu_setting
    ui.dim(f"Compute mode: {'CPU + GPU' if gpu_mode == 'gpu' else 'CPU only'} (change with 'config gpu cpu' or 'config gpu auto')")

    # Download model if needed, then load LLM
    llm.maybe_download_model()
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
