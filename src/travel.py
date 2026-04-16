"""Travel system: movement, time passage, random events, ARIA commentary."""

import random

from src import ui
from src.drone import Drone
from src.player import Player
from src.world import Location

TRAVEL_EVENTS = [
    "You spot a faint shimmer in the ice — a small crystal, but nothing collectible.",
    "The ground trembles slightly. A distant geyser erupts, painting the sky with vapor.",
    "Saturn looms large on the horizon, its rings catching the faint sunlight.",
    "You pass a field of strange, bioluminescent organisms glowing beneath the ice.",
    "A sudden gust of thin atmosphere sends ice crystals swirling around you.",
    "You notice old tracks in the ice — something large passed this way recently.",
    "The silence is profound. Only the hum of your drone breaks the stillness.",
    "You cross a ridge and catch a breathtaking view of the frozen landscape below.",
    "Your drone chirps — it detected a brief energy signature, but it faded.",
    "The ice here is unusually smooth, like polished glass. You can see your reflection.",
    "A distant rumble echoes through the ice. The moon's core is restless.",
    "You find a small metal fragment half-buried in ice. Too corroded to be useful.",
]

# Atmospheric flavor — small sensory details
ATMOSPHERE_EVENTS = [
    "Fine ice dust swirls across your visor, briefly obscuring your view.",
    "A thin whistle of wind cuts through a crack in a nearby formation.",
    "Something small and pale drifts past your helmet. A frozen microorganism, perhaps.",
    "Your boots crunch through a patch of brittle surface ice. The sound echoes.",
    "Static crackles in your helmet speakers for a moment, then fades.",
    "You feel the ground shift slightly — a subsurface ice plate adjusting.",
    "Frost crystals form on your glove as you brush against an outcrop.",
    "A brief flash of light catches your eye — sunlight refracting through distant ice.",
    "Your suit's temperature readout drops two degrees. A cold pocket.",
    "The vibration of the drone overhead is oddly comforting out here.",
    "A shadow passes overhead. Just Saturn, drifting across the sky.",
    "You catch yourself holding your breath. The silence is that heavy.",
    "Tiny ice moths flutter near a thermal vent, wings catching pale light.",
    "A frozen dust devil spins lazily across the plain ahead of you.",
    "Your helmet fogs briefly from exertion. You wipe it clear and press on.",
]

# ARIA musings — optional commentary during longer trips
ARIA_MUSINGS = [
    "Enceladus has 101 known geysers. I wonder how many are still unmapped.",
    "At 0.0113g, you could theoretically jump 88 meters. I do not recommend testing this.",
    "The subsurface ocean here is estimated at 10 km deep. Earth's deepest trench is only 11.",
    "Saturn's rings are visible even from the surface. Quite the view, Commander.",
    "If my sensors are correct, the ice beneath us is roughly 30 km thick.",
    "I am detecting faint thermal signatures ahead. Probably geological, not biological.",
    "Fun fact: Enceladus orbits Saturn every 32.9 hours. We've been here for several orbits now.",
    "The ambient radiation here is remarkably low. Your suit is more than adequate.",
    "I've been recalibrating my translation matrices during the walk. Quality should improve.",
    "My battery efficiency increases in low gravity. Small mercies.",
    "I sometimes wonder what the creatures here make of us. Probably nothing good.",
    "Commander, do you ever think about how far we are from the nearest cup of coffee?",
]

# Weather/environment updates
WEATHER_UPDATES = [
    "Surface temperature holding at -198°C. Nominal for this region.",
    "Atmospheric trace density increasing slightly. A geyser field may be nearby.",
    "Seismic activity: minor tremors detected 4 km east. No threat to our path.",
    "Wind speed: 2.1 m/s from the north. Negligible at this atmospheric density.",
    "Thermal gradient shifting — we're approaching a warmer subsurface zone.",
    "UV index minimal. Saturn's shadow provides natural shielding here.",
    "Humidity spike detected. Possible subsurface water venting ahead.",
    "Surface albedo increasing — fresh ice. This area may have seen recent geyser activity.",
]

FIND_EVENTS = [
    ("ice_crystal", "You spot a loose ice crystal on the ground and pocket it."),
    ("metal_shard", "A small metal shard glints in the ice. You pick it up."),
]


def calculate_travel_time(distance: float, drone: Drone) -> float:
    """Returns travel time in hours."""
    base_speed = 10.0  # km/h
    speed = base_speed + drone.speed_boost
    return distance / speed


def _build_travel_narration(hours_int: int, rng: random.Random, ship_ai, locations, destination, drone=None, current=None) -> list[str]:
    """Build flavor messages for the journey. Longer trips get more events."""
    narration = []

    # Number of events scales with travel time: 1 event per ~2 hours, min 1, max 5
    num_events = min(5, max(1, hours_int // 2))

    # Build a pool of candidate events weighted by type
    pool: list[tuple[str, str]] = []  # (type, message)

    for msg in TRAVEL_EVENTS:
        pool.append(("event", msg))
    for msg in ATMOSPHERE_EVENTS:
        pool.append(("atmosphere", msg))

    # ARIA handles weather/environment data
    if ship_ai:
        for msg in WEATHER_UPDATES:
            pool.append(("weather", ship_ai.speak(f"[dim]{msg}[/dim]")))

    # Drone handles companion commentary (replaces ARIA musings)
    if drone:
        musing = drone.get_travel_musing(rng)
        if musing:
            pool.append(("drone", musing))
        # Add a second drone musing for longer trips
        if hours_int >= 3:
            musing2 = drone.get_travel_musing(rng)
            if musing2:
                pool.append(("drone", musing2))
    else:
        # Fallback to ARIA musings if no drone
        if ship_ai:
            for msg in ARIA_MUSINGS:
                pool.append(("aria", ship_ai.speak(msg)))

    rng.shuffle(pool)

    # Pick events, avoiding too many of the same type
    selected: list[str] = []
    type_counts: dict[str, int] = {}
    for event_type, msg in pool:
        if len(selected) >= num_events:
            break
        if type_counts.get(event_type, 0) >= 2:
            continue
        selected.append(msg)
        type_counts[event_type] = type_counts.get(event_type, 0) + 1

    # Interleave with "..." separators for pacing
    for i, msg in enumerate(selected):
        if i > 0:
            narration.append("[dim]...[/dim]")
        narration.append(f"[italic]{msg}[/italic]")

    # Route suggestion on longer trips — drone gives this advice now
    if hours_int >= 3 and locations:
        closer = _find_closer_alternative(locations, destination, current)
        if closer:
            narration.append("[dim]...[/dim]")
            if drone:
                narration.append(drone.speak(f"For future reference, {closer} may offer a shorter route to this region."))
            elif ship_ai:
                narration.append(ship_ai.speak(f"For future reference, {closer} may offer a shorter route to this region."))

    return narration


def _find_closer_alternative(locations: list[Location], destination: Location, current: Location | None = None) -> str | None:
    """Find a known location that's close to the destination (potential waypoint)."""
    best_name = None
    best_dist = float("inf")
    for loc in locations:
        if loc.name == destination.name or not loc.discovered:
            continue
        if current and loc.name == current.name:
            continue
        d = destination.distance_to(loc.x, loc.y)
        if 2.0 < d < best_dist and d < 15.0:
            best_dist = d
            best_name = loc.name
    return best_name


def execute_travel(
    player: Player,
    drone: Drone,
    destination: Location,
    current: Location,
    rng: random.Random,
    ship_ai=None,
    locations: list[Location] | None = None,
) -> list[str]:
    """Move player to destination. Returns list of event messages."""
    distance = current.distance_to(destination.x, destination.y)
    hours = calculate_travel_time(distance, drone)
    hours_int = max(1, round(hours))

    # Battery cost
    battery_cost = drone.travel_battery_cost(distance)
    drone.use_battery(battery_cost)

    # Show travel progress (real-time duration scales with game hours, capped)
    real_duration = min(hours_int * 0.3, 3.0)
    ui.travel_progress(destination.name, real_duration)

    # Consume resources
    player.consume_resources(hours_int)

    # Move player
    player.location_name = destination.name
    destination.visited = True
    player.discover_location(destination.name)

    messages = []
    messages.append(f"Arrived at [cyan]{destination.name}[/cyan] after {hours_int}h of travel ({distance:.1f} km).")

    # Travel narration — scales with trip length
    narration = _build_travel_narration(hours_int, rng, ship_ai, locations or [], destination, drone, current)
    messages.extend(narration)

    # Small chance to find an item
    if rng.random() < 0.15 and player.total_items < drone.cargo_capacity:
        item, msg = rng.choice(FIND_EVENTS)
        player.add_item(item)
        messages.append(f"[yellow]{msg}[/yellow]")

    # Food/water source at destination
    if destination.food_source:
        player.replenish_food()
        if ship_ai:
            ship_ai.reset_warnings("food")
        messages.append("[green]You found a renewable food source here! Food fully replenished.[/green]")
    if destination.water_source:
        player.replenish_water()
        if ship_ai:
            ship_ai.reset_warnings("water")
        messages.append("[green]You found a water source here! Water fully replenished.[/green]")

    # Resource warnings — use ARIA if available, fall back to plain text
    if player.food <= 20 and not player.food_warning_given:
        if ship_ai:
            messages.append(ship_ai.speak("Food supplies critically low. Find a food source soon, Commander."))
        else:
            messages.append("[bold red]WARNING: Food supplies critically low! Find a food source soon.[/bold red]")
        player.food_warning_given = True
    if player.water <= 20 and not player.water_warning_given:
        if ship_ai:
            messages.append(ship_ai.speak("Water reserves critically low. Locate a water source immediately."))
        else:
            messages.append("[bold red]WARNING: Water supplies critically low! Find a water source soon.[/bold red]")
        player.water_warning_given = True

    # ARIA post-travel summary
    if ship_ai:
        messages.append(ship_ai.post_travel_summary(player, drone, hours_int, distance))

    # Recharge drone at crash site
    if destination.loc_type == "crash_site":
        drone.recharge()
        if ship_ai:
            ship_ai.reset_warnings("battery")
        messages.append("[magenta]Drone recharged at crash site.[/magenta]")

    return messages
