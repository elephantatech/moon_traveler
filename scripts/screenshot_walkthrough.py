#!/usr/bin/env python3
"""Scripted walkthrough that exports each game screen as an SVG file using Rich."""

import sys

sys.path.insert(0, ".")

from pathlib import Path

from rich.console import Console

from src import ui
from src.commands import (
    HELP_TEXT,
    _show_bay_menu,
    cmd_give,
    cmd_gps,
    cmd_inventory,
    cmd_look,
    cmd_scan,
    cmd_status,
    cmd_take,
)
from src.game import init_game
from src.llm import fallback_response
from src.travel import execute_travel

ASSETS_DIR = Path("assets")
TERM_WIDTH = 100


class ScreenshotCapture:
    """Captures Rich output to an SVG file."""

    def __init__(self):
        self.screenshots = []

    def capture(self, title: str, render_fn):
        """Run render_fn with a recording console, then save SVG."""
        record_console = Console(
            width=TERM_WIDTH,
            record=True,
            force_terminal=True,
            color_system="truecolor",
        )
        # Temporarily swap the global console
        original = ui.console
        ui.console = record_console
        try:
            render_fn(record_console)
        finally:
            ui.console = original

        # Export SVG
        slug = title.lower().replace(" ", "-").replace("/", "-").replace("—", "").replace("(", "").replace(")", "")
        slug = "-".join(slug.split())
        filename = f"screenshot-{slug}.svg"
        path = ASSETS_DIR / filename
        svg = record_console.export_svg(title=f"Moon Traveler CLI — {title}")
        path.write_text(svg)
        self.screenshots.append((title, filename))
        print(f"  Saved: {path}")


def show_status_bar(ctx, console):
    loc = ctx.current_location()
    creature_here = ctx.creature_at_location(loc.name)
    followers = [c for c in ctx.creatures if c.following]
    # Render directly to the given console
    from src.ui import render_status_bar
    original = ui.console
    ui.console = console
    render_status_bar(ctx.player, ctx.drone, ctx.repair_checklist, loc.loc_type, creature_here, followers)
    ui.console = original


def show_prompt(ctx, console, cmd=""):
    loc = ctx.player.location_name
    if cmd:
        console.print(f"[bold cyan]{loc}[/bold cyan] [bold]>[/bold] {cmd}")
    else:
        console.print(f"[bold cyan]{loc}[/bold cyan] [bold]>[/bold]")


def main():
    print("Moon Traveler CLI — Generating Screenshots\n")

    cap = ScreenshotCapture()
    ctx = init_game("short", seed=42)
    ctx.tutorial.step = ctx.tutorial.step.__class__["COMPLETED"]

    # 1. Title Screen
    def render_title(c):
        c.print(ui.TITLE_ART)
        c.print()
        c.print("[dim]  Choose: 1. New Game  2. Load Game[/dim]")
    cap.capture("Title Screen", render_title)

    # 2. Crash Site — First Look
    def render_crash_look(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "look")
        cmd_look(ctx, "")
    cap.capture("Crash Site — First Look", render_crash_look)

    # 3. Scanning
    def render_scan(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "scan")
        cmd_scan(ctx, "")
    cap.capture("Scanning for Locations", render_scan)

    # 4. GPS
    def render_gps(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "gps")
        cmd_gps(ctx, "")
    cap.capture("GPS Map View", render_gps)

    # 5. Drone Status
    def render_drone(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "drone")
        drone_dict = ctx.drone.to_dict()
        drone_dict["cargo_used"] = ctx.player.total_items
        ui.show_drone_status(drone_dict, title="ARIA Scout Drone")
    cap.capture("Drone Status", render_drone)

    # 6. Travel
    def render_travel(c):
        show_prompt(ctx, c, "travel Azure Warren")
        cur = ctx.current_location()
        dest = ctx.find_location("Azure Warren")
        messages = execute_travel(ctx.player, ctx.drone, dest, cur, ctx.rng, ctx.ship_ai, ctx.locations)
        for msg in messages:
            c.print(msg)
    cap.capture("Traveling to a Location", render_travel)

    # 7. Location with Creature
    def render_location(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "look")
        cmd_look(ctx, "")
    cap.capture("Location with Creature and Items", render_location)

    # 8. Taking Items
    def render_take(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "take ice_crystal")
        cmd_take(ctx, "ice_crystal")
        show_prompt(ctx, c, "take power_cell")
        cmd_take(ctx, "power_cell")
        c.print()
        show_prompt(ctx, c, "inventory")
        cmd_inventory(ctx, "")
    cap.capture("Taking Items and Inventory", render_take)

    # 9. Player Status
    def render_status(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "status")
        cmd_status(ctx, "")
    cap.capture("Player Status", render_status)

    # 10. Giving Gifts
    creature = ctx.creature_at_location(ctx.player.location_name)
    def render_give(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, f"give power_cell to {creature.name}")
        cmd_give(ctx, f"power_cell to {creature.name}")
    cap.capture("Giving a Gift to Build Trust", render_give)

    # 11. Conversation
    def render_talk(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, f"talk {creature.name}")
        c.print(
            f"\n[bold]── ARIA Communicator ── [{creature.color}]{creature.name}[/{creature.color}]"
            f" ({creature.species}, {creature.archetype})[/bold]"
        )
        c.print(
            f"[dim]Trust: {creature.trust}/100 ({creature.trust_level})"
            " — 'bye' or '/end' to disconnect | /? for help[/dim]\n"
        )
        tip = ctx.drone.get_interaction_advice(creature, ctx.rng)
        if tip:
            c.print(tip)
        c.print()
        c.print("[bold]You>[/bold] Hello, I come in peace. Can you help me?")
        response = fallback_response(creature, ctx.rng)
        ui.creature_speak(creature.name, response, creature.color)
        creature.add_trust(3)
        c.print()
        c.print("[bold]You>[/bold] I need to repair my ship. Do you know where I can find bio gel?")
        response = fallback_response(creature, ctx.rng)
        ui.creature_speak(creature.name, response, creature.color)
        creature.add_trust(3)
        c.print()
        c.print("[bold]You>[/bold] bye")
        c.print(f"[cyan]You step away from {creature.name}.[/cyan]")
    cap.capture("Creature Conversation", render_talk)

    # 12. Escort
    def render_escort(c):
        creature.trust = 55
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "escort")
        c.print(
            f"\n[bold]Ask [{creature.color}]{creature.name}[/{creature.color}]"
            " to travel with you?[/bold]"
        )
        c.print("[bold](y/n) > [/bold]y")
        creature.following = True
        creature.home_location = creature.location_name
        c.print(f"[green]{creature.name} agrees to travel with you![/green]")
        c.print(ctx.ship_ai.speak(
            f"Excellent, Commander. {creature.name} may be able to assist with repairs at the ship."
        ))
    cap.capture("Escort System", render_escort)

    # 13. Status Bar with Follower
    def render_follower(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c)
    cap.capture("Status Bar with Follower", render_follower)

    # 14. Ship Bays
    ctx.player.location_name = "Crash Site"
    for cr in ctx.creatures:
        if cr.following:
            cr.location_name = "Crash Site"
    ctx.player.add_item("bio_gel")
    ctx.player.add_item("ice_crystal", 2)
    ctx.player.ship_storage = {"metal_shard": 2, "antenna_array": 1}

    def render_ship(c):
        show_status_bar(ctx, c)
        show_prompt(ctx, c, "ship")
        ui.show_ship_repair(ctx.repair_checklist)
        c.print()
        _show_bay_menu(ctx)
    cap.capture("Ship Bays Menu", render_ship)

    # 15. Repair Progress
    def render_repair(c):
        ctx.repair_checklist["material_ice_crystal"] = True
        ctx.player.remove_item("ice_crystal")
        c.print("[green]Installed Ice Crystal into ship repairs![/green]")
        c.print()
        ui.show_ship_repair(ctx.repair_checklist)
    cap.capture("Ship Repair Progress", render_repair)

    # 16. Victory Screen
    def render_victory(c):
        c.print()
        c.print("[bold green]" + "=" * 60 + "[/bold green]")
        win_lines = [
            "  The final component clicks into place.",
            "  Your ship groans, then hums with renewed energy.",
            "",
            "  Systems online. Hull integrity: stable.",
            "  Fuel cells: charged. Navigation: locked.",
            "",
            "  You take one last look at the frozen landscape of Enceladus.",
            "  The creatures who helped you watch from a distance.",
        ]
        for line in win_lines:
            c.print(f"  [italic]{line}[/italic]")
        c.print(ui.LAUNCH_ART)
        launch_lines = [
            "  The thrusters ignite. The ice beneath you melts and steams.",
            "  You rise — slowly at first, then faster, breaking free",
            "  of the moon's gentle gravity.",
            "",
            "  Enceladus shrinks below you, a pale jewel against Saturn's rings.",
            "",
            f"  Time survived: {ctx.player.hours_elapsed} hours.",
            "",
            "  You made it home.",
        ]
        for line in launch_lines:
            c.print(f"  [italic]{line}[/italic]")
        c.print("[bold green]" + "=" * 60 + "[/bold green]")
        c.print("\n[bold]MISSION COMPLETE[/bold]\n")
    cap.capture("Victory", render_victory)

    # 17. Game Over Screen
    def render_gameover(c):
        c.print()
        c.print("[bold red]" + "=" * 60 + "[/bold red]")
        lose_lines = [
            "  Your vision blurs. The cold seeps deeper.",
            "  The drone chirps a warning you can barely hear.",
            "",
            "  You collapse onto the ice, exhausted and depleted.",
            "  The last thing you see is Saturn's rings, shimmering above.",
            "",
            f"  Time survived: {ctx.player.hours_elapsed} hours.",
            "",
            "  The ice claims another visitor.",
        ]
        for line in lose_lines:
            c.print(f"  [italic]{line}[/italic]")
        c.print("[bold red]" + "=" * 60 + "[/bold red]")
        c.print("\n[bold]GAME OVER[/bold]\n")
    cap.capture("Game Over", render_gameover)

    # 18. Dev Mode
    def render_dev(c):
        ctx.dev_mode.enabled = True
        ctx.dev_mode.render_panel(ctx)
    cap.capture("Dev Mode Diagnostics", render_dev)

    # 19. Help
    def render_help(c):
        c.print(HELP_TEXT)
    cap.capture("Help Screen", render_help)

    # Summary
    print(f"\nGenerated {len(cap.screenshots)} screenshots in {ASSETS_DIR}/:")
    for title, filename in cap.screenshots:
        print(f"  {filename:50s} — {title}")

    # Clean up old hand-crafted screenshots that are now replaced
    old_files = [
        "screenshot-gameplay.svg",
        "screenshot-ship.svg",
        "screenshot-scan.svg",
        "screenshot-travel.svg",
        "screenshot-escort.svg",
    ]
    for old in old_files:
        old_path = ASSETS_DIR / old
        if old_path.exists():
            # Check if it was replaced by a new file with similar name
            replaced = any(old in f for _, f in cap.screenshots)
            if not replaced:
                old_path.unlink()
                print(f"  Removed old: {old}")


if __name__ == "__main__":
    main()
