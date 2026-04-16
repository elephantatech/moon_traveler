"""Rich console output helpers, ASCII art, and styled text."""

import time

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

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


def narrate(text: str, style: str = "italic", delay: float = 0.02):
    """Print text character-by-character for narrative effect."""
    styled = Text(style=style)
    for char in text:
        styled.append(char)
        console.print(styled, end="\r")
        time.sleep(delay)
    console.print(styled)
    console.print()


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
    table = Table(title="Inventory", border_style="cyan")
    table.add_column("Item", style="yellow")
    table.add_column("Qty", justify="right", style="white")
    for item, qty in sorted(items.items()):
        table.add_row(item.replace("_", " ").title(), str(qty))
    console.print(table)


def show_gps(locations: list[dict], player_x: float, player_y: float):
    """Show known locations with distances."""
    table = Table(title="GPS - Known Locations", border_style="green")
    table.add_column("Location", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Dist (km)", justify="right", style="yellow")
    table.add_column("Coords", style="dim")

    for loc in sorted(locations, key=lambda x: x["distance"]):
        dist_str = f"{loc['distance']:.1f}"
        coord_str = f"({loc['x']:.0f}, {loc['y']:.0f})"
        type_str = loc["type"].replace("_", " ")
        marker = " [bold green]<< YOU[/bold green]" if loc["distance"] < 0.1 else ""
        table.add_row(loc["name"] + marker, type_str, dist_str, coord_str)
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
    table.add_row("Cargo Capacity", f"{drone['cargo_used']}/{drone['cargo_capacity']}")
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
        table.add_row(req.replace("_", " ").title(), status)

    done_count = sum(1 for v in checklist.values() if v)
    total = len(checklist)
    console.print(table)
    if done_count == total:
        success(f"All repairs complete! ({done_count}/{total})")
    else:
        info(f"Progress: {done_count}/{total}")


def creature_speak(name: str, text: str, color: str = "green"):
    console.print(f"  [{color}]{name}:[/{color}] {text}")


def drone_speak(text: str):
    """Print drone-formatted speech."""
    console.print(f"[bold magenta]DRONE:[/bold magenta] [white]{text}[/white]")


def drone_whisper(text: str):
    """Print a private drone message (only the player sees this)."""
    console.print(f"  [dim magenta]< DRONE >[/dim magenta] [dim italic]{text}[/dim italic]")


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
        except (ValueError, EOFError):
            pass
        error(f"Please enter a number 1-{len(choices)}.")


def get_creature_color(index: int) -> str:
    return CREATURE_COLORS[index % len(CREATURE_COLORS)]
