"""Developer diagnostics overlay — session-only, not saved."""

import math

from rich.table import Table
from rich.tree import Tree

from src import ui


class DevMode:
    """Toggle-able diagnostics panel. Session-only — never persisted."""

    def __init__(self):
        self.enabled = False

    def toggle(self):
        self.enabled = not self.enabled

    def render_panel(self, ctx):
        """Print a diagnostics table with system + game state info."""
        if not self.enabled:
            return

        table = Table(
            title="DEV — Diagnostics",
            border_style="bright_black",
            show_header=False,
            padding=(0, 1),
        )
        table.add_column("Key", style="dim")
        table.add_column("Value")

        # --- System metrics ---
        ram_str, cpu_str = _system_metrics()
        table.add_row("RAM (RSS)", ram_str)
        table.add_row("CPU", cpu_str)
        table.add_row("", "")  # spacer

        # --- Game state ---
        table.add_row("Mode", ctx.world_mode)
        table.add_row("Seed", str(ctx.world_seed))
        table.add_row("Location", ctx.player.location_name)
        table.add_row("Food / Water", f"{ctx.player.food:.0f}% / {ctx.player.water:.0f}%")
        table.add_row("Hours", str(ctx.player.hours_elapsed))
        table.add_row("Inventory", str(ctx.player.total_items))
        table.add_row("", "")

        # --- World ---
        known = len(ctx.player.known_locations)
        total_locs = len(ctx.locations)
        table.add_row("Locations", f"{known} known / {total_locs} total")
        table.add_row("Drone Battery", f"{ctx.drone.battery:.0f}%")
        table.add_row("", "")

        # --- Creatures + trust ---
        for c in ctx.creatures:
            trust_color = "green" if c.trust >= 70 else "yellow" if c.trust >= 35 else "red"
            disp_tag = {"friendly": "[green]F[/green]", "neutral": "[yellow]N[/yellow]", "hostile": "[red]H[/red]"}
            tag = disp_tag.get(c.disposition, "?")
            helped = " *" if c.has_helped_repair else ""
            table.add_row(
                f"{c.name} {tag}",
                f"[{trust_color}]{c.trust}/100[/{trust_color}]{helped}",
            )
        table.add_row("", "")

        # --- Repair ---
        done = sum(1 for v in ctx.repair_checklist.values() if v)
        total = len(ctx.repair_checklist)
        table.add_row("Repair", f"{done}/{total}")

        # --- Tutorial ---
        if ctx.tutorial:
            table.add_row("Tutorial", ctx.tutorial.step.name)

        # --- LLM ---
        from src import llm

        table.add_row("LLM", "loaded" if llm._llm_available else "unavailable")

        ui.console.print(table)

        # --- Location details table ---
        loc_table = Table(
            title="DEV — Locations",
            border_style="bright_black",
            padding=(0, 1),
        )
        loc_table.add_column("#", style="dim", justify="right")
        loc_table.add_column("Name", style="cyan")
        loc_table.add_column("Type", style="dim")
        loc_table.add_column("Coords", style="dim")
        loc_table.add_column("Dist", justify="right")
        loc_table.add_column("Status")
        loc_table.add_column("Items", style="yellow")
        loc_table.add_column("Creature", style="green")

        cur = ctx.current_location()
        sorted_locs = sorted(ctx.locations, key=lambda loc: cur.distance_to(loc.x, loc.y))
        for i, loc in enumerate(sorted_locs, 1):
            d = cur.distance_to(loc.x, loc.y)
            dist_str = f"{d:.1f} km" if d > 0.01 else "HERE"

            if loc.visited:
                status = "[green]visited[/green]"
            elif loc.discovered:
                status = "[yellow]known[/yellow]"
            else:
                status = "[red]hidden[/red]"

            items_str = ", ".join(loc.items) if loc.items else "[dim]-[/dim]"
            creature = ctx.creature_at_location(loc.name)
            creature_str = f"{creature.name} ({creature.disposition[0].upper()})" if creature else "[dim]-[/dim]"

            # Add food/water source markers
            markers = []
            if loc.food_source:
                markers.append("F")
            if loc.water_source:
                markers.append("W")
            type_str = loc.loc_type.replace("_", " ")
            if markers:
                type_str += f" [green]{''.join(markers)}[/green]"

            loc_table.add_row(
                str(i), loc.name, type_str, f"({loc.x:.0f},{loc.y:.0f})",
                dist_str, status, items_str, creature_str,
            )

        ui.console.print(loc_table)

        # --- Scan reachability tree ---
        self._render_scan_tree(ctx)

        # --- Chat history ---
        self._render_chat_history(ctx)

    def _render_scan_tree(self, ctx):
        """Render a tree showing scan reachability from the current location."""
        cur = ctx.current_location()
        scanner_range = ctx.drone.scanner_range

        tree = Tree(f"[bold cyan]{cur.name}[/bold cyan] [dim](scan range: {scanner_range} km)[/dim]")

        # Find locations scannable from current position
        scannable = []
        for loc in ctx.locations:
            if loc.name == cur.name:
                continue
            d = cur.distance_to(loc.x, loc.y)
            if d <= scanner_range:
                scannable.append((loc, d))

        scannable.sort(key=lambda x: x[1])

        for loc, d in scannable:
            known = loc.name in ctx.player.known_locations
            if known:
                label = f"[green]{loc.name}[/green] [dim]({d:.1f} km · known)[/dim]"
            else:
                label = f"[yellow]{loc.name}[/yellow] [dim]({d:.1f} km · undiscovered)[/dim]"

            branch = tree.add(label)

            # Show what's scannable from THAT location (depth 2)
            for loc2 in ctx.locations:
                if loc2.name in (cur.name, loc.name):
                    continue
                d2 = math.sqrt((loc.x - loc2.x) ** 2 + (loc.y - loc2.y) ** 2)
                if d2 <= scanner_range:
                    k2 = loc2.name in ctx.player.known_locations
                    style = "green" if k2 else "red"
                    branch.add(f"[{style}]{loc2.name}[/{style}] [dim]({d2:.1f} km)[/dim]")

        if not scannable:
            tree.add("[dim]No locations in scan range[/dim]")

        ui.console.print(tree)

    def _render_chat_history(self, ctx):
        """Show conversation history for all creatures that have been spoken to."""
        creatures_with_history = [c for c in ctx.creatures if c.conversation_history]
        if not creatures_with_history:
            return

        from rich.panel import Panel

        ui.console.print()
        for creature in creatures_with_history:
            lines = []
            for msg in creature.conversation_history:
                role = msg["role"]
                content = msg["content"]
                if len(content) > 80:
                    content = content[:77] + "..."
                if role == "user":
                    lines.append(f"[bold]You>[/bold] {content}")
                else:
                    lines.append(f"[{creature.color}]{creature.name}>[/{creature.color}] {content}")

            trust_color = "green" if creature.trust >= 70 else "yellow" if creature.trust >= 35 else "red"
            title = (
                f"[{creature.color}]{creature.name}[/{creature.color}] "
                f"[dim]({creature.species} · {creature.archetype})[/dim] "
                f"[{trust_color}]Trust: {creature.trust}/100[/{trust_color}] "
                f"[dim]({len(creature.conversation_history)} msgs)[/dim]"
            )
            ui.console.print(Panel(
                "\n".join(lines),
                title=title,
                border_style="bright_black",
                padding=(0, 1),
            ))


def _system_metrics() -> tuple[str, str]:
    """Return (ram_str, cpu_str). Gracefully handles missing psutil."""
    try:
        import psutil

        proc = psutil.Process()
        ram_mb = proc.memory_info().rss / (1024 * 1024)
        cpu = proc.cpu_percent(interval=0.05)
        return f"{ram_mb:.1f} MB", f"{cpu:.1f}%"
    except ImportError:
        return "psutil not installed", "psutil not installed"
    except Exception as e:
        return f"error: {e}", f"error: {e}"
