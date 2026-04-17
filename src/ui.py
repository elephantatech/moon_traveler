"""Rich console output helpers, ASCII art, and styled text."""

import time

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

_real_console = Console()
_bridge = None  # Set by tui_app when Textual mode is active


def set_bridge(bridge):
    """Wire up the Textual UIBridge. Called once by tui_app on startup."""
    global _bridge, console
    _bridge = bridge
    console = _BridgeConsoleShim()


class _BridgeConsoleShim:
    """Drop-in replacement for Rich Console that routes through UIBridge.

    When the bridge is set (Textual mode), print() goes to the RichLog widget
    and input() blocks via the bridge's ask queue. When no bridge is set,
    falls back to the real Rich Console.
    """

    def print(self, *args, **kwargs):
        if _bridge:
            _bridge.print(*args, **kwargs)
        else:
            _real_console.print(*args, **kwargs)

    def input(self, prompt: str = "") -> str:
        if _bridge:
            return _bridge.input(prompt)
        return _real_console.input(prompt)

    def clear(self):
        if _bridge:
            _bridge.clear()
        else:
            _real_console.clear()


console = _real_console  # Default to real console; overridden by set_bridge()

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


def _safe_sound(event: str):
    """Play a sound, never crash the game."""
    try:
        from src import sound

        sound.play(event)
    except Exception:
        pass


def show_title():
    _safe_sound("boot")
    console.print(TITLE_ART)


def show_crash():
    _safe_sound("damage")
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
    _safe_sound("warning")
    console.print(f"[yellow]{text}[/yellow]")


def error(text: str):
    _safe_sound("error")
    console.print(f"[red]{text}[/red]")


def success(text: str):
    _safe_sound("success")
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
                item_key = key[len("material_") :]
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

    if drone.get("voice_enabled"):
        table.add_row("Voice", "[green]Enabled[/green]")
    if drone.get("autopilot_enabled"):
        table.add_row("Autopilot", "[green]Enabled[/green]")
    if drone.get("charge_module_installed"):
        ac = "[green]ON[/green]" if drone.get("auto_charge_enabled") else "[dim]OFF[/dim]"
        table.add_row("Auto-Charge", ac)

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
    from rich.markup import escape

    console.print(f"  [{color}]{escape(name)}:[/{color}] {escape(text)}")


def travel_progress(destination: str, duration: float):
    """Show a progress bar for travel. duration is in seconds (real-time)."""
    if _bridge:
        # TUI mode: single line before/after (RichLog can't animate in-place)
        _bridge.print(f"  [dim]Traveling to[/dim] [cyan]{destination}[/cyan][dim]...[/dim]")
        time.sleep(duration)
        _bridge.print(f"  [green]Arrived at {destination}.[/green]")
        return

    steps = 20
    step_time = duration / steps
    with Progress(
        SpinnerColumn(),
        TextColumn(f"Traveling to [cyan]{destination}[/cyan]..."),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=_real_console,
    ) as progress:
        task = progress.add_task("travel", total=steps)
        for _ in range(steps):
            time.sleep(step_time)
            progress.advance(task)


def loading_spinner(message: str, duration: float):
    """Show a spinner for a loading operation."""
    if _bridge:
        _bridge.print(f"  {message}")
        time.sleep(duration)
        return

    with Progress(
        SpinnerColumn(),
        TextColumn(message),
        console=_real_console,
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
            raise
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


def _bar_html(value: float, width: int = 5) -> str:
    """Build a colored bar as prompt_toolkit HTML."""
    filled = round(value / 100 * width)
    empty = width - filled
    if value > 50:
        color = "#5caa78"  # green
    elif value > 20:
        color = "#c8a844"  # yellow
    else:
        color = "#c85050"  # red
    bar = "█" * filled
    gap = "░" * empty
    return f'<style fg="{color}">{bar}</style><style fg="#4a5070">{gap}</style>'


def _vital_html(label: str, value: float, color: str) -> str:
    """Format a single vital stat as colored HTML."""
    bar = _bar_html(value)
    return f'<style fg="{color}">{label}</style> {bar} <style fg="#8890b0">{value:.0f}%</style>'


# Module-level status bar HTML for prompt_toolkit bottom_toolbar
_status_bar_html: str = ""


def get_toolbar_text() -> str:
    """Return the current status bar as HTML for prompt_toolkit bottom_toolbar."""
    return _status_bar_html


def _rich_vital(label: str, value: float, label_color: str) -> str:
    """Format a single vital as Rich markup for Textual status bar."""
    bar = _bar(value, 5)
    return f"[{label_color}]{label}[/{label_color}] {bar} [dim]{value:.0f}%[/dim]"


def render_status_bar(
    player,
    drone,
    repair_checklist: dict,
    location_type: str = "",
    creature=None,
    followers=None,
):
    """Update the fixed bottom status bar (Textual widget or prompt_toolkit toolbar)."""
    global _status_bar_html

    done = sum(1 for v in repair_checklist.values() if v)
    total = len(repair_checklist)

    hours = player.hours_elapsed
    time_str = f"{hours}h" if hours < 24 else f"{hours // 24}d{hours % 24}h"

    inv_count = player.total_items
    inv_max = drone.cargo_capacity

    ship_color = "green" if done == total else "yellow" if done > 0 else "red"

    # --- Textual mode: Rich markup → StatusBar widget ---
    if _bridge:
        parts = [
            _rich_vital("Food", player.food, "green"),
            _rich_vital("Water", player.water, "cyan"),
            _rich_vital("Suit", player.suit_integrity, "#c89450"),
            _rich_vital("Batt", drone.battery, "#a080d0"),
            f"[{ship_color}]Ship {done}/{total}[/{ship_color}]",
            f"[dim]Inv {inv_count}/{inv_max}[/dim]",
            f"[dim]⏱ {time_str}[/dim]",
        ]
        markup = "  ".join(parts)

        if creature and not creature.following:
            from rich.markup import escape

            trust_bar = _bar(creature.trust, 5)
            dc = {"friendly": "green", "neutral": "yellow", "hostile": "red"}.get(creature.disposition, "dim")
            markup += (
                f"  [dim]│[/dim]  [bold]{escape(creature.name)}[/bold] "
                f"[dim]{escape(creature.archetype)}[/dim] [{dc}]{creature.disposition}[/{dc}] "
                f"Trust {trust_bar} [dim]{creature.trust}[/dim]"
            )

        if followers:
            from rich.markup import escape

            names = " ".join(f"[bold]{escape(c.name)}[/bold]" for c in followers)
            markup += f"  [dim]│[/dim]  [dim]Following:[/dim] {names}"

        _bridge.update_status_bar(markup)
        return

    # --- CLI mode: prompt_toolkit HTML → bottom_toolbar ---
    html_ship_color = {"green": "#5caa78", "yellow": "#c8a844", "red": "#c85050"}[ship_color]

    parts = [
        _vital_html("Food", player.food, "#5caa78"),
        _vital_html("Water", player.water, "#5ca8c8"),
        _vital_html("Suit", player.suit_integrity, "#c89450"),
        _vital_html("Batt", drone.battery, "#a080d0"),
        f'<style fg="{html_ship_color}">Ship {done}/{total}</style>',
        f'<style fg="#7880a0">Inv {inv_count}/{inv_max}</style>',
        f'<style fg="#606888">⏱ {time_str}</style>',
    ]

    html = "  ".join(parts)

    if creature and not creature.following:
        trust_bar = _bar_html(creature.trust)
        disp_colors = {"friendly": "#5caa78", "neutral": "#c8a844", "hostile": "#c85050"}
        dc = disp_colors.get(creature.disposition, "#7880a0")
        html += (
            f'  <style fg="#4a5070">│</style>  '
            f'<style fg="#b4bcd4">{creature.name}</style> '
            f'<style fg="#7880a0">{creature.archetype}</style> '
            f'<style fg="{dc}">{creature.disposition}</style> '
            f'Trust {trust_bar} <style fg="#8890b0">{creature.trust}</style>'
        )

    if followers:
        names = " ".join(f'<style fg="#b4bcd4">{c.name}</style>' for c in followers)
        html += f'  <style fg="#4a5070">│</style>  <style fg="#7880a0">Following:</style> {names}'

    _status_bar_html = html
