"""Developer diagnostics — logs game state to a JSON log file."""

import json
import math
import os
import time

from src import ui
from src.config import get_data_dir

# Log location: ~/.moonwalker/dev/
DEV_LOG_DIR = get_data_dir() / "dev"
DEV_LOG_FILE = DEV_LOG_DIR / "dev_diagnostics.jsonl"


class DevMode:
    """Toggle-able diagnostics logger. Writes JSON lines to a log file."""

    def __init__(self):
        self.enabled = False
        self.log_path = DEV_LOG_FILE
        self._llm_calls: list[dict] = []  # Last N inference calls

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            DEV_LOG_DIR.mkdir(parents=True, exist_ok=True)
            ui.success(f"Dev mode ON — logging to {self.log_path}")
        else:
            ui.info("Dev mode OFF — logging stopped.")

    def log_llm_call(
        self,
        call_type: str,
        elapsed_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        rss_delta_mb: float,
    ):
        """Record an LLM inference call for the performance panel."""
        if not self.enabled:
            return
        entry = {
            "type": call_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "elapsed_ms": round(elapsed_ms),
            "rss_delta_mb": round(rss_delta_mb, 1),
        }
        self._llm_calls.append(entry)
        if len(self._llm_calls) > 5:
            self._llm_calls = self._llm_calls[-5:]
        # Also write to JSONL log
        self.debug("llm_call", **entry)

    def debug(self, event: str, **data):
        """Write a debug log entry. No-op when dev mode is off. Never crashes the game."""
        if not self.enabled:
            return
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{time.time() % 1:.3f}"[2:],
            "level": "DEBUG",
            "event": event,
            **data,
        }
        try:
            DEV_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass  # Never crash the game due to logging failure

    def render_panel(self, ctx):
        """Log diagnostics to JSON file. Never crashes the game."""
        if not self.enabled:
            return

        try:
            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "event": "diagnostics",
                "system": _system_metrics_dict(),
                "game": _game_state_dict(ctx),
                "locations": _locations_dict(ctx),
                "creatures": _creatures_dict(ctx),
                "scan_tree": _scan_tree_dict(ctx),
                "chat_history": _chat_history_dict(ctx),
            }

            DEV_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass  # Never crash the game due to logging failure

    def _render_scan_tree(self, ctx):
        """No-op: scan tree is now included in the JSON log."""

    def _render_chat_history(self, ctx):
        """No-op: chat history is now included in the JSON log."""


def _system_metrics_dict() -> dict:
    """Return system metrics as a plain dict for JSON logging."""
    result = {
        "ram_rss_mb": None,
        "ram_vms_mb": None,
        "system_ram_total_gb": None,
        "system_ram_used_gb": None,
        "system_ram_percent": None,
        "cpu_percent": None,
        "model_ram_estimate_mb": None,
        "model_file_size_mb": None,
        "model_loaded": False,
    }
    try:
        import psutil

        proc = psutil.Process()
        mem = proc.memory_info()
        result["ram_rss_mb"] = round(mem.rss / (1024 * 1024), 1)
        result["ram_vms_mb"] = round(mem.vms / (1024 * 1024), 1)

        sys_mem = psutil.virtual_memory()
        result["system_ram_total_gb"] = round(sys_mem.total / (1024**3), 1)
        result["system_ram_used_gb"] = round(sys_mem.used / (1024**3), 1)
        result["system_ram_percent"] = sys_mem.percent

        result["cpu_percent"] = round(proc.cpu_percent(interval=0.05), 1)
    except (ImportError, Exception):
        pass

    try:
        from src import llm

        if llm._llm_available and llm._llm_model is not None:
            result["model_loaded"] = True
            model_path = getattr(llm._llm_model, "model_path", None)
            if model_path:
                try:
                    size_mb = os.path.getsize(model_path) / (1024 * 1024)
                    result["model_file_size_mb"] = round(size_mb, 0)
                    result["model_ram_estimate_mb"] = round(size_mb * 1.3, 0)
                except OSError:
                    pass
    except Exception:
        pass

    return result


def _game_state_dict(ctx) -> dict:
    """Return core game state as a dict."""
    done = sum(1 for v in ctx.repair_checklist.values() if v)
    total = len(ctx.repair_checklist)

    from src import llm

    return {
        "mode": ctx.world_mode,
        "seed": ctx.world_seed,
        "location": ctx.player.location_name,
        "food": round(ctx.player.food, 1),
        "water": round(ctx.player.water, 1),
        "suit_integrity": round(ctx.player.suit_integrity, 1),
        "hours_elapsed": ctx.player.hours_elapsed,
        "inventory_count": ctx.player.total_items,
        "inventory_capacity": ctx.drone.cargo_capacity,
        "drone_battery": round(ctx.drone.battery, 1),
        "locations_known": len(ctx.player.known_locations),
        "locations_total": len(ctx.locations),
        "repair_done": done,
        "repair_total": total,
        "repair_checklist": {k: v for k, v in ctx.repair_checklist.items()},
        "tutorial_step": ctx.tutorial.step.name if ctx.tutorial else "N/A",
        "llm_available": llm._llm_available,
    }


def _locations_dict(ctx) -> list[dict]:
    """Return all locations as a list of dicts."""
    cur = ctx.current_location()
    result = []
    sorted_locs = sorted(ctx.locations, key=lambda loc: cur.distance_to(loc.x, loc.y))
    for loc in sorted_locs:
        d = cur.distance_to(loc.x, loc.y)
        creature = ctx.creature_at_location(loc.name)
        result.append(
            {
                "name": loc.name,
                "type": loc.loc_type,
                "x": loc.x,
                "y": loc.y,
                "distance_km": round(d, 1),
                "discovered": loc.discovered,
                "visited": loc.visited,
                "items": list(loc.items),
                "food_source": loc.food_source,
                "water_source": loc.water_source,
                "creature": creature.name if creature else None,
            }
        )
    return result


def _creatures_dict(ctx) -> list[dict]:
    """Return all creatures as a list of dicts."""
    result = []
    for c in ctx.creatures:
        result.append(
            {
                "name": c.name,
                "species": c.species,
                "archetype": c.archetype,
                "disposition": c.disposition,
                "location": c.location_name,
                "trust": c.trust,
                "trust_level": c.trust_level,
                "following": c.following,
                "has_helped_repair": c.has_helped_repair,
                "role_inventory": list(c.role_inventory),
                "given_items": list(c.given_items),
                "can_give_materials": list(c.can_give_materials),
                "trade_wants": list(c.trade_wants),
                "knows_food_source": c.knows_food_source,
                "knows_water_source": c.knows_water_source,
                "conversation_count": len(c.conversation_history),
            }
        )
    return result


def _scan_tree_dict(ctx) -> dict:
    """Return scan reachability from current location."""
    cur = ctx.current_location()
    scanner_range = ctx.drone.scanner_range
    scannable = []
    for loc in ctx.locations:
        if loc.name == cur.name:
            continue
        d = cur.distance_to(loc.x, loc.y)
        if d <= scanner_range:
            # Depth-2: what's scannable from that location
            reachable_from = []
            for loc2 in ctx.locations:
                if loc2.name in (cur.name, loc.name):
                    continue
                d2 = math.sqrt((loc.x - loc2.x) ** 2 + (loc.y - loc2.y) ** 2)
                if d2 <= scanner_range:
                    reachable_from.append(
                        {
                            "name": loc2.name,
                            "distance_km": round(d2, 1),
                            "known": loc2.name in ctx.player.known_locations,
                        }
                    )
            scannable.append(
                {
                    "name": loc.name,
                    "distance_km": round(d, 1),
                    "known": loc.name in ctx.player.known_locations,
                    "reachable_from": reachable_from,
                }
            )
    return {
        "current": cur.name,
        "scanner_range_km": scanner_range,
        "scannable": scannable,
    }


def _chat_history_dict(ctx) -> list[dict]:
    """Return conversation history for creatures that have been spoken to."""
    result = []
    for c in ctx.creatures:
        if not c.conversation_history:
            continue
        messages = []
        for msg in c.conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        result.append(
            {
                "creature": c.name,
                "trust": c.trust,
                "message_count": len(c.conversation_history),
                "messages": messages,
            }
        )
    return result
