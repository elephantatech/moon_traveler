"""Main game loop: initialization, intro sequence, win/lose conditions."""

import random

from src import llm, ui
from src.commands import GameContext, cmd_look, dispatch
from src.creatures import generate_creatures
from src.dev_mode import DevMode
from src.drone import Drone
from src.player import Player
from src.ship_ai import ShipAI
from src.tutorial import TutorialManager
from src.world import generate_world

# Escort requirements by mode — creatures that must help at the ship
ESCORT_REQUIREMENTS = {
    "short": 1,
    "medium": 2,
    "long": 3,
    "brutal": 4,
}

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
    "brutal": [
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
    # Filter out non-material keys (e.g. _escorts_completed sentinel from save/load)
    material_values = [v for k, v in ctx.repair_checklist.items() if not k.startswith("_")]
    if not material_values or not all(material_values):
        return False
    req = ESCORT_REQUIREMENTS.get(ctx.world_mode, 1)
    return ctx.escorts_completed >= req


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

    # Post-game stats screen and leaderboard
    ui.render_stats_screen(ctx.stats, ctx, won=True)
    _record_to_leaderboard(ctx, won=True)

    return True  # Signal game ended


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

    # Post-game stats screen and leaderboard
    ui.render_stats_screen(ctx.stats, ctx, won=False)
    _record_to_leaderboard(ctx, won=False)

    return True  # Signal game ended


def _record_to_leaderboard(ctx: GameContext, won: bool):
    """Record the game result to the local leaderboard."""
    from src.save_load import record_score

    score, grade = ctx.stats.calculate_score(ctx.player.hours_elapsed, ctx.creatures, ctx.repair_checklist)
    allies = sum(1 for c in ctx.creatures if c.trust >= 50)
    record_score(
        score=score,
        grade=grade,
        won=won,
        game_mode=ctx.world_mode,
        hours_elapsed=ctx.player.hours_elapsed,
        real_time_seconds=int(ctx.stats.elapsed_seconds),
        creatures_befriended=allies,
        world_seed=ctx.world_seed,
        player_name=ctx.player.name,
    )


def _prompt_play_again() -> bool:
    """Ask if the player wants to start a new game. Returns True to play again."""
    ui.console.print()
    try:
        answer = ui.console.input("[bold]Play again? (y/n) > [/bold] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def apply_super_mode(ctx: GameContext):
    """Cheat mode: max trust, all repair materials, fully upgraded drone."""
    from src.drone import UPGRADE_EFFECTS

    # Max trust on all creatures
    for c in ctx.creatures:
        c.trust = 100
        c.disposition = "friendly"

    # Add all repair materials to inventory (skip if already in inventory or storage)
    for key in ctx.repair_checklist:
        mat = key.replace("material_", "")
        in_inv = ctx.player.has_item(mat)
        in_storage = ctx.player.ship_storage.get(mat, 0) > 0
        if not in_inv and not in_storage:
            ctx.player.add_item(mat)

    # Max out drone upgrades
    for upgrade_name in UPGRADE_EFFECTS:
        if upgrade_name not in ctx.drone.upgrades_installed:
            ctx.drone.apply_upgrade(upgrade_name)

    # Full resources
    ctx.player.food = 100.0
    ctx.player.water = 100.0
    ctx.player.suit_integrity = 100.0
    ctx.drone.recharge()

    ui.console.print("[bold magenta]SUPER MODE ACTIVATED[/bold magenta]")
    ui.dim("  All creatures trust you. All repair materials in inventory.")
    ui.dim("  Drone fully upgraded. Resources maxed.")
    ui.console.print()


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

    # Wire dev mode into LLM for performance logging
    from src import llm as _llm_mod

    _llm_mod.set_dev_mode(dev_mode)

    ctx = GameContext(
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
    return ctx


def game_loop(ctx: GameContext) -> bool:
    """Main game loop. Returns True if game ended (win/lose), False if player quit."""
    if ui._bridge is None:
        raise RuntimeError("game_loop() requires TUI bridge — launch via play_tui.py")

    # Initial look
    cmd_look(ctx, "")
    ui.console.print()

    while True:
        # Check win/lose
        if check_win(ctx):
            if ctx.dev_mode:
                ctx.dev_mode.debug("game_win", hours=ctx.player.hours_elapsed)
            show_win_sequence(ctx)
            return True

        if check_lose(ctx):
            if ctx.dev_mode:
                ctx.dev_mode.debug(
                    "game_lose",
                    food=ctx.player.food,
                    water=ctx.player.water,
                    suit=ctx.player.suit_integrity,
                    hours=ctx.player.hours_elapsed,
                )
            show_lose_sequence(ctx)
            return True

        # Status bar
        loc = ctx.current_location()
        creature_here = ctx.creature_at_location(loc.name)
        followers = [c for c in ctx.creatures if c.following]
        ui.render_status_bar(ctx.player, ctx.drone, ctx.repair_checklist, loc.loc_type, creature_here, followers)

        # Get player command via TUI bridge
        location = ctx.player.location_name
        raw = ui._bridge.get_command(location)

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
                from src import animations

                animations.drone_transmit("alert")
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
            checklist = state["repair_checklist"]
            raw_escorts = checklist.pop("_escorts_completed", 0)
            max_escorts = max(ESCORT_REQUIREMENTS.values())
            ctx.escorts_completed = max(0, min(int(raw_escorts), max_escorts))
            ctx.repair_checklist = checklist
            import time as _time

            ctx.rng = random.Random(state["world_seed"] ^ int(_time.time()))
            if "ship_ai" in state:
                ctx.ship_ai = state["ship_ai"]
            if "tutorial" in state:
                ctx.tutorial = state["tutorial"]
            ctx.should_load = False
            ctx.loaded_state = None
            # Sync sound voice state with drone
            from src import sound

            sound.set_voice(ctx.drone.voice_enabled)
            cmd_look(ctx, "")

        if ctx.should_quit:
            ctx.do_auto_save()
            ui.info("Goodbye, traveler.")
            return False


def _parse_flags() -> tuple[bool, bool, bool, bool]:
    """Parse command-line flags."""
    import sys

    dev_flag = "--dev" in sys.argv
    super_flag = "--super" in sys.argv
    upgrade_flag = "--upgrade" in sys.argv
    no_anim_flag = "--disable-animation" in sys.argv
    return dev_flag, super_flag, upgrade_flag, no_anim_flag


def _stderr(msg):
    """Write debug message to stderr (bypasses TUI, always visible)."""
    import sys as _sys

    if "--dev" in _sys.argv:
        print(f"[DEBUG] {msg}", file=_sys.stderr, flush=True)


def main():
    """Entry point. Runs game sessions in a loop (play-again restarts without recursion)."""
    dev_flag, super_flag, upgrade_flag, no_anim_flag = _parse_flags()
    _stderr(f"main() started. flags: dev={dev_flag} super={super_flag} upgrade={upgrade_flag} no_anim={no_anim_flag}")

    # --upgrade: check for updates and exit
    if upgrade_flag:
        from src.upgrade import run_upgrade

        run_upgrade()
        return

    # Restore sound preference from config
    try:
        from src.config import get_sound_enabled

        if not get_sound_enabled():
            from src import sound as _snd

            _snd.disable()
    except Exception:
        pass

    # Disable animations if requested via CLI flag
    if no_anim_flag:
        try:
            from src import animations

            animations.force_disable()
        except Exception:
            pass

    # First-run: prompt for save location
    from src.config import is_first_run, prompt_save_location

    if is_first_run():
        prompt_save_location()

    # Play-again loop — iterative, no recursion, no LLM reload
    while True:
        game_ended = _run_session(dev_flag, super_flag)
        if not (game_ended and _prompt_play_again()):
            break


def _run_session(dev_flag: bool, super_flag: bool) -> bool:
    """Run a single game session (new or loaded). Returns True if game ended (win/lose)."""
    _stderr("_run_session() started")
    from src.save_load import list_saves, load_game

    saves = list_saves()
    _stderr(f"saves found: {saves}")

    choice = "new"
    if saves:
        choice = ui.prompt_choice(
            "What would you like to do?",
            ["New Game", "Load Game"],
        )
    _stderr(f"choice: {choice}")

    if choice == "Load Game":
        ui.info("Available saves: " + ", ".join(saves))
        try:
            slot = ui.console.input("[bold]Load which slot? > [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            return False

        state = load_game(slot)
        if state:
            _ensure_llm_loaded(dev_flag=dev_flag)

            ship_ai = state.get("ship_ai", ShipAI())
            if isinstance(ship_ai, dict):
                ship_ai = ShipAI.from_dict(ship_ai)
            ship_ai.boot_complete = True

            tutorial = state.get("tutorial", TutorialManager())
            if isinstance(tutorial, dict):
                tutorial = TutorialManager.from_dict(tutorial)

            load_checklist = state["repair_checklist"]
            raw_load_escorts = load_checklist.pop("_escorts_completed", 0)
            load_escorts = max(0, min(int(raw_load_escorts), max(ESCORT_REQUIREMENTS.values())))

            ctx = GameContext(
                player=state["player"],
                drone=state["drone"],
                locations=state["locations"],
                creatures=state["creatures"],
                world_seed=state["world_seed"],
                world_mode=state["world_mode"],
                repair_checklist=load_checklist,
                rng=random.Random(state["world_seed"] ^ int(__import__("time").time())),
                ship_ai=ship_ai,
                tutorial=tutorial,
                dev_mode=DevMode(),
            )
            ctx.escorts_completed = load_escorts
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
            # Apply command-line flags on load
            if dev_flag and ctx.dev_mode:
                ctx.dev_mode.toggle()
            if super_flag:
                apply_super_mode(ctx)
            # Derive easter egg state from loaded storage
            from src.difficulty import check_junk_easter_egg

            ctx.easter_egg_announced = check_junk_easter_egg(ctx.player, ctx.world_mode)
            # Wire Textual autocomplete
            try:
                ui._bridge._app.call_from_thread(ui._bridge._app.set_suggester, ctx)
            except Exception as e:
                ui.dim(f"(autocomplete unavailable: {e})")
            return game_loop(ctx)
        else:
            ui.error("Failed to load. Starting new game.")

    # New game
    _stderr("prompting for game mode...")
    mode = ui.prompt_choice(
        "Choose game length:",
        ["Easy (~30 min)", "Medium (~1-2 hours)", "Hard (~3+ hours)", "Brutal (~5+ hours)"],
    )
    _mode_map = {"easy": "short", "medium": "medium", "hard": "long", "brutal": "brutal"}
    mode_key = _mode_map.get(mode.split()[0].lower(), "short")
    _stderr(f"mode selected: {mode} -> {mode_key}")

    # Prompt for player name
    _stderr("prompting for player name...")
    try:
        raw_name = ui.console.input("[bold]Enter your name (Enter for 'Commander'): [/bold]").strip()
        player_name = _sanitize_player_name(raw_name)
    except (EOFError, KeyboardInterrupt):
        player_name = "Commander"
    _stderr(f"player name: {player_name}")

    # Clear the mode selection UI before boot sequence
    _stderr("clearing screen...")
    ui.console.clear()

    _stderr("calling _ensure_llm_loaded()...")
    _ensure_llm_loaded(dev_flag=dev_flag)
    _stderr(f"LLM loaded. is_available={llm.is_available()}")

    _stderr("calling init_game()...")
    ctx = init_game(mode_key)
    ctx.player.name = player_name
    _stderr(f"game initialized. locations={len(ctx.locations)}, creatures={len(ctx.creatures)}")

    # Apply command-line flags
    if dev_flag and ctx.dev_mode:
        ctx.dev_mode.toggle()
    if super_flag:
        apply_super_mode(ctx)

    # Wire Textual autocomplete
    try:
        ui._bridge._app.call_from_thread(ui._bridge._app.set_suggester, ctx)
    except Exception as e:
        ui.dim(f"(autocomplete unavailable: {e})")

    # Run ARIA boot sequence (replaces old show_intro)
    _stderr("running boot sequence...")
    ctx.tutorial.run_boot_sequence(
        ctx.ship_ai,
        ctx.player,
        ctx.drone,
        ctx.locations,
        ctx.repair_checklist,
        mode_key,
    )
    _stderr("boot sequence done. entering game loop...")

    return game_loop(ctx)


def _sanitize_player_name(raw: str) -> str:
    """Sanitize player name: strip markup/format chars, max 20 chars, default Commander."""
    import re

    name = raw.strip()[:20]
    # Remove format/markup chars and collapse whitespace (prevents prompt injection via newlines)
    name = re.sub(r"[\r\n\t]", " ", name)
    name = re.sub(r"[{}\[\]%]", "", name).strip()
    return name if name else "Commander"


def _ensure_llm_loaded(dev_flag: bool = False):
    """Load the LLM model if not already loaded. Skips reload on play-again."""
    if llm.is_available():
        _stderr("LLM already loaded, skipping")
        return
    from src.config import get_gpu_mode

    _stderr(f"_LLAMA_AVAILABLE = {llm._LLAMA_AVAILABLE}")
    if not llm._LLAMA_AVAILABLE:
        _stderr("llama-cpp-python not available")
        ui.warn("llama-cpp-python not installed. Using fallback dialogue.")
        return
    gpu_setting = get_gpu_mode()
    _stderr(f"gpu_setting = {gpu_setting}")
    if gpu_setting == "auto":
        try:
            _stderr("detect_gpu() starting...")
            gpu_info = llm.detect_gpu()
            gpu_mode = "gpu" if gpu_info["available"] else "cpu"
            _stderr(f"detect_gpu() done: {gpu_info}, mode={gpu_mode}")
        except Exception as e:
            gpu_mode = "cpu"
            _stderr(f"detect_gpu() FAILED: {e}")
    else:
        gpu_mode = gpu_setting
    _stderr("maybe_download_model() starting...")
    llm.maybe_download_model()
    _stderr("load_model() starting...")
    llm.load_model(gpu_mode=gpu_mode, quiet=True)
    _stderr(f"load_model() done. is_available={llm.is_available()}")
