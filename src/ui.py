"""Rich console output helpers, ASCII art, and styled text."""

import time

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()

TITLE_ART = r"""
[bold cyan]
    __  ___                     ______                         __
   /  |/  /____   ____   ____  /_  __/_____ ____ _ _   __ ___ / /___   _____
  / /|_/ // __ \ / __ \ / __ \  / /  / ___// __ `/| | / // _ \/ // _ \ / ___/
 / /  / // /_/ // /_/ // / / / / /  / /   / /_/ / | |/ //  __/ //  __// /
/_/  /_/ \____/ \____//_/ /_/ /_/  /_/    \__,_/  |___/ \___/_/ \___//_/
[/bold cyan]
[dim]            A survival game on Saturn's moon Enceladus[/dim]
"""

LAUNCH_ART = r"""[bold green]
                        *    .  *       .             *
                   *  .    *    .   *  .    *    .

                              /\
                             /  \
                            / [] \
                           /______\
                           |      |
                           |  ()  |
                           |______|
                          /| /--\ |\
                         / |/    \| \
                        /  ||    ||  \
                       /___|_\  /_|___\
                        [yellow]//// \\\\ ////[/yellow]
                       [yellow]///  \\\\///[/yellow]
                      [red]{{{{[/red][yellow]  [/yellow][red]}}}}[/red][yellow]  [/yellow][red]{{{{[/red]
                     [red]{{{{[/red][yellow]    [/yellow][red]}}}}[/red][yellow]   [/yellow][red]{{{{[/red]
                    [red]{{{{[/red][yellow]      [/yellow][red]}}}}[/red][yellow]    [/yellow][red]{{{{[/red]

[dim]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/dim]
[/bold green]"""

CRASH_ART = r"""[yellow]
        *    .  *       .             *
   *  .    *    .   *  .    *    .
      .  ______|______  .     *
   *    /  ___________  \    .     *
  .    /  /     |     \  \
      |  |  [red]X[/red]  |  [red]X[/red]  |  |   .
   *  |  |_____|_____|  |     *
  .    \_______________/  .
     .  //// ||||| \\\\ .    *
   *   ///   |||||   \\\     .
  ____///____||||| ___\\\_________
 [dim]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/dim]
[/yellow]"""


CREATURE_COLORS = [
    "green",
    "magenta",
    "yellow",
    "cyan",
    "bright_red",
    "bright_green",
    "bright_magenta",
    "bright_cyan",
    "bright_yellow",
    "dark_orange",
    "deep_pink4",
    "spring_green3",
    "steel_blue1",
    "orchid",
    "turquoise2",
    "salmon1",
    "chartreuse3",
    "medium_purple1",
    "hot_pink",
    "dark_sea_green",
]


def show_title():
    console.print(TITLE_ART)


def show_crash():
    console.print(CRASH_ART)


def narrate_lines(lines: list[str], style: str = "italic", pause: float = 0.5):
    """Print multiple lines with pauses between them."""
    for line in lines:
        console.print(f"  [italic]{line}[/italic]")
        time.sleep(pause)
    console.print()


def info(text: str):
    console.print(f"[cyan]{text}[/cyan]")


def warn(text: str):
    console.print(f"[yellow]{text}[/yellow]")


def error(text: str):
    console.print(f"[red]{text}[/red]")


def success(text: str):
    console.print(f"[green]{text}[/green]")


def dim(text: str):
    console.print(f"[dim]{text}[/dim]")


def show_panel(title: str, content: str, style: str = "cyan"):
    console.print(Panel(content, title=title, border_style=style))


def show_location(name: str, loc_type: str, description: str, items: list, creature_name: str | None):
    """Display a location description panel."""
    lines = [f"[italic]{description}[/italic]"]
    if items:
        lines.append(f"\n[yellow]Items here:[/yellow] {', '.join(items)}")
    if creature_name:
        lines.append(f"\n[green]A creature is here:[/green] {creature_name}")
    content = "\n".join(lines)
    type_label = loc_type.replace("_", " ").title()
    console.print(Panel(content, title=f"[bold]{name}[/bold] [{type_label}]", border_style="cyan"))


def show_inventory(items: dict[str, int]):
    if not items:
        info("Your inventory is empty.")
        return

    from src.drone import UPGRADE_EFFECTS
    from src.game import REPAIR_MATERIALS

    # Categorize items
    all_repair = set()
    for mats in REPAIR_MATERIALS.values():
        all_repair.update(mats)
    upgrades = set(UPGRADE_EFFECTS.keys())
    cookable = {"bio_gel", "ice_crystal"}

    table = Table(title="Inventory", border_style="cyan")
    table.add_column("Item", style="yellow")
    table.add_column("Qty", justify="right", style="white")
    table.add_column("Type", style="dim")

    for item, qty in sorted(items.items()):
        display = item.replace("_", " ").title()
        tags = []
        if item in all_repair:
            tags.append("[yellow]repair[/yellow]")
        if item in upgrades:
            tags.append("[magenta]upgrade[/magenta]")
        if item in cookable:
            tags.append("[cyan]cookable[/cyan]")
        tag_str = ", ".join(tags) if tags else "[dim]-[/dim]"
        table.add_row(display, str(qty), tag_str)
    console.print(table)


def show_gps(locations: list[dict], player_x: float, player_y: float):
    """Show known locations with distances."""
    table = Table(title="GPS - Known Locations", border_style="green")
    table.add_column("Location", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Dist (km)", justify="right", style="yellow")
    table.add_column("Resources", style="green")
    table.add_column("Coords", style="dim")

    for loc in sorted(locations, key=lambda x: x["distance"]):
        dist_str = f"{loc['distance']:.1f}"
        coord_str = f"({loc['x']:.0f}, {loc['y']:.0f})"
        type_str = loc["type"].replace("_", " ")
        marker = " [bold green]<< YOU[/bold green]" if loc["distance"] < 0.1 else ""
        resources = []
        if loc.get("food_source"):
            resources.append("\U0001f34e")
        if loc.get("water_source"):
            resources.append("\U0001f6b0")
        resource_str = " ".join(resources)
        table.add_row(loc["name"] + marker, type_str, dist_str, resource_str, coord_str)
    console.print(table)


def show_status(
    food: float,
    water: float,
    hours: int,
    location: str,
    repair_checklist: dict | None = None,
    inventory: dict | None = None,
    suit_integrity: float = 92.0,
):
    table = Table(title="Status", border_style="cyan", show_header=False)
    table.add_column("Stat", style="bold")
    table.add_column("Value")

    food_color = "green" if food > 50 else "yellow" if food > 20 else "red"
    water_color = "green" if water > 50 else "yellow" if water > 20 else "red"
    suit_color = "green" if suit_integrity > 60 else "yellow" if suit_integrity > 30 else "red"

    table.add_row("Location", f"[cyan]{location}[/cyan]")
    table.add_row("Food", f"[{food_color}]{food:.0f}%[/{food_color}]")
    table.add_row("Water", f"[{water_color}]{water:.0f}%[/{water_color}]")
    table.add_row("Suit Integrity", f"[{suit_color}]{suit_integrity:.0f}%[/{suit_color}]")
    table.add_row("Time Elapsed", f"{hours}h")

    # Show repair material checklist if available
    if repair_checklist:
        material_lines = []
        for key, done in repair_checklist.items():
            display = key.replace("_", " ").title()
            if key.startswith("material_"):
                item_key = key[len("material_"):]
                held = inventory.get(item_key, 0) if inventory else 0
                if done:
                    material_lines.append(f"  [green]{display} — DONE[/green]")
                elif held > 0:
                    material_lines.append(f"  [yellow]{display} — IN INVENTORY[/yellow]")
                else:
                    material_lines.append(f"  [red]{display} — NEEDED[/red]")

        done_count = sum(1 for v in repair_checklist.values() if v)
        total = len(repair_checklist)
        table.add_row("Repair", f"{done_count}/{total}")
        console.print(table)

        if material_lines:
            console.print("\n[bold]Repair Materials:[/bold]")
            for line in material_lines:
                console.print(line)
    else:
        console.print(table)


def show_drone_status(drone: dict, title: str = "ARIA Scout Drone"):
    table = Table(title=title, border_style="magenta", show_header=False)
    table.add_column("Stat", style="bold")
    table.add_column("Value")
    table.add_row("Scanner Range", f"{drone['scanner_range']} km")
    table.add_row("Translation", drone["translation_quality"].title())
    table.add_row("Cargo Capacity", f"{drone.get('cargo_used', 0)}/{drone['cargo_capacity']}")
    table.add_row("Speed Boost", f"+{drone['speed_boost']} km/h")
    battery_color = "green" if drone["battery"] > 50 else "yellow" if drone["battery"] > 20 else "red"
    table.add_row("Battery", f"[{battery_color}]{drone['battery']:.0f}%[/{battery_color}]")

    upgrades = drone.get("upgrades_installed", [])
    if upgrades:
        table.add_row("Upgrades", ", ".join(u.replace("_", " ").title() for u in upgrades))
    else:
        table.add_row("Upgrades", "[dim]None[/dim]")
    console.print(table)


def show_ship_repair(checklist: dict):
    table = Table(title="Ship Repair Progress", border_style="yellow")
    table.add_column("Requirement", style="white")
    table.add_column("Status", justify="center")

    for req, done in checklist.items():
        status = "[green]DONE[/green]" if done else "[red]NEEDED[/red]"
        display = req.removeprefix("material_").replace("_", " ").title()
        table.add_row(display, status)

    done_count = sum(1 for v in checklist.values() if v)
    total = len(checklist)
    console.print(table)
    if done_count == total:
        success(f"All repairs complete! ({done_count}/{total})")
    else:
        info(f"Progress: {done_count}/{total}")


def creature_speak(name: str, text: str, color: str = "green"):
    console.print(f"  [{color}]{name}:[/{color}] {text}")


def travel_progress(destination: str, duration: float):
    """Show a progress bar for travel. duration is in seconds (real-time)."""
    steps = 20
    step_time = duration / steps
    with Progress(
        SpinnerColumn(),
        TextColumn(f"Traveling to [cyan]{destination}[/cyan]..."),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("travel", total=steps)
        for _ in range(steps):
            time.sleep(step_time)
            progress.advance(task)


def loading_spinner(message: str, duration: float):
    """Show a spinner for a loading operation."""
    with Progress(
        SpinnerColumn(),
        TextColumn(message),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("loading", total=None)
        time.sleep(duration)


def prompt_choice(prompt_text: str, choices: list[str]) -> str:
    """Show numbered choices and get user selection."""
    console.print(f"\n[bold]{prompt_text}[/bold]")
    for i, choice in enumerate(choices, 1):
        console.print(f"  [cyan]{i}[/cyan]. {choice}")
    while True:
        try:
            raw = console.input("\n[bold]> [/bold]").strip()
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except KeyboardInterrupt:
            console.print()
            raise SystemExit(0)
        except (ValueError, EOFError):
            pass
        error(f"Please enter a number 1-{len(choices)}.")


def get_creature_color(index: int) -> str:
    return CREATURE_COLORS[index % len(CREATURE_COLORS)]


def _bar(value: float, width: int = 10) -> str:
    """Build a colored text bar like ████░░░░░░ for a 0-100 percentage."""
    filled = round(value / 100 * width)
    empty = width - filled
    if value > 50:
        color = "green"
    elif value > 20:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"


def render_status_bar(
    player,
    drone,
    repair_checklist: dict,
    location_type: str = "",
    creature=None,
    followers=None,
):
    """Render a compact status bar above the prompt."""
    food_bar = _bar(player.food, 5)
    water_bar = _bar(player.water, 5)
    suit_bar = _bar(player.suit_integrity, 5)
    batt_bar = _bar(drone.battery, 5)

    # Repair progress
    done = sum(1 for v in repair_checklist.values() if v)
    total = len(repair_checklist)
    repair_color = "green" if done == total else "yellow" if done > 0 else "dim"

    # Location icon
    env_icon = {
        "crash_site": "🛸",
        "plains": "🌊",
        "ridge": "⛰️",
        "cave": "🕳️",
        "geyser_field": "♨️",
        "ice_lake": "❄️",
        "ruins": "🏛️",
        "forest": "🌿",
        "canyon": "🏜️",
        "settlement": "🏘️",
    }.get(location_type, "·")

    # Time display
    hours = player.hours_elapsed
    if hours < 24:
        time_str = f"{hours}h"
    else:
        days = hours // 24
        rem = hours % 24
        time_str = f"{days}d{rem}h"

    # Inventory count
    inv_count = player.total_items
    inv_max = drone.cargo_capacity

    if location_type == "crash_site":
        # Full vitals at Crash Site
        line = (
            f" {env_icon} "
            f"[dim]Food[/dim] {food_bar} [dim]{player.food:.0f}%[/dim]  "
            f"[dim]Water[/dim] {water_bar} [dim]{player.water:.0f}%[/dim]  "
            f"[dim]Suit[/dim] {suit_bar} [dim]{player.suit_integrity:.0f}%[/dim]  "
            f"[dim]Batt[/dim] {batt_bar} [dim]{drone.battery:.0f}%[/dim]  "
            f"[{repair_color}]Ship {done}/{total}[/{repair_color}]  "
            f"[dim]Inv {inv_count}/{inv_max}[/dim]  "
            f"[dim]⏱ {time_str}[/dim]"
        )
        console.print(line)

        # Ship bay summary
        stored = sum(player.ship_storage.values()) if player.ship_storage else 0
        bays = []
        bays.append(f"Storage:{stored}")
        bays.append("Kitchen")
        bays.append("Charging")
        bays.append("Medical")
        remaining = sum(1 for v in repair_checklist.values() if not v)
        if remaining:
            bays.append(f"[yellow]Repair:{remaining} remaining[/yellow]")
        else:
            bays.append("[green]Repair:Done[/green]")
        console.print(f" [dim]🔧 Ship Bays:[/dim] {' │ '.join(bays)}")
    else:
        # Exploring bar — always show all vitals for ambient awareness
        parts = [f" {env_icon} "]
        parts.append(f"[dim]Food[/dim] {food_bar} [dim]{player.food:.0f}%[/dim]  ")
        parts.append(f"[dim]Water[/dim] {water_bar} [dim]{player.water:.0f}%[/dim]  ")
        parts.append(f"[dim]Suit[/dim] {suit_bar} [dim]{player.suit_integrity:.0f}%[/dim]  ")
        parts.append(f"[dim]Batt[/dim] {batt_bar} [dim]{drone.battery:.0f}%[/dim]  ")
        parts.append(f"[dim]Inv {inv_count}/{inv_max}[/dim]  ")
        parts.append(f"[dim]⏱ {time_str}[/dim]")
        console.print("".join(parts))

    # Creature at location
    if creature and not creature.following:
        trust = creature.trust
        trust_bar = _bar(trust, 5)
        disp = creature.disposition
        disp_color = {"friendly": "green", "neutral": "yellow", "hostile": "red"}.get(disp, "dim")
        console.print(
            f" [dim]👾[/dim] [{creature.color}]{creature.name}[/{creature.color}] "
            f"[dim]{creature.species} · {creature.archetype}[/dim]  "
            f"[{disp_color}]{disp}[/{disp_color}]  "
            f"[dim]Trust[/dim] {trust_bar} [dim]{trust}/100[/dim]"
        )

    # Followers
    if followers:
        names = [f"[{c.color}]{c.name}[/{c.color}]" for c in followers]
        console.print(f" [dim]🤝 Following:[/dim] {', '.join(names)}")
