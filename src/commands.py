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
  [cyan]escort[/cyan]               — Ask a creature to travel with you
  [cyan]drone[/cyan]                — Show drone status and upgrades
  [cyan]upgrade[/cyan] <component>  — Install a drone upgrade from inventory
  [cyan]status[/cyan]               — Show player status (food, water, time)
  [cyan]ship[/cyan]                 — Ship bays menu (storage, kitchen, charging, medical, repair)
  [cyan]save[/cyan] [slot]          — Save game (default slot: 'manual')
  [cyan]load[/cyan] [slot]          — Load a saved game
  [cyan]clear[/cyan] / [cyan]cls[/cyan]          — Clear the screen
  [cyan]config[/cyan]               — Show/change game settings (e.g. save path)
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
        """Find a resident (non-following) creature at a location."""
        for c in self.creatures:
            if c.location_name == location_name and not c.following:
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
    candidates = []
    for loc in ctx.locations:
        if loc.name in ctx.player.known_locations:
            continue
        dist = cur.distance_to(loc.x, loc.y)
        if dist <= drone.scanner_range:
            candidates.append((loc, dist))

    # Discover up to 3 closest locations per scan
    candidates.sort(key=lambda x: x[1])
    discovered = []
    for loc, dist in candidates[:3]:
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

    # Move any following creatures to the destination
    for c in ctx.creatures:
        if c.following:
            c.location_name = dest.name
            ui.console.print(f"  [{c.color}]{c.name}[/{c.color}] [dim]travels with you.[/dim]")

    # When arriving at crash site with companions, offer help (once per escort)
    if dest.loc_type == "crash_site":
        new_companions = [c for c in ctx.creatures if c.following and not c.helped_at_ship]
        if new_companions:
            _companions_help_at_ship(ctx, new_companions)

    # Warn about hostile creature at destination
    creature = ctx.creature_at_location(dest.name)
    if creature and creature.disposition == "hostile" and creature.trust < 35 and not creature.following:
        ui.console.print(f"\n[bold red]{creature.name} blocks your path aggressively![/bold red]")

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
        raw_response = llm.generate_response(creature, player_input, ctx.drone.translation_quality)

        # Parse action tags from LLM response (e.g. [GIVE_WATER], [HEAL])
        response, actions = llm.parse_actions(raw_response)
        creature.add_message("assistant", response)

        # Drone translation frame (always on first exchange, ~40% after)
        show_frame = exchange_count == 0 or ctx.rng.random() < 0.4
        if show_frame:
            frame = ctx.drone.get_translation_frame(ctx.rng)
            if frame:
                ui.console.print(frame)

        ui.creature_speak(creature.name, response, creature.color)

        # Apply any creature actions (give water/food/materials, heal, repair suit)
        if actions:
            action_msgs = llm.apply_actions(
                actions, ctx.player, ctx.drone, creature, ctx.repair_checklist
            )
            for msg in action_msgs:
                ui.console.print(msg)

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
        if creature.trust >= 70:
            if creature.knows_food_source and creature.knows_food_source not in ctx.player.known_locations:
                ctx.player.discover_location(creature.knows_food_source)
                for loc in ctx.locations:
                    if loc.name == creature.knows_food_source:
                        loc.discovered = True
                ui.success(f"{creature.name} revealed a food source: {creature.knows_food_source}")
            if creature.knows_water_source and creature.knows_water_source not in ctx.player.known_locations:
                ctx.player.discover_location(creature.knows_water_source)
                for loc in ctx.locations:
                    if loc.name == creature.knows_water_source:
                        loc.discovered = True
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
        creature.can_give_materials.clear()


def cmd_escort(ctx: GameContext, args: str):
    """Ask a creature to follow you or dismiss a companion."""
    loc = ctx.current_location()
    creature = ctx.creature_at_location(loc.name)

    # Check if player wants to dismiss a follower
    if args.strip().lower() in ("dismiss", "stay", "stop"):
        followers = [c for c in ctx.creatures if c.following]
        if not followers:
            ui.info("No one is following you.")
            return
        for c in followers:
            c.following = False
            c.location_name = ctx.player.location_name
            ui.success(f"{c.name} stays at {ctx.player.location_name}.")
        return

    # Check if there's a creature here to ask
    if not creature:
        # Check if any follower is here
        followers = [c for c in ctx.creatures if c.following]
        if followers:
            ui.info(f"Currently following you: {', '.join(c.name for c in followers)}")
            ui.dim("Use 'escort dismiss' to let them stay here.")
        else:
            ui.error("There's no creature here to escort.")
        return

    if creature.following:
        ui.info(f"{creature.name} is already following you.")
        return

    if creature.trust < 50:
        ui.warn(f"{creature.name} doesn't trust you enough to travel with you. (Trust: {creature.trust}/100, need 50+)")
        return

    if creature.disposition == "hostile" and creature.trust < 70:
        ui.warn(f"{creature.name} is too hostile to escort. Build more trust first.")
        return

    # Ask creature
    ui.console.print(f"\n[bold]Ask [{creature.color}]{creature.name}[/{creature.color}] to travel with you to the Crash Site for help?[/bold]")
    try:
        confirm = ui.console.input("[bold](y/n) > [/bold]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if confirm not in ("y", "yes"):
        return

    creature.following = True
    creature.home_location = creature.location_name
    ui.success(f"{creature.name} agrees to travel with you!")
    if ctx.ship_ai:
        ui.console.print(ctx.ship_ai.speak(
            f"Excellent, Commander. {creature.name} may be able to assist with repairs at the ship."
        ))


def _companions_help_at_ship(ctx: GameContext, companions: list):
    """When companions arrive at the crash site, they offer to help."""
    from src.game import REPAIR_MATERIALS

    ui.console.print()
    ui.console.print("[bold]── Companions at the Ship ──[/bold]")

    for creature in companions:
        helped = False
        ui.console.print(f"\n  [{creature.color}]{creature.name}[/{creature.color}] examines the ship...")

        # Healer: restore food/water/suit
        if creature.archetype == "Healer":
            if ctx.player.suit_integrity < 100:
                restore = min(30.0, 100.0 - ctx.player.suit_integrity)
                ctx.player.suit_integrity += restore
                ui.success(f"  {creature.name} tends to your suit. Suit +{restore:.0f}%!")
                helped = True
            if ctx.player.food < 100 or ctx.player.water < 100:
                ctx.player.food = min(100.0, ctx.player.food + 25.0)
                ctx.player.water = min(100.0, ctx.player.water + 25.0)
                ctx.player.food_warning_given = False
                ctx.player.water_warning_given = False
                ui.success(f"  {creature.name} provides nourishment. Food/Water +25%!")
                helped = True

        # Builder: install a repair material if player has one
        if creature.archetype in ("Builder", "Wise Elder"):
            for mat in REPAIR_MATERIALS[ctx.world_mode]:
                key = f"material_{mat}"
                if key in ctx.repair_checklist and not ctx.repair_checklist[key]:
                    if ctx.player.has_item(mat):
                        ctx.player.remove_item(mat)
                        ctx.repair_checklist[key] = True
                        display = mat.replace("_", " ").title()
                        ui.success(f"  {creature.name} helps install {display} into the ship!")
                        helped = True
                        break

        # Any creature with materials can donate them
        if creature.can_give_materials and not creature.has_helped_repair:
            creature.has_helped_repair = True
            for mat in list(creature.can_give_materials):
                ctx.player.add_item(mat)
                display = mat.replace("_", " ").title()
                ui.success(f"  {creature.name} contributes: {display}")
                helped = True
            creature.can_give_materials.clear()

        # Trust bonus for the trip
        creature.add_trust(10)

        if not helped:
            ui.dim(f"  {creature.name} observes the ship with fascination. (+10 trust)")
        else:
            ui.dim(f"  (+10 trust)")

    # Mark all companions as having helped (prevents repeat exploit)
    for creature in companions:
        creature.helped_at_ship = True

    # Ask if companions should stay or return home
    ui.console.print()
    ui.console.print("[bold]Your companions can stay here or return home.[/bold]")
    try:
        choice = ui.console.input("[bold]Send companions home? (y/n) > [/bold]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if choice in ("y", "yes"):
        for creature in companions:
            creature.following = False
            if creature.home_location:
                creature.location_name = creature.home_location
                creature.home_location = None
                ui.dim(f"  {creature.name} returns to {creature.location_name}.")
            else:
                ui.dim(f"  {creature.name} stays at the Crash Site.")


def cmd_drone(ctx: GameContext, args: str):
    drone_dict = ctx.drone.to_dict()
    drone_dict["cargo_used"] = ctx.player.total_items
    ui.show_drone_status(drone_dict, title="ARIA Scout Drone")


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
    at_crash = ctx.player.location_name == "Crash Site"

    if not at_crash:
        ui.show_ship_repair(ctx.repair_checklist)
        ui.dim("Travel to the Crash Site to access ship bays and install materials.")
        return

    # --- At Crash Site: show ship bay menu ---
    sub = args.strip().lower() if args else ""

    if sub in ("storage", "stash"):
        _bay_storage(ctx)
    elif sub in ("kitchen", "cook"):
        _bay_kitchen(ctx)
    elif sub in ("charging", "charge", "recharge"):
        _bay_charging(ctx)
    elif sub in ("medical", "med", "medbay"):
        _bay_medical(ctx)
    elif sub in ("repair", "install"):
        _bay_repair(ctx)
    else:
        # Show ship overview with bay menu
        ui.show_ship_repair(ctx.repair_checklist)
        ui.console.print()
        _show_bay_menu(ctx)


def _show_bay_menu(ctx: GameContext):
    """Display the ship bay menu."""
    from rich.table import Table

    table = Table(title="Ship Bays", border_style="yellow", show_header=False, padding=(0, 2))
    table.add_column("Bay", style="bold cyan")
    table.add_column("Description")
    table.add_column("Status", style="dim")

    # Repair bay status
    from src.game import REPAIR_MATERIALS

    installable = sum(
        1
        for mat in REPAIR_MATERIALS[ctx.world_mode]
        if not ctx.repair_checklist.get(f"material_{mat}", False) and ctx.player.has_item(mat)
    )
    repair_status = f"[yellow]{installable} materials ready[/yellow]" if installable else "[dim]No materials to install[/dim]"
    table.add_row("ship repair", "Install repair materials", repair_status)

    # Storage bay status
    stored = sum(ctx.player.ship_storage.values())
    table.add_row("ship storage", "Stash/retrieve items", f"{stored} items stored")

    # Kitchen bay status
    cookable = sum(ctx.player.inventory.get(item, 0) for item in ("bio_gel", "ice_crystal"))
    kitchen_status = f"[yellow]{cookable} items cookable[/yellow]" if cookable else "[dim]Nothing to cook[/dim]"
    table.add_row("ship kitchen", "Cook items into food/water", kitchen_status)

    # Charging bay status
    batt = ctx.drone.battery
    batt_color = "green" if batt > 50 else "yellow" if batt > 20 else "red"
    table.add_row("ship charging", "Recharge drone battery", f"[{batt_color}]{batt:.0f}%[/{batt_color}]")

    # Medical bay status
    suit = ctx.player.suit_integrity
    food = ctx.player.food
    water = ctx.player.water
    needs_med = suit < 100 or food < 100 or water < 100
    med_status = "[yellow]Treatment available[/yellow]" if needs_med else "[green]All vitals full[/green]"
    table.add_row("ship medical", "Heal, restore suit and vitals", med_status)

    ui.console.print(table)
    ui.dim("Usage: ship <bay>  (e.g. 'ship kitchen', 'ship storage')")


def _bay_repair(ctx: GameContext):
    """Install repair materials into the ship."""
    from src.game import REPAIR_MATERIALS

    installable = []
    for mat in REPAIR_MATERIALS[ctx.world_mode]:
        key = f"material_{mat}"
        if key in ctx.repair_checklist and not ctx.repair_checklist[key]:
            if ctx.player.has_item(mat):
                installable.append(mat)

    if not installable:
        ui.info("No repair materials in inventory to install.")
        ui.show_ship_repair(ctx.repair_checklist)
        return

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


def _bay_storage(ctx: GameContext):
    """Stash or retrieve items from ship storage."""
    from rich.table import Table

    ui.console.print("\n[bold]── Storage Bay ──[/bold]")

    # Show current storage
    if ctx.player.ship_storage:
        table = Table(border_style="cyan", show_header=True)
        table.add_column("Stored Item", style="yellow")
        table.add_column("Qty", justify="right")
        for item, qty in sorted(ctx.player.ship_storage.items()):
            table.add_row(item.replace("_", " ").title(), str(qty))
        ui.console.print(table)
    else:
        ui.dim("  Ship storage is empty.")

    ui.console.print()
    ui.console.print("  [cyan]1[/cyan]. Stash items (inventory → storage)")
    ui.console.print("  [cyan]2[/cyan]. Retrieve items (storage → inventory)")
    ui.console.print("  [cyan]3[/cyan]. Back")

    try:
        choice = ui.console.input("\n[bold]> [/bold]").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "1":
        if not ctx.player.inventory:
            ui.info("Inventory is empty.")
            return
        items = sorted(ctx.player.inventory.keys())
        ui.console.print("\n[bold]Stash which item?[/bold]")
        for i, item in enumerate(items, 1):
            display = item.replace("_", " ").title()
            qty = ctx.player.inventory[item]
            ui.console.print(f"  [cyan]{i}[/cyan]. {display} (x{qty})")
        try:
            pick = ui.console.input("[bold]> [/bold]").strip()
            idx = int(pick) - 1
            if 0 <= idx < len(items):
                item = items[idx]
                ctx.player.stash_item(item)
                display = item.replace("_", " ").title()
                ui.success(f"Stashed {display} in ship storage.")
        except (ValueError, EOFError, KeyboardInterrupt):
            return

    elif choice == "2":
        if not ctx.player.ship_storage:
            ui.info("Nothing in storage.")
            return
        items = sorted(ctx.player.ship_storage.keys())
        ui.console.print("\n[bold]Retrieve which item?[/bold]")
        for i, item in enumerate(items, 1):
            display = item.replace("_", " ").title()
            qty = ctx.player.ship_storage[item]
            ui.console.print(f"  [cyan]{i}[/cyan]. {display} (x{qty})")
        try:
            pick = ui.console.input("[bold]> [/bold]").strip()
            idx = int(pick) - 1
            if 0 <= idx < len(items):
                item = items[idx]
                if ctx.player.total_items >= ctx.drone.cargo_capacity:
                    ui.error(f"Inventory full! Drone cargo capacity: {ctx.drone.cargo_capacity}")
                    return
                ctx.player.retrieve_item(item)
                display = item.replace("_", " ").title()
                ui.success(f"Retrieved {display} from storage.")
        except (ValueError, EOFError, KeyboardInterrupt):
            return


# Items that can be cooked and what they produce
_KITCHEN_RECIPES = {
    "bio_gel": {"effect": "food", "amount": 40.0, "label": "Nutrient paste from bio-gel"},
    "ice_crystal": {"effect": "water", "amount": 40.0, "label": "Purified water from ice crystal"},
}


def _bay_kitchen(ctx: GameContext):
    """Cook items to restore food or water."""
    ui.console.print("\n[bold]── Kitchen Bay ──[/bold]")
    ui.dim("  Process raw materials into food and water.\n")

    available = []
    for item, recipe in _KITCHEN_RECIPES.items():
        qty = ctx.player.inventory.get(item, 0)
        if qty > 0:
            available.append((item, recipe, qty))

    if not available:
        ui.info("No cookable items in inventory. (bio_gel → food, ice_crystal → water)")
        return

    for i, (item, recipe, qty) in enumerate(available, 1):
        display = item.replace("_", " ").title()
        effect = recipe["effect"].title()
        ui.console.print(
            f"  [cyan]{i}[/cyan]. {recipe['label']} — "
            f"[yellow]{display}[/yellow] (x{qty}) → +{recipe['amount']:.0f}% {effect}"
        )
    ui.console.print(f"  [cyan]{len(available) + 1}[/cyan]. Back")

    try:
        pick = ui.console.input("\n[bold]Cook which? > [/bold]").strip()
        idx = int(pick) - 1
        if 0 <= idx < len(available):
            item, recipe, qty = available[idx]
            ctx.player.remove_item(item)
            display = item.replace("_", " ").title()
            if recipe["effect"] == "food":
                ctx.player.food = min(100.0, ctx.player.food + recipe["amount"])
                ctx.player.food_warning_given = False
                if ctx.ship_ai:
                    ctx.ship_ai.reset_warnings("food")
                ui.success(f"Cooked {display}! Food: {ctx.player.food:.0f}%")
            elif recipe["effect"] == "water":
                ctx.player.water = min(100.0, ctx.player.water + recipe["amount"])
                ctx.player.water_warning_given = False
                if ctx.ship_ai:
                    ctx.ship_ai.reset_warnings("water")
                ui.success(f"Processed {display}! Water: {ctx.player.water:.0f}%")
    except (ValueError, EOFError, KeyboardInterrupt):
        return


def _bay_charging(ctx: GameContext):
    """Recharge drone battery at the ship."""
    ui.console.print("\n[bold]── Charging Bay ──[/bold]")
    batt = ctx.drone.battery
    batt_max = ctx.drone.battery_max
    batt_color = "green" if batt > 50 else "yellow" if batt > 20 else "red"
    ui.console.print(f"  Drone Battery: [{batt_color}]{batt:.0f}%[/{batt_color}] / {batt_max:.0f}%\n")

    if batt >= batt_max:
        ui.success("Drone battery is fully charged!")
        return

    ui.console.print("  [cyan]1[/cyan]. Full recharge (free at Crash Site)")
    has_power_cell = ctx.player.has_item("power_cell")
    if has_power_cell:
        ui.console.print("  [cyan]2[/cyan]. Overcharge with Power Cell (+10% max capacity permanently)")
    ui.console.print(f"  [cyan]{'3' if has_power_cell else '2'}[/cyan]. Back")

    try:
        choice = ui.console.input("\n[bold]> [/bold]").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "1":
        ctx.drone.recharge()
        if ctx.ship_ai:
            ctx.ship_ai.reset_warnings("battery")
        ui.success(f"Drone fully recharged! Battery: {ctx.drone.battery:.0f}%")
    elif choice == "2" and has_power_cell:
        ctx.player.remove_item("power_cell")
        ctx.drone.battery_max += 10.0
        ctx.drone.recharge()
        if ctx.ship_ai:
            ctx.ship_ai.reset_warnings("battery")
        ui.success(
            f"Power Cell consumed! Battery max: {ctx.drone.battery_max:.0f}%. "
            f"Battery: {ctx.drone.battery:.0f}%"
        )


def _bay_medical(ctx: GameContext):
    """Medical bay: heal the player."""
    ui.console.print("\n[bold]── Medical Bay ──[/bold]")

    suit = ctx.player.suit_integrity
    food = ctx.player.food
    water = ctx.player.water
    suit_color = "green" if suit > 60 else "yellow" if suit > 30 else "red"
    food_color = "green" if food > 50 else "yellow" if food > 20 else "red"
    water_color = "green" if water > 50 else "yellow" if water > 20 else "red"

    ui.console.print(f"  Suit:  [{suit_color}]{suit:.0f}%[/{suit_color}]")
    ui.console.print(f"  Food:  [{food_color}]{food:.0f}%[/{food_color}]")
    ui.console.print(f"  Water: [{water_color}]{water:.0f}%[/{water_color}]")
    ui.console.print()

    if suit == 100 and food == 100 and water == 100:
        ui.success("All vitals at 100%. No treatment needed.")
        return

    options = []
    if suit < 100 and ctx.drone.battery >= 10:
        repair_amount = min(100 - suit, ctx.drone.battery * 2)
        battery_cost = repair_amount / 2
        options.append(("suit", f"Repair suit (+{repair_amount:.0f}%) — costs {battery_cost:.0f}% drone battery"))
    elif suit < 100:
        ui.dim("  Suit repair unavailable — drone battery too low.")

    if food < 100 or water < 100:
        options.append(("rest", "Rest and recover (+20% food, +20% water) — costs 1 hour"))

    if not options:
        ui.info("No treatments available right now.")
        return

    for i, (key, desc) in enumerate(options, 1):
        ui.console.print(f"  [cyan]{i}[/cyan]. {desc}")
    ui.console.print(f"  [cyan]{len(options) + 1}[/cyan]. Back")

    try:
        choice = ui.console.input("\n[bold]> [/bold]").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            key = options[idx][0]
            if key == "suit":
                repair_amount = min(100 - ctx.player.suit_integrity, ctx.drone.battery * 2)
                battery_cost = repair_amount / 2
                ctx.drone.use_battery(battery_cost)
                ctx.player.suit_integrity = min(100.0, ctx.player.suit_integrity + repair_amount)
                if ctx.ship_ai:
                    ctx.ship_ai.reset_warnings("suit")
                ui.success(
                    f"Suit repaired to {ctx.player.suit_integrity:.0f}%! "
                    f"(Battery: {ctx.drone.battery:.0f}%)"
                )
            elif key == "rest":
                ctx.player.food = min(100.0, ctx.player.food + 20.0)
                ctx.player.water = min(100.0, ctx.player.water + 20.0)
                ctx.player.food_warning_given = False
                ctx.player.water_warning_given = False
                ctx.player.hours_elapsed += 1
                if ctx.ship_ai:
                    ctx.ship_ai.reset_warnings("food")
                    ctx.ship_ai.reset_warnings("water")
                ui.success(
                    f"Rested for 1 hour. Food: {ctx.player.food:.0f}%, "
                    f"Water: {ctx.player.water:.0f}%"
                )
    except (ValueError, EOFError, KeyboardInterrupt):
        return


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


def cmd_clear(ctx: GameContext, args: str):
    ui.console.clear()


def cmd_config(ctx: GameContext, args: str):
    """Show or change game configuration."""
    from pathlib import Path
    from src.config import get_save_dir, set_save_dir, CONFIG_PATH

    sub = args.strip().lower()

    if sub.startswith("savedir ") or sub.startswith("save_dir "):
        new_path = Path(args.split(maxsplit=1)[1].strip()).expanduser().resolve()
        try:
            new_path.mkdir(parents=True, exist_ok=True)
            set_save_dir(new_path)
            ui.success(f"Save directory changed to: {new_path}")
            ui.dim("New saves will use this location. Existing saves remain at the old path.")
        except Exception as e:
            ui.error(f"Cannot use path: {e}")
        return

    # Show current config
    ui.console.print("\n[bold]Game Configuration[/bold]")
    ui.console.print(f"  [cyan]Save directory:[/cyan] {get_save_dir()}")
    ui.console.print(f"  [cyan]Config file:[/cyan]   {CONFIG_PATH}")
    ui.console.print()
    ui.dim("Change save location: config savedir /path/to/saves")


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
    "escort": cmd_escort,
    "drone": cmd_drone,
    "upgrade": cmd_upgrade,
    "status": cmd_status,
    "ship": cmd_ship,
    "repair": cmd_ship,
    "save": cmd_save,
    "load": cmd_load,
    "config": cmd_config,
    "dev": cmd_dev,
    "devmode": cmd_dev,
    "clear": cmd_clear,
    "cls": cmd_clear,
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
