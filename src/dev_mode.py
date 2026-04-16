"""Developer diagnostics overlay — session-only, not saved."""

from rich.table import Table

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
