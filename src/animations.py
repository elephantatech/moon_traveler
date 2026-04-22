"""Simple ASCII frame animations using a dedicated animation widget.

Animations play in the #animation-bar Static widget, which updates
in-place. The RichLog stays append-only for game text.

Each animation checks config before playing. If disabled, the function
either does nothing or falls back to a minimal static message.
"""

import time

from src import ui

_LATE_GAME_HOURS = 24
_force_disabled = False


def force_disable():
    """Disable animations for the current session (does not persist to config)."""
    global _force_disabled
    _force_disabled = True


def force_enable():
    """Re-enable animations after force_disable (for screenshot captures)."""
    global _force_disabled
    _force_disabled = False


def _enabled() -> bool:
    if _force_disabled:
        return False
    from src.config import get_animations_enabled

    return get_animations_enabled()


def _can_animate() -> bool:
    """Check if the animation widget is available (TUI mode with bridge)."""
    return _enabled() and hasattr(ui.console, "animate_frame")


def _animate(frames: list[str], delay: float = 0.2, clear: bool = True):
    """Play frames in the animation bar widget.

    Each frame replaces the previous one in-place.
    Clears the widget after the last frame unless clear=False.
    """
    if not _can_animate() or not frames:
        return
    for frame in frames:
        ui.console.animate_frame(frame)
        time.sleep(delay)
    # Hold the last frame so the player can read it
    time.sleep(0.6)
    if clear:
        ui.console.clear_animation()


# --- Beat (absorption pause) ---


def beat(duration: float = 0.8):
    """Pause to let the player absorb output. No printed output."""
    if not _enabled():
        return
    time.sleep(duration)


# --- Scan animation ---


def scan_sweep(hours_elapsed: int = 0):
    """Animated scan sequence in the animation bar."""
    if not _can_animate():
        ui.console.print("  Scanning surroundings...")
        time.sleep(0.5)
        return

    spin = [".", "-", "+", "|", "\\", "/"]
    frames = []
    for i, ch in enumerate(spin):
        frames.append(f"[dim]  (({ch}))  (({ch}))\n  Scanning...[/dim]")
    if hours_elapsed >= _LATE_GAME_HOURS:
        frames.append("[yellow]  ((!))  ((!))\n  Interference...[/yellow]")
        frames.append(f"[dim]  (({spin[-1]}))  (({spin[-1]}))\n  Scanning...[/dim]")
    frames.append("[cyan]  ((*))  ((*))\n  Scan complete.[/cyan]")

    _animate(frames, delay=0.35)


# --- Travel animation ---


def travel_sequence(
    destination: str,
    duration: float,
    distance: float,
    hours_elapsed: int = 0,
    upgrade_count: int = 0,
):
    """Animated travel — drone sprite moves in-place in the animation bar."""
    if not _can_animate():
        ui.console.print(f"  [dim]Traveling to[/dim] [cyan]{destination}[/cyan][dim]...[/dim]")
        time.sleep(duration)
        ui.console.print(f"  [green]Arrived at {destination}.[/green]")
        return

    field_width = min(40, max(14, round(distance * 1.5)))
    frame_count = min(8, max(3, round(distance / 4)))
    sleep_per = max(0.35, duration / frame_count)
    sprite_width = 13  # [o]--(+)--[o] is 13 chars

    # Drone sprite — eyes upgrade o→O, belly fills [] per upgrade
    # Rich markup eats [x] as tags — escape all [ with \[
    eye = "O" if upgrade_count > 0 else " "
    drone_top = f"\\[{eye}]--(+)--\\[{eye}]"
    # 9-char belly: fill [] from outside in (left, right, left, right...)
    belly = list("_________")  # 9 chars, indices 0-8
    slots = [0, 7, 2, 5]  # pairs: (0,1), (7,8), (2,3), (5,6) — outside in
    for i in range(min(upgrade_count, 4)):
        s = slots[i]
        belly[s] = "["
        belly[s + 1] = "]"
    belly_str = "".join(belly).replace("[", "\\[")
    drone_bot = " \\" + belly_str + "/"

    # Departure message in the game log
    ui.console.print(f"  [dim]Departing for[/dim] [cyan]{destination}[/cyan] [dim]({distance:.1f} km)...[/dim]")

    # Drone moves across the animation bar (2-line sprite)
    travel_width = max(1, field_width - sprite_width)
    for i in range(frame_count):
        pos = round(i / max(1, frame_count - 1) * travel_width)
        pad = " " * pos
        if hours_elapsed >= _LATE_GAME_HOURS and i == frame_count // 2:
            ui.console.animate_frame(f"[yellow]{pad} ~!~ ~!~ ~!~\n{pad} ~~~~~~~~~~~[/yellow]")
        else:
            ui.console.animate_frame(f"[magenta]{pad} {drone_top}\n{pad} {drone_bot}[/magenta]")
        time.sleep(sleep_per)

    # Hold final position, then arrival
    time.sleep(0.5)
    ui.console.clear_animation()
    ui.console.print(f"  [green]Arrived at {destination}.[/green]")


# --- Look animation ---


def look_sweep():
    """Binoculars sweep in the animation bar."""
    if not _can_animate():
        return

    _animate(
        [
            "[dim] .---. .---.\n (o  )-(o  )[/dim]",
            "[dim] .---. .---.\n ( o )-( o )[/dim]",
            "[dim] .---. .---.\n (  o)-(  o)[/dim]",
            "[dim] .---. .---.\n ( o )-( o )[/dim]",
            "[cyan] .---. .---.\n ( o )-( o )[/cyan]",
        ],
        delay=0.35,
    )


# --- Drone transmission ---


def drone_transmit(style: str = "speak"):
    """Brief animation in the animation bar before a key drone message."""
    if not _can_animate():
        return

    if style == "alert":
        _animate(
            [
                "[bold yellow]  /!\\\n  !![/bold yellow]",
                "[bold yellow]  /!\\\n  !! ALERT !![/bold yellow]",
            ],
            delay=0.4,
        )
    elif style == "whisper":
        _animate(["[dim magenta] <*>\n . . .[/dim magenta]"], delay=0.5)
    else:
        _animate(
            [
                "[dim magenta] <*>\n <<[/dim magenta]",
                "[magenta] <*>\n << DRONE >>[/magenta]",
            ],
            delay=0.4,
        )


# --- Hazard flash ---


def hazard_flash(hours_elapsed: int = 0):
    """Danger flash in the animation bar."""
    if not _can_animate():
        return

    if hours_elapsed >= _LATE_GAME_HOURS:
        _animate(
            [
                "[bold red]  /!\\\n ! ! ! ! ![/bold red]",
                "[bold red]  /!\\\n !!! HAZARD !!![/bold red]",
                "[bold red]  /!\\\n ! ! ! ! ![/bold red]",
            ],
            delay=0.35,
        )
    else:
        _animate(
            [
                "[bold red]  /!\\\n ! ! ![/bold red]",
                "[red]  /!\\\n \u2014 HAZARD \u2014[/red]",
            ],
            delay=0.4,
        )


# --- Exchange flash (give/trade) ---


def exchange_flash():
    """Small success flash in the animation bar."""
    if not _can_animate():
        return

    _animate(["[green]  +-+\n * * *[/green]"], delay=0.5)


# --- Model loading ---


def model_loading():
    """In-place animation in the animation bar before blocking Llama() call."""
    if not _can_animate():
        return

    _animate(
        [
            "[dim] <*>\n [ .   ] Initializing model...[/dim]",
            "[dim] <*>\n [ . . ] Allocating memory...[/dim]",
            "[dim] <*>\n [ . . . ] Loading weights...[/dim]",
        ],
        delay=0.5,
        clear=False,  # Keep showing "Loading weights..." during the blocking call
    )
