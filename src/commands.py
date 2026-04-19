"""Command registry, parser, and handlers."""

import random
import re
import unicodedata

from src import llm, ui
from src.creatures import Creature
from src.drone import UPGRADE_EFFECTS, Drone
from src.player import Player
from src.save_load import list_saves, load_game, save_game
from src.travel import execute_travel
from src.world import Location

try:
    from src import sound as _sound_mod
except Exception:
    _sound_mod = None


class _SafeSound:
    """Proxy that never crashes the game."""

    @staticmethod
    def play(event):
        if _sound_mod:
            try:
                _sound_mod.play(event)
            except Exception:
                pass

    @staticmethod
    def is_enabled():
        return _sound_mod.is_enabled() if _sound_mod else False

    @staticmethod
    def set_voice(v):
        if _sound_mod:
            _sound_mod.set_voice(v)

    @staticmethod
    def enable():
        if _sound_mod:
            _sound_mod.enable()

    @staticmethod
    def disable():
        if _sound_mod:
            _sound_mod.disable()


sound = _SafeSound()

HELP_TEXT = """
[bold yellow]Goal:[/bold yellow] Collect repair materials and install them at the Crash Site to fix your ship.
[bold yellow]Survive:[/bold yellow] Keep food and water above 0% or you die. Use [cyan]status[/cyan] to check.

[bold]Navigation:[/bold]
  [cyan]look[/cyan]                 — Describe current location
  [cyan]scan[/cyan]                 — Use drone to discover nearby locations
  [cyan]gps[/cyan] / [cyan]map[/cyan]             — Show known locations with distances
  [cyan]travel[/cyan] <location>    — Travel to a known location

[bold]Items:[/bold]
  [cyan]take[/cyan] <item>          — Pick up an item at current location
  [cyan]inventory[/cyan] / [cyan]inv[/cyan]       — Show your inventory
  [cyan]inspect[/cyan] <item>       — Examine an item to see what it's used for

[bold]Creatures:[/bold]
  [cyan]talk[/cyan] <creature>      — Talk to a creature here (LLM dialogue)
  [cyan]give[/cyan] <item> to <creature> — Give an item to build trust
  [cyan]trade[/cyan]                — Trade items with a Merchant creature
  [cyan]escort[/cyan]               — Ask a creature to travel with you (trust 50+)

[bold]Drone:[/bold]
  [cyan]drone[/cyan]                — Show drone status and upgrades
  [cyan]drone upgrade[/cyan] <part> — Install a drone upgrade from inventory
  [cyan]drone charge[/cyan]         — Toggle auto-charge (requires Charge Module)

[bold]Player:[/bold]
  [cyan]status[/cyan]               — Show player vitals (food, water, suit, time)
  [cyan]stats[/cyan]                — Show session gameplay statistics
  [cyan]scores[/cyan]               — View local leaderboard (top 10)
  [cyan]rest[/cyan]                 — Rest 1 hour (+10% food/water, +20% at ship)

[bold]Ship:[/bold]
  [cyan]ship[/cyan]                 — Show repair progress (bays available at Crash Site)

[bold]System:[/bold]
  [cyan]save[/cyan] [slot]          — Save game (default: 'manual')
  [cyan]load[/cyan] [slot]          — Load a saved game
  [cyan]sound[/cyan]                — Toggle sound effects
  [cyan]screenshot[/cyan]           — Save a screenshot (F12)
  [cyan]tutorial[/cyan]             — Replay the tutorial
  [cyan]config[/cyan]               — Game settings (save path, GPU, context)
  [cyan]clear[/cyan] / [cyan]cls[/cyan]          — Clear the screen
  [cyan]help[/cyan]                 — Show this help message
  [cyan]quit[/cyan] / [cyan]exit[/cyan]           — Exit game
"""


CHAT_HELP_TEXT = """
[bold]ARIA Communicator — Help[/bold]

  [cyan]/end[/cyan], [cyan]/bye[/cyan], [cyan]/quit[/cyan], [cyan]bye[/cyan]   — Disconnect from conversation
  [cyan]/?[/cyan], [cyan]/help[/cyan]               — Show this help
  [cyan]/history[/cyan]              — Show recent conversation history
  [cyan]/<command>[/cyan]              — Run a game command (e.g. /status, /inventory, /look)
  [cyan]/give[/cyan] <item> to <name> — Give an item to this creature
  [cyan]/trade[/cyan]                 — Open trade menu (Merchants only)
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
        self.easter_egg_announced = False
        self.escorts_completed: int = 0

        from src.stats import SessionStats

        self.stats: SessionStats = SessionStats()

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

    def any_creature_here(self, location_name: str, name_hint: str = "") -> Creature | None:
        """Find any creature at location — residents first, then followers.

        If name_hint is given, match by name (partial, case-insensitive).
        """
        if name_hint:
            hint = name_hint.lower()
            for c in self.creatures:
                if c.location_name == location_name and hint in c.name.lower():
                    return c
            return None
        # Prefer resident, fall back to follower
        resident = self.creature_at_location(location_name)
        if resident:
            return resident
        for c in self.creatures:
            if c.following and c.location_name == location_name:
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

        # Include escorts_completed in checklist for persistence
        checklist_with_escorts = dict(self.repair_checklist)
        checklist_with_escorts["_escorts_completed"] = self.escorts_completed

        auto_save(
            self.player,
            self.drone,
            self.locations,
            self.creatures,
            self.world_seed,
            self.world_mode,
            checklist_with_escorts,
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


SHIP_HELP = """
[bold]Ship Bays (Crash Site):[/bold]
  [cyan]ship repair[/cyan]          — Install repair materials to fix the ship
  [cyan]ship storage[/cyan]         — Stash/retrieve items from ship storage
  [cyan]ship kitchen[/cyan]         — Cook bio_gel (+40% food) or ice_crystal (+40% water)
  [cyan]ship charging[/cyan]        — Recharge drone battery, overcharge, auto-charge toggle
  [cyan]ship medical[/cyan]         — Repair suit (costs battery) or rest to recover
"""


def cmd_help(ctx: GameContext, args: str):
    ui.console.print(HELP_TEXT)
    if ctx.player.location_name == "Crash Site":
        ui.console.print(SHIP_HELP)


def cmd_look(ctx: GameContext, args: str):
    loc = ctx.current_location()
    creature = ctx.creature_at_location(loc.name)
    creature_name = None
    if creature:
        creature_name = f"[{creature.color}]{creature.name}[/{creature.color}] ({creature.species})"
    items_display = [i.replace("_", " ").title() for i in loc.items]
    ui.show_location(loc.name, loc.loc_type, loc.description, items_display, creature_name)

    # Show followers present
    followers_here = [c for c in ctx.creatures if c.following and c.location_name == loc.name]
    if followers_here:
        names = [f"[{c.color}]{c.name}[/{c.color}]" for c in followers_here]
        ui.dim(f"  Companions here: {', '.join(names)}")

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

    if ctx.dev_mode:
        ctx.dev_mode.debug(
            "scan", location=ctx.player.location_name, discovered=len(discovered), battery_after=round(drone.battery, 1)
        )

    if discovered:
        sound.play("scan")
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
                "food_source": loc.food_source if loc.visited else False,
                "water_source": loc.water_source if loc.visited else False,
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

    # Estimate travel cost and warn if dangerous
    from src.travel import calculate_travel_time

    distance = cur.distance_to(dest.x, dest.y)
    hours = calculate_travel_time(distance, ctx.drone)
    hours_int = max(1, round(hours))
    food_cost = hours_int * 2.0
    water_cost = hours_int * 3.0

    # Account for late-game extra water drain in estimate
    from src.travel import LATE_GAME_THRESHOLDS

    late_threshold = LATE_GAME_THRESHOLDS.get(ctx.world_mode, 40)
    # Use pre-trip hours to match what execute_travel computes
    hours_past = max(0, ctx.player.hours_elapsed - late_threshold)
    if hours_past > 0:
        water_cost += hours_int * 0.5 * (hours_past // 10 + 1)

    food_after = ctx.player.food - food_cost
    water_after = ctx.player.water - water_cost

    needs_confirm = hours_int >= 3
    if food_after <= 10 or water_after <= 10:
        needs_confirm = True
        ui.error(f"Dangerous trip! After travel: food ~{max(0, food_after):.0f}%, water ~{max(0, water_after):.0f}%")
    if needs_confirm:
        ui.warn(
            f"Travel to {dest.name} will take ~{hours_int}h "
            f"(~{food_cost:.0f}% food, ~{water_cost:.0f}% water, ~{distance * 0.5:.0f}% battery)"
        )
        try:
            confirm = ui.console.input("[bold]Continue? (y/n) > [/bold]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if confirm not in ("y", "yes"):
            return

    # Clear screen before travel
    ui.console.clear()

    # Log travel start
    if ctx.dev_mode:
        ctx.dev_mode.debug(
            "travel_start",
            origin=cur.name,
            destination=dest.name,
            distance_km=round(cur.distance_to(dest.x, dest.y), 1),
            food_before=round(ctx.player.food, 1),
            water_before=round(ctx.player.water, 1),
            suit_before=round(ctx.player.suit_integrity, 1),
            battery_before=round(ctx.drone.battery, 1),
        )

    messages, travel_km, hazards_hit = execute_travel(
        ctx.player, ctx.drone, dest, cur, ctx.rng, ctx.ship_ai, ctx.locations, ctx.world_mode
    )
    ctx.stats.km_traveled += travel_km
    ctx.stats.hazards_survived += hazards_hit
    for msg in messages:
        ui.console.print(msg)

    # Log travel result
    if ctx.dev_mode:
        ctx.dev_mode.debug(
            "travel_arrive",
            destination=dest.name,
            food_after=round(ctx.player.food, 1),
            water_after=round(ctx.player.water, 1),
            suit_after=round(ctx.player.suit_integrity, 1),
            battery_after=round(ctx.drone.battery, 1),
            hours_elapsed=ctx.player.hours_elapsed,
        )

    ui.console.print()

    # Autopilot: auto-look and auto-scan on arrival if drone has the upgrade
    if ctx.drone.autopilot_enabled and ctx.drone.battery > 0:
        cmd_look(ctx, "")
        if ctx.drone.can_scan():
            ui.dim("Drone autopilot: scanning area...")
            cmd_scan(ctx, "")
    else:
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
        ui.error(f"{creature.name} won't let you take anything here. Try offering a gift to build trust.")
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
        ctx.stats.items_collected += 1
        if ctx.dev_mode:
            ctx.dev_mode.debug("item_pickup", item=item_name, location=loc.name, inventory_count=ctx.player.total_items)
        # Hint if this is a needed repair material
        key = f"material_{item_name}"
        if key in ctx.repair_checklist and not ctx.repair_checklist[key]:
            ui.dim("  This is needed for ship repair!")
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
    creature = ctx.any_creature_here(loc.name, name_hint=args)

    if not creature:
        # Try without hint to give a helpful message
        anyone = ctx.any_creature_here(loc.name)
        if anyone and args:
            ui.error(f"'{args}' is not here. {anyone.name} is at this location.")
        else:
            ui.info("There's no one to talk to here.")
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

    # Drone initial coaching tip (context-aware)
    initial_tip = ctx.drone.get_smart_advice(creature, ctx.player, ctx.repair_checklist, ctx.rng)
    if initial_tip:
        ui.console.print(initial_tip)
        ui.console.print()

    ctx.stats.creatures_talked.add(creature.id)

    exchange_count = 0
    conversation_start_idx = len(creature.conversation_history)

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

        if player_input.lower() == "/history":
            if creature.conversation_history:
                ui.console.print(f"\n[bold]Conversation history with {creature.name}:[/bold]")
                for msg in creature.conversation_history:
                    if msg["role"] == "user":
                        ui.console.print(f"  [bold]You>[/bold] {msg['content']}")
                    else:
                        ui.creature_speak(creature.name, msg["content"], creature.color)
                ui.console.print()
            else:
                ui.dim("No previous conversation history.")
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

        # Sanitize player input — strip action tag patterns to prevent injection
        # Normalize Unicode to catch fullwidth/variant chars that bypass regex
        normalized_input = unicodedata.normalize("NFKC", player_input)
        clean_input = re.sub(r"\[/?[A-Z_]+(?::[^\]]*)?\]", "", normalized_input).strip()
        if not clean_input:
            clean_input = player_input  # Fallback if everything was stripped

        creature.add_message("user", clean_input)
        raw_response = llm.generate_response(creature, clean_input, ctx.drone.translation_quality)

        # Parse action tags from LLM response (e.g. [GIVE_WATER], [HEAL])
        response, actions = llm.parse_actions(raw_response)
        if not response.strip():
            response = "*nods thoughtfully*"
        creature.add_message("assistant", response)

        if ctx.dev_mode and actions:
            ctx.dev_mode.debug(
                "llm_actions",
                creature=creature.name,
                actions=[a["action"] for a in actions],
                trust=creature.trust,
                archetype=creature.archetype,
            )

        # Drone translation frame (always on first exchange, ~40% after)
        show_frame = exchange_count == 0 or ctx.rng.random() < 0.4
        if show_frame:
            frame = ctx.drone.get_translation_frame(ctx.rng)
            if frame:
                ui.console.print(frame)

        ui.creature_speak(creature.name, response, creature.color)

        # Apply any creature actions (give water/food/materials, heal, repair suit)
        if actions:
            action_msgs = llm.apply_actions(actions, ctx.player, ctx.drone, creature, ctx.repair_checklist)
            for msg in action_msgs:
                ui.console.print(msg)
            # Track LLM-initiated trades in session stats
            for act in actions:
                if act.get("action") == "TRADE":
                    ctx.stats.trades += 1

        # Trust gain from conversation (scaled by difficulty)
        from src.difficulty import EASTER_EGG_TRUST_MULTIPLIER, check_junk_easter_egg, get_difficulty

        diff = get_difficulty(ctx.world_mode)
        trust_gain = diff["trust_per_chat"]
        if check_junk_easter_egg(ctx.player, ctx.world_mode):
            trust_gain = int(trust_gain * EASTER_EGG_TRUST_MULTIPLIER)
        old_trust = creature.trust
        creature.add_trust(trust_gain)
        if ctx.dev_mode:
            ctx.dev_mode.debug(
                "trust_change",
                creature=creature.name,
                old=old_trust,
                new=creature.trust,
                source="conversation",
                exchange=exchange_count,
            )
        if creature.trust >= 100:
            ui.console.print(f"[dim]+{trust_gain} trust ({creature.trust}/100 — max trust)[/dim]")
        else:
            next_tier = 70 if creature.trust < 70 else 100
            tier_label = "full cooperation" if next_tier == 70 else "max trust"
            ui.console.print(f"[dim]+{trust_gain} trust ({creature.trust}/100 — {next_tier} for {tier_label})[/dim]")
        exchange_count += 1

        # Update status bar so player sees trust/vitals change live
        loc = ctx.current_location()
        followers = [c for c in ctx.creatures if c.following]
        ui.render_status_bar(ctx.player, ctx.drone, ctx.repair_checklist, loc.loc_type, creature, followers)

        # Drone private advice (NOT added to creature conversation history)
        interjection_chance = _interjection_probability(creature, exchange_count)
        if ctx.rng.random() < interjection_chance:
            advice = ctx.drone.get_smart_advice(creature, ctx.player, ctx.repair_checklist, ctx.rng)
            if advice:
                ui.console.print(advice)

        # Fallback material offering (when LLM is unavailable)
        if not llm.is_available():
            from src.creatures import ROLE_CAPABILITIES

            caps = ROLE_CAPABILITIES.get(creature.archetype, {})
            thresholds = caps.get("trust_threshold", {})
            mat_threshold = thresholds.get("materials", thresholds.get("trade", 50))
            role_inv = creature.role_inventory if creature.role_inventory else creature.can_give_materials
            unoffered = [m for m in role_inv if m not in creature.given_items]
            if creature.trust >= mat_threshold and unoffered and exchange_count % 3 == 2:
                mat = unoffered[0]
                display = mat.replace("_", " ").title()
                ui.console.print(f"\n[bold]{creature.name} reaches into their pack and holds out: {display}[/bold]")
                try:
                    accept = ui.console.input("[bold](accept? y/n) > [/bold]").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    accept = "n"
                if accept in ("y", "yes"):
                    ctx.player.add_item(mat)
                    role_inv.remove(mat)
                    creature.given_items.append(mat)
                    # Keep can_give_materials in sync (only if different list)
                    if role_inv is not creature.can_give_materials and mat in creature.can_give_materials:
                        creature.can_give_materials.remove(mat)
                    ui.success(f"You received {display}!")
                else:
                    ui.dim(f"{creature.name} puts it away.")

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

    # Update creature memory with current conversation (capped to avoid context overflow)
    if exchange_count > 0:
        current_convo_len = len(creature.conversation_history) - conversation_start_idx
        try:
            llm.update_creature_memory(creature, recent_count=min(max(current_convo_len, 1), 40))
        except Exception:
            pass

    # ARIA trust commentary after conversation
    if ctx.ship_ai and creature:
        if creature.trust >= 70:
            ui.console.print(ctx.ship_ai.speak(f"{creature.name} appears highly cooperative. Trust is strong."))
        elif creature.trust >= 35:
            ui.console.print(ctx.ship_ai.speak(f"{creature.name} is warming up to you, Commander."))

    # Escort hint when trust is high enough
    if creature and creature.trust >= 50 and not creature.following:
        ui.dim(f"Tip: {creature.name} trusts you enough to escort. Type 'escort' to ask.")

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
    creature = ctx.any_creature_here(loc.name, name_hint=creature_part)

    if not creature:
        ui.error(f"'{creature_part}' is not here.")
        return

    if not ctx.player.has_item(item_part):
        display = item_part.replace("_", " ").title()
        ui.error(f"You don't have '{display}' in your inventory.")
        return

    # Check if it's a junk item — creature mocks but gives it back
    from src.difficulty import JUNK_REACTIONS, is_junk_item

    if is_junk_item(item_part):
        display = item_part.replace("_", " ").title()
        reaction = ctx.rng.choice(JUNK_REACTIONS).format(name=creature.name, item=display)
        ui.creature_speak(creature.name, reaction, creature.color)
        ui.dim(f"  {creature.name} hands the {display} back to you.")
        return

    ctx.player.remove_item(item_part)
    display = item_part.replace("_", " ").title()
    ui.success(f"You give {display} to {creature.name}.")
    ctx.stats.gifts_given += 1

    # Trust increase from gift (scaled by difficulty)
    from src.difficulty import EASTER_EGG_TRUST_MULTIPLIER, check_junk_easter_egg, get_difficulty

    diff = get_difficulty(ctx.world_mode)
    trust_gain = diff["trust_per_gift"]
    if creature.disposition == "hostile":
        trust_gain = diff["trust_per_gift_hostile"]
    if check_junk_easter_egg(ctx.player, ctx.world_mode):
        trust_gain = int(trust_gain * EASTER_EGG_TRUST_MULTIPLIER)
    old_trust = creature.trust
    creature.add_trust(trust_gain)
    if ctx.dev_mode:
        ctx.dev_mode.debug(
            "trust_change", creature=creature.name, old=old_trust, new=creature.trust, source="gift", item=item_part
        )
    next_tier = 70 if creature.trust < 70 else 100
    tier_label = "full cooperation" if next_tier == 70 else "max trust"
    remaining = next_tier - creature.trust
    if remaining > 0:
        ui.info(f"{creature.name}'s trust: {creature.trust}/100 ({creature.trust_level}) — {remaining} to {tier_label}")
    else:
        ui.info(f"{creature.name}'s trust: {creature.trust}/100 ({creature.trust_level})")

    # Record gift in creature memory (without injecting into chat history)
    try:
        gift_ctx = f"Player gave {display} as a gift. Trust is now {creature.trust}."
        llm.update_creature_memory(creature, extra_context=gift_ctx)
    except Exception:
        pass

    # At high trust, creature acknowledges friendship
    if creature.trust >= 70 and not creature.has_helped_repair:
        creature.has_helped_repair = True
        ui.success(f"{creature.name} considers you a true friend. They may share what they have in conversation.")

    ctx.do_auto_save()


def cmd_trade(ctx: GameContext, args: str):
    """Trade items with a Merchant creature."""
    loc = ctx.current_location()
    creature = ctx.any_creature_here(loc.name)

    if not creature:
        ui.error("There's no creature here to trade with.")
        return

    if creature.archetype != "Merchant":
        ui.info(f"{creature.name} is not a trader. Try talking to them instead.")
        return

    from src.creatures import ROLE_CAPABILITIES

    caps = ROLE_CAPABILITIES.get("Merchant", {})
    required_trust = caps.get("trust_threshold", {}).get("trade", 20)

    if creature.trust < required_trust:
        ui.warn(
            f"{creature.name} doesn't trust you enough to trade. (Trust: {creature.trust}/100, need {required_trust}+)"
        )
        return

    # Show what the merchant has and wants
    has_items = [m for m in creature.role_inventory if m not in creature.given_items]
    wants_items = creature.trade_wants

    if not has_items:
        ui.info(f"{creature.name} has nothing left to trade.")
        return

    ui.console.print(f"\n[bold]── Trade with [{creature.color}]{creature.name}[/{creature.color}] ──[/bold]")
    ui.console.print("\n[bold]They have:[/bold]")
    for i, item in enumerate(has_items, 1):
        display = item.replace("_", " ").title()
        ui.console.print(f"  [cyan]{i}[/cyan]. {display}")

    ui.console.print("\n[bold]They want:[/bold]")
    available_wants = [w for w in wants_items if ctx.player.has_item(w)]
    if not available_wants:
        ui.dim(f"  Items wanted: {', '.join(w.replace('_', ' ').title() for w in wants_items)}")
        ui.warn("  You don't have anything they want.")
        return

    for i, item in enumerate(available_wants, 1):
        display = item.replace("_", " ").title()
        ui.console.print(f"  [yellow]{i}[/yellow]. {display}")

    ui.console.print(f"\n[dim]Pick an item to receive (1-{len(has_items)}), or 0 to cancel:[/dim]")
    try:
        pick_get = ui.console.input("[bold]Receive #> [/bold]").strip()
        idx_get = int(pick_get) - 1
        if idx_get < 0 or idx_get >= len(has_items):
            return
    except (ValueError, EOFError, KeyboardInterrupt):
        return

    ui.console.print(f"[dim]Pick an item to give (1-{len(available_wants)}), or 0 to cancel:[/dim]")
    try:
        pick_give = ui.console.input("[bold]Give #> [/bold]").strip()
        idx_give = int(pick_give) - 1
        if idx_give < 0 or idx_give >= len(available_wants):
            return
    except (ValueError, EOFError, KeyboardInterrupt):
        return

    get_item = has_items[idx_get]
    give_item = available_wants[idx_give]

    # Trade is 1-for-1: remove one, add one — net zero inventory change
    ctx.player.remove_item(give_item)
    ctx.player.add_item(get_item)
    creature.role_inventory.remove(get_item)
    creature.given_items.append(get_item)

    get_display = get_item.replace("_", " ").title()
    give_display = give_item.replace("_", " ").title()
    sound.play("trade")
    ui.success(f"Traded! You gave {give_display} and received {get_display}.")
    ctx.stats.trades += 1

    if ctx.dev_mode:
        ctx.dev_mode.debug(
            "trade", creature=creature.name, gave=give_item, received=get_item, trust_before=creature.trust
        )

    # Trust bonus for trading
    creature.add_trust(5)
    ui.dim(f"+5 trust ({creature.trust}/100)")
    ctx.do_auto_save()


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
        if len(followers) == 1:
            followers[0].following = False
            followers[0].location_name = ctx.player.location_name
            ui.success(f"{followers[0].name} stays at {ctx.player.location_name}.")
            return
        # Multiple followers — let player choose
        ui.console.print("\n[bold]Dismiss which companion?[/bold]")
        for i, c in enumerate(followers, 1):
            ui.console.print(f"  [cyan]{i}[/cyan]. [{c.color}]{c.name}[/{c.color}] ({c.archetype})")
        ui.console.print(f"  [cyan]{len(followers) + 1}[/cyan]. Dismiss all")
        try:
            pick = ui.console.input("[bold]> [/bold]").strip()
            idx = int(pick) - 1
            if idx == len(followers):
                # Dismiss all
                for c in followers:
                    c.following = False
                    c.location_name = ctx.player.location_name
                    ui.success(f"{c.name} stays at {ctx.player.location_name}.")
            elif 0 <= idx < len(followers):
                c = followers[idx]
                c.following = False
                c.location_name = ctx.player.location_name
                ui.success(f"{c.name} stays at {ctx.player.location_name}.")
        except (ValueError, EOFError, KeyboardInterrupt):
            return
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
    ui.console.print(f"\n[bold]Ask [{creature.color}]{creature.name}[/{creature.color}] to travel with you?[/bold]")
    ui.dim("  Companions help with repairs at the Crash Site.")
    try:
        confirm = ui.console.input("[bold](y/n) > [/bold]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if confirm not in ("y", "yes"):
        return

    creature.following = True
    creature.home_location = creature.location_name
    sound.play("escort")
    ui.success(f"{creature.name} agrees to travel with you!")
    if ctx.ship_ai:
        ui.console.print(
            ctx.ship_ai.speak(f"Excellent, Commander. {creature.name} may be able to assist with repairs at the ship.")
        )


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

        # Any creature with materials can donate them (use role_inventory, fall back to can_give_materials)
        donate_list = creature.role_inventory if creature.role_inventory else creature.can_give_materials
        unoffered = [m for m in donate_list if m not in creature.given_items]
        if unoffered and not creature.has_helped_repair:
            creature.has_helped_repair = True
            for mat in list(unoffered):
                if ctx.player.total_items >= ctx.drone.cargo_capacity:
                    # Overflow goes directly to ship storage
                    ctx.player.ship_storage[mat] = ctx.player.ship_storage.get(mat, 0) + 1
                    ui.dim(f"  Inventory full — {mat.replace('_', ' ').title()} stashed in ship storage.")
                else:
                    ctx.player.add_item(mat)
                donate_list.remove(mat)
                creature.given_items.append(mat)
                # Keep can_give_materials in sync (only if different list)
                if donate_list is not creature.can_give_materials and mat in creature.can_give_materials:
                    creature.can_give_materials.remove(mat)
                display = mat.replace("_", " ").title()
                ui.success(f"  {creature.name} contributes: {display}")
                helped = True

        # Trust bonus for the trip
        creature.add_trust(10)

        if not helped:
            ui.dim(f"  {creature.name} observes the ship with fascination. (+10 trust)")
        else:
            ui.dim("  (+10 trust)")

    # Mark all companions as having helped (prevents repeat exploit)
    for creature in companions:
        creature.helped_at_ship = True
        ctx.escorts_completed += 1

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

    # Win check is handled by the main game loop — no need to check here


def cmd_drone(ctx: GameContext, args: str):
    """Drone command hub: status, upgrade, charge."""
    sub = args.strip().lower().split(None, 1) if args else []
    sub_cmd = sub[0] if sub else ""
    sub_args = sub[1] if len(sub) > 1 else ""

    if sub_cmd in ("upgrade", "install"):
        _drone_upgrade(ctx, sub_args)
    elif sub_cmd in ("charge", "autocharge"):
        _drone_charge(ctx)
    elif sub_cmd == "status" or not sub_cmd:
        _drone_status(ctx)
    else:
        # Treat unknown sub-command as upgrade attempt (e.g. "drone range_module")
        _drone_upgrade(ctx, args)


def _drone_status(ctx: GameContext):
    """Show drone status panel."""
    drone_dict = ctx.drone.to_dict()
    drone_dict["cargo_used"] = ctx.player.total_items
    ui.show_drone_status(drone_dict, title="ARIA Scout Drone")


def _drone_upgrade(ctx: GameContext, args: str):
    """Install a drone upgrade from inventory."""
    if not args:
        _drone_status(ctx)
        ui.console.print()
        ui.info("Usage: drone upgrade <component>")
        ui.info("Components: " + ", ".join(k.replace("_", " ").title() for k in UPGRADE_EFFECTS))
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
    if upgrade_name == "voice_module":
        sound.set_voice(True)
    sound.play("upgrade")
    ui.success(f"Installed {display}!")
    if result:
        ui.info(f"Effect: {result}")


def _drone_charge(ctx: GameContext):
    """Toggle auto-charge on/off (requires Charge Module upgrade)."""
    if not ctx.drone.charge_module_installed:
        ui.error("No Charge Module installed. Find and install one first.")
        ui.dim("Tip: Use 'ship charging' at the Crash Site to recharge your drone battery.")
        return
    if ctx.drone.auto_charge_enabled:
        ctx.drone.auto_charge_enabled = False
        ui.info("Auto-charge: OFF — drone will not recover battery during travel.")
    else:
        ctx.drone.auto_charge_enabled = True
        sound.play("success")
        ui.success("Auto-charge: ON — drone recovers +5% battery per hour of travel.")
    ctx.do_auto_save()


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


def cmd_stats(ctx: GameContext, args: str):
    """Show session gameplay statistics."""
    if not ctx.stats:
        ui.error("Session stats failed to initialize. Please report this bug.")
        return

    from rich.table import Table

    s = ctx.stats
    table = Table(title="Session Stats", border_style="cyan", show_header=False)
    table.add_column("Stat", style="bold")
    table.add_column("Value")

    table.add_row("Real time", s.elapsed_display)
    table.add_row("Commands typed", str(s.commands))
    table.add_row("Distance traveled", f"{s.km_traveled:.1f} km")
    table.add_row("Creatures talked to", str(len(s.creatures_talked)))
    table.add_row("Hazards survived", str(s.hazards_survived))
    table.add_row("Trades completed", str(s.trades))
    table.add_row("Gifts given", str(s.gifts_given))
    table.add_row("Items collected", str(s.items_collected))
    ui.console.print(table)


def cmd_scores(ctx: GameContext, args: str):
    """Show the local leaderboard (top 10 scores)."""
    from rich.table import Table

    from src.save_load import get_top_scores

    scores = get_top_scores(10)
    if not scores:
        ui.info("No scores recorded yet. Complete a game to see your leaderboard.")
        return

    table = Table(title="Leaderboard — Top 10", border_style="yellow")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Score", style="bold yellow")
    table.add_column("Grade", justify="center")
    table.add_column("Result")
    table.add_column("Mode")
    table.add_column("Time", style="dim")
    table.add_column("Allies", justify="right")
    table.add_column("Date", style="dim")

    grade_colors = {"S": "bold magenta", "A": "bold green", "B": "green", "C": "yellow", "D": "red"}

    for i, s in enumerate(scores, 1):
        gc = grade_colors.get(s["grade"], "white")
        result = "[green]Win[/green]" if s["won"] else "[red]Loss[/red]"
        mode_map = {"short": "Easy", "medium": "Medium", "long": "Hard", "brutal": "Brutal"}
        mode = mode_map.get(s["mode"], s["mode"])
        # Format real time
        rt = s["real_time"]
        if rt < 60:
            time_str = f"{rt}s"
        elif rt < 3600:
            time_str = f"{rt // 60}m"
        else:
            time_str = f"{rt // 3600}h {(rt % 3600) // 60}m"
        game_time = f"{s['hours']}h / {time_str}"
        date = s["date"][:10] if s["date"] else ""
        table.add_row(
            str(i),
            str(s["score"]),
            f"[{gc}]{s['grade']}[/{gc}]",
            result,
            mode,
            game_time,
            str(s["allies"]),
            date,
        )

    ui.console.print(table)


def cmd_ship(ctx: GameContext, args: str):
    at_crash = ctx.player.location_name == "Crash Site"

    if not at_crash:
        ui.show_ship_repair(ctx.repair_checklist)
        ui.warn("Travel to the Crash Site to access ship bays and install materials.")
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
    repair_status = (
        f"[yellow]{installable} materials ready[/yellow]" if installable else "[dim]No materials to install[/dim]"
    )
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

    # Escort progress
    from src.game import ESCORT_REQUIREMENTS

    req = ESCORT_REQUIREMENTS.get(ctx.world_mode, 1)
    esc = ctx.escorts_completed
    esc_color = "green" if esc >= req else "yellow" if esc > 0 else "red"
    table.add_row("Escort help", "Creatures who assisted at ship", f"[{esc_color}]{esc}/{req}[/{esc_color}]")

    ui.console.print(table)
    ui.dim("Usage: ship <bay>  (e.g. 'ship kitchen', 'ship storage')")


def _bay_repair(ctx: GameContext):
    """Install repair materials into the ship."""
    from src.game import ESCORT_REQUIREMENTS, REPAIR_MATERIALS

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

    # Check escort requirement — block if installing would complete repairs but escorts not met
    already_done = sum(1 for v in ctx.repair_checklist.values() if v)
    remaining = len(ctx.repair_checklist) - already_done
    req = ESCORT_REQUIREMENTS.get(ctx.world_mode, 1)

    if len(installable) >= remaining and ctx.escorts_completed < req:
        ui.console.print("\n[bold]Materials ready to install:[/bold]")
        for mat in installable:
            display = mat.replace("_", " ").title()
            ui.console.print(f"  [yellow]{display}[/yellow]")
        ui.console.print()
        ui.warn(f"You need help from {req - ctx.escorts_completed} more creature(s) to complete final repairs.")
        ui.dim(f"  Escort progress: {ctx.escorts_completed}/{req}")
        ui.dim("  Use 'escort' to ask a trusted creature to travel with you, then return here.")
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
            sound.play("repair")
            ui.success(f"Installed {display} into ship repairs!")
            if ctx.dev_mode:
                done = sum(1 for v in ctx.repair_checklist.values() if v)
                ctx.dev_mode.debug("repair_install", material=mat, progress=f"{done}/{len(ctx.repair_checklist)}")
        ctx.do_auto_save()


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

    has_inv = bool(ctx.player.inventory)
    ui.console.print()
    ui.console.print("  [cyan]1[/cyan]. Stash items (inventory \u2192 storage)")
    ui.console.print("  [cyan]2[/cyan]. Retrieve items (storage \u2192 inventory)")
    if has_inv:
        ui.console.print("  [cyan]3[/cyan]. Stash all items")
    ui.console.print(f"  [cyan]{'4' if has_inv else '3'}[/cyan]. Back")

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

    elif choice == "3" and has_inv:
        stashed = []
        for item in list(ctx.player.inventory.keys()):
            qty = ctx.player.inventory[item]
            for _ in range(qty):
                ctx.player.stash_item(item)
            stashed.append(f"{item.replace('_', ' ').title()} x{qty}")
        ui.success(f"Stashed all: {', '.join(stashed)}")

    # Check for junk easter egg (only on stash operations, fire once)
    if choice in ("1", "3") and has_inv and not ctx.easter_egg_announced:
        from src.difficulty import check_junk_easter_egg

        if check_junk_easter_egg(ctx.player, ctx.world_mode):
            ctx.easter_egg_announced = True
            ui.console.print()
            ui.console.print("[bold magenta]Something shifts in the air...[/bold magenta]")
            ui.console.print(
                "[dim magenta]The creatures of Enceladus sense your curiosity. "
                "They seem... friendlier somehow.[/dim magenta]"
            )

    # Back: "3" when no inventory, "4" when inventory exists — both just return


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
            display = item.replace("_", " ").title()

            # Warn if this item is needed for repair
            key = f"material_{item}"
            if key in ctx.repair_checklist and not ctx.repair_checklist[key]:
                ui.warn(f"{display} is needed for ship repair!")
                confirm = ui.console.input("[bold]Cook anyway? (y/n) > [/bold]").strip().lower()
                if confirm not in ("y", "yes"):
                    return

            ctx.player.remove_item(item)
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
    ui.console.print(f"  Drone Battery: [{batt_color}]{batt:.0f}%[/{batt_color}] / {batt_max:.0f}%")

    # Show auto-charge status
    if ctx.drone.charge_module_installed:
        ac_status = "[green]ON[/green]" if ctx.drone.auto_charge_enabled else "[dim]OFF[/dim]"
        ui.console.print(f"  Auto-Charge: {ac_status} (+5%/hr during travel)")
    ui.console.print()

    options = []
    if batt < batt_max:
        options.append(("recharge", "Full recharge (free at Crash Site)"))
    has_power_cell = ctx.player.has_item("power_cell")
    if has_power_cell:
        options.append(("overcharge", "Overcharge with Power Cell (+10% max capacity permanently)"))
    if ctx.drone.charge_module_installed:
        toggle = "OFF" if ctx.drone.auto_charge_enabled else "ON"
        options.append(("toggle", f"Turn auto-charge {toggle}"))
    else:
        options.append(("no_module", "[dim]Auto-charge — no charge module detected[/dim]"))

    options.append(("back", "Back"))

    for i, (_, label) in enumerate(options, 1):
        ui.console.print(f"  [cyan]{i}[/cyan]. {label}")

    try:
        choice = ui.console.input("\n[bold]> [/bold]").strip()
        idx = int(choice) - 1
        if idx < 0 or idx >= len(options):
            return
    except (ValueError, EOFError, KeyboardInterrupt):
        return

    action = options[idx][0]

    if action == "recharge":
        ctx.drone.recharge()
        if ctx.ship_ai:
            ctx.ship_ai.reset_warnings("battery")
        ui.success(f"Drone fully recharged! Battery: {ctx.drone.battery:.0f}%")
    elif action == "overcharge":
        ctx.player.remove_item("power_cell")
        ctx.drone.battery_max += 10.0
        ctx.drone.recharge()
        if ctx.ship_ai:
            ctx.ship_ai.reset_warnings("battery")
        ui.success(f"Power Cell consumed! Battery max: {ctx.drone.battery_max:.0f}%. Battery: {ctx.drone.battery:.0f}%")
    elif action == "toggle":
        ctx.drone.auto_charge_enabled = not ctx.drone.auto_charge_enabled
        if ctx.drone.auto_charge_enabled:
            sound.play("success")
            ui.success("Auto-charge: ON — drone recovers +5% battery per hour of travel.")
        else:
            ui.info("Auto-charge: OFF")
    elif action == "no_module":
        ui.error("No advanced charge module detected. Find and install a Charge Module upgrade.")

    ctx.do_auto_save()


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
        at_crash = ctx.player.location_name == "Crash Site"
        gain = 20 if at_crash else 10
        options.append(("rest", f"Rest and recover (+{gain}% food, +{gain}% water) — costs 1 hour"))

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
                ui.success(f"Suit repaired to {ctx.player.suit_integrity:.0f}%! (Battery: {ctx.drone.battery:.0f}%)")
            elif key == "rest":
                # 1 hour of rest costs resources (same rates as travel)
                ctx.player.food = max(0, ctx.player.food - 2.0)
                ctx.player.water = max(0, ctx.player.water - 3.0)
                ctx.player.suit_integrity = max(0, ctx.player.suit_integrity - 0.5)
                # Recover — same location-based gain as standalone rest
                rest_at_crash = ctx.player.location_name == "Crash Site"
                rest_gain = 20.0 if rest_at_crash else 10.0
                ctx.player.food = min(100.0, ctx.player.food + rest_gain)
                ctx.player.water = min(100.0, ctx.player.water + rest_gain)
                ctx.player.food_warning_given = False
                ctx.player.water_warning_given = False
                ctx.player.hours_elapsed += 1
                if ctx.ship_ai:
                    ctx.ship_ai.reset_warnings("food")
                    ctx.ship_ai.reset_warnings("water")
                ui.success(f"Rested for 1 hour. Food: {ctx.player.food:.0f}%, Water: {ctx.player.water:.0f}%")
    except (ValueError, EOFError, KeyboardInterrupt):
        return


def cmd_rest(ctx: GameContext, args: str):
    """Rest to recover food and water. Better recovery at the Crash Site."""
    at_crash = ctx.player.location_name == "Crash Site"
    food_gain = 20.0 if at_crash else 10.0
    water_gain = 20.0 if at_crash else 10.0

    if ctx.player.food >= 100 and ctx.player.water >= 100:
        ui.info("You're already at full food and water. No need to rest.")
        return

    # 1 hour passes — consume resources first, then apply rest bonus
    ctx.player.food = max(0, ctx.player.food - 2.0)
    ctx.player.water = max(0, ctx.player.water - 3.0)
    ctx.player.suit_integrity = max(0, ctx.player.suit_integrity - 0.5)

    ctx.player.food = min(100.0, ctx.player.food + food_gain)
    ctx.player.water = min(100.0, ctx.player.water + water_gain)
    ctx.player.food_warning_given = False
    ctx.player.water_warning_given = False
    ctx.player.hours_elapsed += 1
    if ctx.ship_ai:
        ctx.ship_ai.reset_warnings("food")
        ctx.ship_ai.reset_warnings("water")

    if at_crash:
        ui.success(f"Rested for 1 hour in the ship. Food: {ctx.player.food:.0f}%, Water: {ctx.player.water:.0f}%")
    else:
        ui.success(f"Rested for 1 hour on the ice. Food: {ctx.player.food:.0f}%, Water: {ctx.player.water:.0f}%")
        ui.dim("(Rest at the Crash Site for better recovery)")


def _sanitize_slot(slot: str) -> str | None:
    """Validate save slot name — prevent path traversal."""
    import re

    slot = slot.strip()
    if not slot or not re.match(r"^[\w\-\.]+$", slot):
        ui.error("Invalid slot name. Use only letters, numbers, hyphens, underscores.")
        return None
    return slot


def cmd_save(ctx: GameContext, args: str):
    slot = _sanitize_slot(args.strip() if args.strip() else "manual")
    if not slot:
        return
    if ctx.dev_mode:
        ctx.dev_mode.debug("save", slot=slot, hours=ctx.player.hours_elapsed)
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

    slot = _sanitize_slot(slot)
    if not slot:
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

    from src.config import CONFIG_PATH, get_save_dir, set_save_dir

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

    if sub.startswith("gpu "):
        from src.config import set_gpu_mode

        value = args.split(maxsplit=1)[1].strip().lower()
        if value in ("auto", "gpu", "cpu"):
            set_gpu_mode(value)
            ui.success(f"GPU mode set to: {value}")
            ui.dim("Takes effect on next game launch.")
        else:
            ui.error("Invalid GPU mode. Use: config gpu auto | gpu | cpu")
        return

    if sub.startswith("context "):
        from src.config import set_context_size

        try:
            value = int(args.split(maxsplit=1)[1].strip())
            if value < 2048:
                ui.error("Minimum context size is 2048.")
                return
            if value > 131072:
                ui.error("Maximum context size is 131072.")
                return
            set_context_size(value)
            ui.success(f"LLM context size set to: {value}")
            ui.dim("Takes effect on next game launch.")
        except ValueError:
            ui.error("Invalid number. Use: config context 8192")
        return

    # Show current config
    from src.config import get_context_size, get_gpu_mode

    ui.console.print("\n[bold]Game Configuration[/bold]")
    ui.console.print(f"  [cyan]Save directory:[/cyan]  {get_save_dir()}")
    ui.console.print(f"  [cyan]GPU mode:[/cyan]        {get_gpu_mode()}")
    ui.console.print(f"  [cyan]Context size:[/cyan]    {get_context_size()}")
    ui.console.print(f"  [cyan]Sound effects:[/cyan]  {'ON' if sound.is_enabled() else 'OFF'}")
    ui.console.print(f"  [cyan]Config file:[/cyan]    {CONFIG_PATH}")
    ui.console.print()
    ui.dim("config savedir /path/to/saves   — change save location")
    ui.dim("config gpu auto|gpu|cpu         — change compute mode")
    ui.dim("config context 8192             — change LLM context window")
    ui.dim("sound                           — toggle sound effects")


def cmd_tutorial(ctx: GameContext, args: str):
    """Replay the ARIA boot sequence and tutorial."""
    from src.tutorial import TutorialManager, TutorialStep

    ctx.tutorial = TutorialManager()
    ctx.tutorial.run_boot_sequence(
        ctx.ship_ai,
        ctx.player,
        ctx.drone,
        ctx.locations,
        ctx.repair_checklist,
        ctx.world_mode,
        replay=True,
    )
    if ctx.tutorial.step < TutorialStep.COMPLETED:
        ui.dim("Tutorial restarted. Follow the prompts.")
    cmd_look(ctx, "")


def cmd_sound(ctx: GameContext, args: str):
    """Toggle system sound effects on/off."""
    from src.config import set_sound_enabled

    if sound.is_enabled():
        sound.disable()
        set_sound_enabled(False)
        ui.info("Sound effects: OFF")
    else:
        sound.enable()
        set_sound_enabled(True)
        sound.play("success")
        ui.info("Sound effects: ON")


def cmd_inspect(ctx: GameContext, args: str):
    """Inspect an item in your inventory to learn what it's used for."""
    if not args:
        ui.info("What do you want to inspect? Usage: inspect <item>")
        return

    from src.difficulty import ITEM_DESCRIPTIONS

    item_name = args.strip().lower().replace(" ", "_")

    if not ctx.player.has_item(item_name):
        display = args.strip().title()
        ui.error(f"You don't have '{display}' in your inventory.")
        return

    display = item_name.replace("_", " ").title()
    desc = ITEM_DESCRIPTIONS.get(item_name)
    if desc:
        ui.console.print(f"\n[bold]{display}[/bold]")
        ui.console.print(f"  {desc}")

        # Show if it's needed for repair
        key = f"material_{item_name}"
        if key in ctx.repair_checklist:
            if ctx.repair_checklist[key]:
                ui.console.print("  [green]Already installed in ship.[/green]")
            else:
                ui.console.print("  [yellow]Needed for ship repair![/yellow]")
    else:
        ui.console.print(f"\n[bold]{display}[/bold]")
        ui.console.print("  A mysterious item. You're not sure what it's for.")
    ui.console.print()


def cmd_charge(ctx: GameContext, args: str):
    """Shortcut for 'drone charge'."""
    _drone_charge(ctx)


def cmd_upgrade(ctx: GameContext, args: str):
    """Shortcut for 'drone upgrade <component>'."""
    _drone_upgrade(ctx, args)


def cmd_screenshot(ctx: GameContext, args: str):
    """Save a screenshot."""
    if not ui._bridge:
        ui.error("Screenshot unavailable (display bridge not initialized).")
        return
    try:
        path = ui._bridge.take_screenshot()
        ui.success(f"Screenshot saved: {path}")
    except Exception as e:
        ui.error(f"Screenshot failed: {e}")


def cmd_quit(ctx: GameContext, args: str):
    ui.console.print("[bold yellow]Are you sure you want to quit? (y/n)[/bold yellow]")
    try:
        confirm = ui.console.input("[bold]Quit? (y/n) > [/bold]").strip().lower()
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
    "trade": cmd_trade,
    "escort": cmd_escort,
    "drone": cmd_drone,
    "upgrade": cmd_upgrade,
    "status": cmd_status,
    "stats": cmd_stats,
    "scores": cmd_scores,
    "leaderboard": cmd_scores,
    "ship": cmd_ship,
    "repair": cmd_ship,
    "rest": cmd_rest,
    "save": cmd_save,
    "load": cmd_load,
    "config": cmd_config,
    "dev": cmd_dev,
    "devmode": cmd_dev,
    "inspect": cmd_inspect,
    "examine": cmd_inspect,
    "tutorial": cmd_tutorial,
    "sound": cmd_sound,
    "charge": cmd_charge,
    "screenshot": cmd_screenshot,
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
        ctx.stats.commands += 1
        handler(ctx, args)
    else:
        ui.error(f"Unknown command: '{cmd}'. Type 'help' for available commands.")
