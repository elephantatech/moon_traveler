"""Command registry, parser, and handlers."""

import random

from src import llm, ui
from src.creatures import Creature
from src.drone import UPGRADE_EFFECTS, Drone
from src.player import Player
from src.save_load import list_saves, load_game, save_game
from src.travel import execute_travel
from src.world import Location

HELP_TEXT = """
[bold]Available Commands:[/bold]

  [cyan]look[/cyan]                 — Describe current location
  [cyan]scan[/cyan]                 — Use drone to discover nearby locations
  [cyan]gps[/cyan] / [cyan]map[/cyan]             — Show known locations with distances
  [cyan]travel[/cyan] <location>    — Travel to a known location
  [cyan]take[/cyan] <item>          — Pick up an item at current location
  [cyan]inventory[/cyan] / [cyan]inv[/cyan]       — Show your inventory
  [cyan]talk[/cyan] <creature>      — Talk to a creature here (LLM dialogue)
  [cyan]give[/cyan] <item> to <creature> — Give an item to build trust
  [cyan]drone[/cyan]                — Show drone status and upgrades
  [cyan]upgrade[/cyan] <component>  — Install a drone upgrade from inventory
  [cyan]status[/cyan]               — Show player status (food, water, time)
  [cyan]ship[/cyan]                 — Show ship repair progress
  [cyan]save[/cyan] [slot]          — Save game (default slot: 'manual')
  [cyan]load[/cyan] [slot]          — Load a saved game
  [cyan]dev[/cyan]                  — Toggle developer diagnostics panel
  [cyan]help[/cyan]                 — Show this help message
  [cyan]quit[/cyan] / [cyan]exit[/cyan]           — Exit game
"""


CHAT_HELP_TEXT = """
[bold]ARIA Communicator — Help[/bold]

  [cyan]/end[/cyan], [cyan]/bye[/cyan], [cyan]/quit[/cyan], [cyan]bye[/cyan]   — Disconnect from conversation
  [cyan]/?[/cyan], [cyan]/help[/cyan]               — Show this help
  [cyan]/<command>[/cyan]              — Run a game command (e.g. /status, /inventory, /look)
  [cyan]/give[/cyan] <item> to <name> — Give an item to this creature
  [dim]Anything without a / prefix is sent as dialogue through the ARIA translator.[/dim]
"""


class GameContext:
    """Holds all mutable game state, passed to command handlers."""

    def __init__(
        self,
        player: Player,
        drone: Drone,
        locations: list[Location],
        creatures: list[Creature],
        world_seed: int,
        world_mode: str,
        repair_checklist: dict,
        rng: random.Random,
        ship_ai=None,
        tutorial=None,
        dev_mode=None,
    ):
        self.player = player
        self.drone = drone
        self.locations = locations
        self.creatures = creatures
        self.world_seed = world_seed
        self.world_mode = world_mode
        self.repair_checklist = repair_checklist
        self.rng = rng
        self.ship_ai = ship_ai
        self.tutorial = tutorial
        self.dev_mode = dev_mode
        self.should_quit = False
        self.should_load = False
        self.loaded_state: dict | None = None

    def current_location(self) -> Location:
        for loc in self.locations:
            if loc.name == self.player.location_name:
                return loc
        return self.locations[0]

    def find_location(self, name: str) -> Location | None:
        name_lower = name.lower()
        for loc in self.locations:
            if loc.name.lower() == name_lower:
                return loc
        # Partial match
        for loc in self.locations:
            if name_lower in loc.name.lower():
                return loc
        return None

    def creature_at_location(self, location_name: str) -> Creature | None:
        for c in self.creatures:
            if c.location_name == location_name:
                return c
        return None

    def find_creature(self, name: str) -> Creature | None:
        name_lower = name.lower()
        for c in self.creatures:
            if c.name.lower() == name_lower:
                return c
        for c in self.creatures:
            if name_lower in c.name.lower():
                return c
        return None

    def do_auto_save(self):
        from src.save_load import auto_save

        auto_save(
            self.player,
            self.drone,
            self.locations,
            self.creatures,
            self.world_seed,
            self.world_mode,
            self.repair_checklist,
            self.ship_ai,
            self.tutorial,
        )


def parse_command(raw: str) -> tuple[str, str]:
    """Parse raw input into (command, args)."""
    raw = raw.strip()
    if not raw:
        return "", ""
    parts = raw.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args


# --- Command handlers ---


def cmd_help(ctx: GameContext, args: str):
    ui.console.print(HELP_TEXT)


def cmd_look(ctx: GameContext, args: str):
    loc = ctx.current_location()
    creature = ctx.creature_at_location(loc.name)
    creature_name = None
    if creature:
        creature_name = f"[{creature.color}]{creature.name}[/{creature.color}] ({creature.species})"
    items_display = [i.replace("_", " ").title() for i in loc.items]
    ui.show_location(loc.name, loc.loc_type, loc.description, items_display, creature_name)

    if loc.food_source:
        ui.info("This location has a renewable food source.")
    if loc.water_source:
        ui.info("This location has a water source.")


def cmd_scan(ctx: GameContext, args: str):
    drone = ctx.drone
    if not drone.can_scan():
        ui.error("Drone battery too low to scan. Return to crash site to recharge.")
        return

    drone.use_battery(drone.scan_cost())
    cur = ctx.current_location()
    discovered = []
    for loc in ctx.locations:
        if loc.name in ctx.player.known_locations:
            continue
        dist = cur.distance_to(loc.x, loc.y)
        if dist <= drone.scanner_range:
            loc.discovered = True
            ctx.player.discover_location(loc.name)
            discovered.append((loc.name, loc.loc_type, dist))

    ui.loading_spinner("Scanning surroundings...", 1.0)

    if discovered:
        ui.success(f"Discovered {len(discovered)} new location(s):")
        for name, loc_type, dist in discovered:
            type_str = loc_type.replace("_", " ")
            ui.console.print(f"  [cyan]{name}[/cyan] ({type_str}) — {dist:.1f} km away")
        if ctx.ship_ai:
            ui.console.print(
                ctx.ship_ai.speak(
                    f"Scan complete. {len(discovered)} new signature{'s' if len(discovered) != 1 else ''} logged."
                )
            )
    else:
        ui.info("No new locations found within scanner range.")
        if ctx.ship_ai:
            ui.console.print(ctx.ship_ai.speak("No new signatures in range. Try moving to a different location."))
    ui.dim(f"Drone battery: {drone.battery:.0f}%")


def cmd_gps(ctx: GameContext, args: str):
    cur = ctx.current_location()
    loc_data = []
    for loc in ctx.locations:
        if loc.name not in ctx.player.known_locations:
            continue
        dist = cur.distance_to(loc.x, loc.y)
        loc_data.append(
            {
                "name": loc.name,
                "type": loc.loc_type,
                "distance": dist,
                "x": loc.x,
                "y": loc.y,
            }
        )
    ui.show_gps(loc_data, cur.x, cur.y)


def cmd_travel(ctx: GameContext, args: str):
    if not args:
        ui.error("Travel where? Usage: travel <location name>")
        return

    dest = ctx.find_location(args)
    if not dest:
        ui.error(f"Unknown location: '{args}'. Use 'gps' to see known locations.")
        return

    if dest.name not in ctx.player.known_locations:
        ui.error(f"You haven't discovered '{dest.name}' yet. Use 'scan' first.")
        return

    if dest.name == ctx.player.location_name:
        ui.info("You're already here.")
        return

    cur = ctx.current_location()

    # Clear screen before travel
    ui.console.clear()

    messages = execute_travel(ctx.player, ctx.drone, dest, cur, ctx.rng, ctx.ship_ai, ctx.locations)
    for msg in messages:
        ui.console.print(msg)

    ui.console.print()

    # Prompt to look around on arrival
    ui.console.print("[dim]Type [cyan]look[/cyan] to observe your surroundings, or enter any command.[/dim]")

    # Check hostile creature
    creature = ctx.creature_at_location(dest.name)
    if creature and creature.disposition == "hostile" and creature.trust < 35:
        ui.console.print(f"\n[bold red]{creature.name} blocks your path aggressively![/bold red]")
        creature.chased_away = True

    ctx.do_auto_save()


def cmd_take(ctx: GameContext, args: str):
    if not args:
        ui.error("Take what? Usage: take <item>")
        return

    loc = ctx.current_location()
    item_name = args.lower().replace(" ", "_")

    # Check for hostile creature blocking
    creature = ctx.creature_at_location(loc.name)
    if creature and creature.disposition == "hostile" and creature.trust < 20:
        ui.error(f"{creature.name} won't let you take anything here.")
        return

    if item_name in loc.items:
        # Check cargo capacity
        if ctx.player.total_items >= ctx.drone.cargo_capacity:
            ui.error(f"Inventory full! Drone cargo capacity: {ctx.drone.cargo_capacity}")
            return
        loc.items.remove(item_name)
        ctx.player.add_item(item_name)
        display = item_name.replace("_", " ").title()
        ui.success(f"Picked up: {display}")
    else:
        ui.error(f"No '{args}' here. Use 'look' to see available items.")


def cmd_inventory(ctx: GameContext, args: str):
    ui.show_inventory(ctx.player.inventory)


def _interjection_probability(creature, exchange_count: int) -> float:
    """How likely the drone is to whisper advice during a creature conversation."""
    if exchange_count <= 1:
        return 0.8  # first exchange — establish the pattern
    if creature.disposition == "hostile" and creature.trust_level == "low":
        return 0.6
    if creature.trust_level == "low":
        return 0.4
    if creature.trust_level == "medium":
        return 0.3
    return 0.15  # high trust — player has it under control


def cmd_talk(ctx: GameContext, args: str):
    loc = ctx.current_location()
    creature = ctx.creature_at_location(loc.name)

    if not creature:
        ui.info("There's no one to talk to here.")
        return

    if args and creature.name.lower() != args.lower() and args.lower() not in creature.name.lower():
        ui.error(f"'{args}' is not here. {creature.name} is at this location.")
        return

    # Hostile and low trust — chase away
    if creature.disposition == "hostile" and creature.trust < 15:
        response = llm.generate_response(creature, "(approaching)", ctx.drone.translation_quality)
        ui.creature_speak(creature.name, response, creature.color)
        ui.warn(f"{creature.name} forces you to back away. Build trust by giving gifts first.")
        return

    ui.console.print(
        f"\n[bold]── ARIA Communicator ── [{creature.color}]{creature.name}[/{creature.color}]"
        f" ({creature.species}, {creature.archetype})[/bold]"
    )
    ui.console.print(
        f"[dim]Trust: {creature.trust}/100 ({creature.trust_level})"
        " — 'bye' or '/end' to disconnect | /? for help[/dim]\n"
    )

    # Drone initial coaching tip
    initial_tip = ctx.drone.get_interaction_advice(creature, ctx.rng)
    if initial_tip:
        ui.console.print(initial_tip)
        ui.console.print()

    exchange_count = 0

    while True:
        try:
            player_input = ui.console.input("[bold]You>[/bold] ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not player_input:
            continue
        if player_input.lower() in ("bye", "leave", "/end", "/bye", "/quit", "/exit"):
            ui.info(f"You step away from {creature.name}.")
            break

        if player_input.lower() in ("/?", "/help"):
            ui.console.print(CHAT_HELP_TEXT)
            continue

        # Allow game commands during conversation — only via "/" prefix
        # e.g. "/status", "/inventory", "/look", "/travel Frost Ridge"
        if player_input.startswith("/"):
            slash_input = player_input[1:]  # strip the "/"
            first_word = slash_input.split()[0].lower() if slash_input else ""
            if first_word not in COMMANDS:
                ui.error(f"Unknown command: '/{first_word}'. Type /? for help.")
                continue
            handler = COMMANDS[first_word]
            _, cmd_args = parse_command(slash_input)
            # Commands that leave the conversation
            if handler in (cmd_travel, cmd_quit):
                ui.info(f"You step away from {creature.name}.")
                handler(ctx, cmd_args)
                break
            # Block re-entering talk
            if handler in (cmd_talk,):
                ui.info("You're already in a conversation.")
                continue
            handler(ctx, cmd_args)
            continue

        creature.add_message("user", player_input)
        response = llm.generate_response(creature, player_input, ctx.drone.translation_quality)
        creature.add_message("assistant", response)

        # Drone translation frame (always on first exchange, ~40% after)
        show_frame = exchange_count == 0 or ctx.rng.random() < 0.4
        if show_frame:
            frame = ctx.drone.get_translation_frame(ctx.rng)
            if frame:
                ui.console.print(frame)

        ui.creature_speak(creature.name, response, creature.color)

        # Trust gain from conversation
        creature.add_trust(3)
        exchange_count += 1

        # Drone private advice (NOT added to creature conversation history)
        interjection_chance = _interjection_probability(creature, exchange_count)
        if ctx.rng.random() < interjection_chance:
            advice = ctx.drone.get_interaction_advice(creature, ctx.rng)
            if advice:
                ui.console.print(advice)

        # High trust — creature might reveal info
        if creature.trust >= 70 and not creature.has_helped_repair:
            if creature.knows_food_source and creature.knows_food_source not in ctx.player.known_locations:
                ctx.player.discover_location(creature.knows_food_source)
                ui.success(f"{creature.name} revealed a food source: {creature.knows_food_source}")
            if creature.knows_water_source and creature.knows_water_source not in ctx.player.known_locations:
                ctx.player.discover_location(creature.knows_water_source)
                ui.success(f"{creature.name} revealed a water source: {creature.knows_water_source}")

        ui.console.print()

    # ARIA trust commentary after conversation
    if ctx.ship_ai and creature:
        if creature.trust >= 70:
            ui.console.print(ctx.ship_ai.speak(f"{creature.name} appears highly cooperative. Trust is strong."))
        elif creature.trust >= 35:
            ui.console.print(ctx.ship_ai.speak(f"{creature.name} is warming up to you, Commander."))

    ctx.do_auto_save()


def cmd_give(ctx: GameContext, args: str):
    if not args or " to " not in args.lower():
        ui.error("Usage: give <item> to <creature>")
        return

    # Split on " to " (case insensitive)
    lower = args.lower()
    to_idx = lower.index(" to ")
    item_part = args[:to_idx].strip().lower().replace(" ", "_")
    creature_part = args[to_idx + 4 :].strip()

    loc = ctx.current_location()
    creature = ctx.creature_at_location(loc.name)

    if not creature:
        ui.error("There's no creature here to give items to.")
        return

    if creature_part.lower() not in creature.name.lower():
        ui.error(f"'{creature_part}' is not here.")
        return

    if not ctx.player.has_item(item_part):
        display = item_part.replace("_", " ").title()
        ui.error(f"You don't have '{display}' in your inventory.")
        return

    ctx.player.remove_item(item_part)
    display = item_part.replace("_", " ").title()
    ui.success(f"You give {display} to {creature.name}.")

    # Trust increase from gift
    trust_gain = 15
    if creature.disposition == "hostile":
        trust_gain = 10
    creature.add_trust(trust_gain)
    ui.info(f"{creature.name}'s trust: {creature.trust}/100 ({creature.trust_level})")

    # At high trust, creature shares materials and info
    if creature.trust >= 70 and not creature.has_helped_repair:
        creature.has_helped_repair = True

        # Give materials
        for mat in creature.can_give_materials:
            ctx.player.add_item(mat)
            mat_display = mat.replace("_", " ").title()
            ui.success(f"{creature.name} gives you: {mat_display}")


def cmd_drone(ctx: GameContext, args: str):
    ui.show_drone_status(ctx.drone.to_dict(), title="ARIA Scout Drone")


def cmd_upgrade(ctx: GameContext, args: str):
    if not args:
        ui.error("Upgrade with what? Usage: upgrade <component>")
        ui.info("Upgrade components: " + ", ".join(f"{k.replace('_', ' ').title()}" for k in UPGRADE_EFFECTS))
        return

    upgrade_name = args.lower().replace(" ", "_")
    if upgrade_name not in UPGRADE_EFFECTS:
        ui.error(f"Unknown upgrade: '{args}'")
        ui.info("Valid upgrades: " + ", ".join(k.replace("_", " ").title() for k in UPGRADE_EFFECTS))
        return

    if not ctx.player.has_item(upgrade_name):
        display = upgrade_name.replace("_", " ").title()
        ui.error(f"You don't have a {display} in your inventory.")
        return

    ctx.player.remove_item(upgrade_name)
    result = ctx.drone.apply_upgrade(upgrade_name)
    display = upgrade_name.replace("_", " ").title()
    ui.success(f"Installed {display}!")
    if result:
        ui.info(f"Effect: {result}")


def cmd_status(ctx: GameContext, args: str):
    ui.show_status(
        ctx.player.food,
        ctx.player.water,
        ctx.player.hours_elapsed,
        ctx.player.location_name,
        ctx.repair_checklist,
        ctx.player.inventory,
        ctx.player.suit_integrity,
    )


def cmd_ship(ctx: GameContext, args: str):
    ui.show_ship_repair(ctx.repair_checklist)

    at_crash = ctx.player.location_name == "Crash Site"

    if not at_crash:
        ui.dim("Travel to the Crash Site to install materials and repair your suit.")
        return

    # --- At Crash Site: interactive repair options ---
    has_actions = False

    # Check for installable materials
    from src.game import REPAIR_MATERIALS

    installable = []
    for mat in REPAIR_MATERIALS[ctx.world_mode]:
        key = f"material_{mat}"
        if key in ctx.repair_checklist and not ctx.repair_checklist[key]:
            if ctx.player.has_item(mat):
                installable.append(mat)

    if installable:
        has_actions = True
        ui.console.print("\n[bold]Materials ready to install:[/bold]")
        for mat in installable:
            display = mat.replace("_", " ").title()
            ui.console.print(f"  [yellow]{display}[/yellow]")
        ui.console.print()
        try:
            confirm = ui.console.input("[bold]Install all available materials? (y/n) > [/bold]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if confirm in ("y", "yes"):
            for mat in installable:
                key = f"material_{mat}"
                ctx.player.remove_item(mat)
                ctx.repair_checklist[key] = True
                display = mat.replace("_", " ").title()
                ui.success(f"Installed {display} into ship repairs!")

    # Suit repair using drone battery
    if ctx.player.suit_integrity < 100 and ctx.drone.battery >= 10:
        has_actions = True
        repair_amount = min(100 - ctx.player.suit_integrity, ctx.drone.battery * 2)
        battery_cost = repair_amount / 2
        ui.console.print(
            f"\n[bold]Suit Repair Available:[/bold] "
            f"Suit at {ctx.player.suit_integrity:.0f}% — "
            f"can restore up to {repair_amount:.0f}% using {battery_cost:.0f}% drone battery"
        )
        try:
            confirm = ui.console.input("[bold]Repair suit? (y/n) > [/bold]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if confirm in ("y", "yes"):
            ctx.drone.use_battery(battery_cost)
            ctx.player.suit_integrity = min(100, ctx.player.suit_integrity + repair_amount)
            ui.success(f"Suit repaired to {ctx.player.suit_integrity:.0f}%! (Battery: {ctx.drone.battery:.0f}%)")
    elif ctx.player.suit_integrity < 100 and ctx.drone.battery < 10:
        ui.warn("Drone battery too low to repair suit. Recharge first.")

    if not has_actions and all(ctx.repair_checklist.values()) and ctx.player.suit_integrity >= 100:
        ui.success("Ship and suit are in top condition!")


def cmd_save(ctx: GameContext, args: str):
    slot = args.strip() if args.strip() else "manual"
    save_game(
        slot,
        ctx.player,
        ctx.drone,
        ctx.locations,
        ctx.creatures,
        ctx.world_seed,
        ctx.world_mode,
        ctx.repair_checklist,
        ctx.ship_ai,
        ctx.tutorial,
    )


def cmd_load(ctx: GameContext, args: str):
    saves = list_saves()
    if not saves:
        ui.info("No save files found.")
        return

    slot = args.strip() if args.strip() else None
    if not slot:
        ui.info("Available saves: " + ", ".join(saves))
        try:
            slot = ui.console.input("[bold]Load which slot? > [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            return

    state = load_game(slot)
    if state:
        ctx.should_load = True
        ctx.loaded_state = state


def cmd_dev(ctx: GameContext, args: str):
    if ctx.dev_mode:
        ctx.dev_mode.toggle()
        state = "ON" if ctx.dev_mode.enabled else "OFF"
        ui.dim(f"Dev mode: {state}")
        if ctx.dev_mode.enabled:
            ctx.dev_mode.render_panel(ctx)
    else:
        ui.error("Dev mode not available.")


def cmd_quit(ctx: GameContext, args: str):
    ui.warn("Are you sure? (y/n)")
    try:
        confirm = ui.console.input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if confirm in ("y", "yes"):
        ctx.should_quit = True


# Command dispatch table
COMMANDS = {
    "help": cmd_help,
    "look": cmd_look,
    "l": cmd_look,
    "scan": cmd_scan,
    "gps": cmd_gps,
    "map": cmd_gps,
    "travel": cmd_travel,
    "go": cmd_travel,
    "take": cmd_take,
    "get": cmd_take,
    "pick": cmd_take,
    "inventory": cmd_inventory,
    "inv": cmd_inventory,
    "i": cmd_inventory,
    "talk": cmd_talk,
    "speak": cmd_talk,
    "give": cmd_give,
    "drone": cmd_drone,
    "upgrade": cmd_upgrade,
    "status": cmd_status,
    "ship": cmd_ship,
    "repair": cmd_ship,
    "save": cmd_save,
    "load": cmd_load,
    "dev": cmd_dev,
    "devmode": cmd_dev,
    "quit": cmd_quit,
    "exit": cmd_quit,
}


def dispatch(ctx: GameContext, raw_input: str):
    """Parse and execute a command."""
    cmd, args = parse_command(raw_input)
    if not cmd:
        return

    handler = COMMANDS.get(cmd)
    if handler:
        handler(ctx, args)
    else:
        ui.error(f"Unknown command: '{cmd}'. Type 'help' for available commands.")
