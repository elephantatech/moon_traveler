"""Tab-autocomplete input for Textual TUI mode."""

from textual.suggester import Suggester as _TextualSuggester

# Base commands (always available)
BASE_COMMANDS = [
    "look",
    "l",
    "scan",
    "gps",
    "map",
    "travel",
    "go",
    "take",
    "get",
    "pick",
    "inventory",
    "inv",
    "i",
    "talk",
    "speak",
    "give",
    "trade",
    "escort",
    "drone",
    "upgrade",
    "status",
    "stats",
    "scores",
    "leaderboard",
    "ship",
    "repair",
    "rest",
    "save",
    "load",
    "help",
    "name",
    "config",
    "inspect",
    "examine",
    "tutorial",
    "sound",
    "charge",
    "screenshot",
    "model",
    "update",
    "clear",
    "cls",
    "dev",
    "devmode",
    "quit",
    "exit",
]


class GameSuggester(_TextualSuggester):
    """Textual Suggester that provides inline tab-completion.

    Extends Textual's Suggester base class so _get_suggestion works.
    Returns the full completed text (not just the suffix).
    """

    def __init__(self, ctx):
        super().__init__(use_cache=False)
        self.ctx = ctx

    async def get_suggestion(self, value: str) -> str | None:
        """Return the best completion for the current input value."""
        try:
            return self._suggest(value)
        except Exception:
            return None

    def _suggest(self, text: str) -> str | None:
        """Return the first matching suggestion."""
        results = self._get_all_suggestions(text)
        return results[0] if results else None

    def _get_all_suggestions(self, text: str) -> list[str]:
        """Return ALL matching suggestions for Tab cycling."""
        if not text:
            return []

        words = text.split()
        word_count = len(words)
        at_space = text.endswith(" ")
        if at_space:
            word_count += 1

        # First word: command completion
        if word_count <= 1:
            prefix = words[0].lower() if words else ""
            return [cmd for cmd in BASE_COMMANDS if cmd.startswith(prefix) and cmd != prefix]

        cmd = words[0].lower()
        # For multi-word args (like location names), use everything after the command
        arg_text = text[len(words[0]) :].lstrip()
        arg_lower = arg_text.lower()
        cmd_prefix = words[0] + " "

        # ship → bay sub-commands
        if cmd in ("ship", "repair"):
            return [
                cmd_prefix + bay
                for bay in ["repair", "storage", "kitchen", "charging", "medical"]
                if bay.startswith(arg_lower) and bay != arg_lower
            ]

        # drone → sub-commands (status, upgrade, charge)
        if cmd == "drone":
            subs = ["status", "upgrade", "charge"]
            if not arg_lower or not any(s.startswith(arg_lower) for s in subs):
                # After "drone upgrade " → complete upgrade names
                if arg_text.lower().startswith("upgrade "):
                    upgrade_arg = arg_text[8:].lower()
                    from src.drone import UPGRADE_EFFECTS

                    return [
                        cmd_prefix + "upgrade " + key.replace("_", " ").title()
                        for key in UPGRADE_EFFECTS
                        if self.ctx.player.has_item(key)
                        and key.replace("_", " ").title().lower().startswith(upgrade_arg)
                        and key.replace("_", " ").title().lower() != upgrade_arg
                    ]
            return [cmd_prefix + s for s in subs if s.startswith(arg_lower) and s != arg_lower]

        # travel / go → known location names (multi-word like "Lunar Lake")
        if cmd in ("travel", "go"):
            return [
                cmd_prefix + name
                for name in sorted(self.ctx.player.known_locations)
                if name.lower().startswith(arg_lower) and name.lower() != arg_lower
            ]

        # talk / speak → creature at current location
        if cmd in ("talk", "speak"):
            loc_name = self.ctx.player.location_name
            results = []
            for c in self.ctx.creatures:
                at_loc = c.location_name == loc_name and not c.following
                following = c.following and c.location_name == loc_name
                if (at_loc or following) and c.name.lower().startswith(arg_lower) and c.name.lower() != arg_lower:
                    results.append(cmd_prefix + c.name)
            return results

        # take / get / pick → items at location
        if cmd in ("take", "get", "pick"):
            loc = self.ctx.current_location()
            results = []
            for item in loc.items:
                display = item.replace("_", " ").title()
                if display.lower().startswith(arg_lower) and display.lower() != arg_lower:
                    results.append(cmd_prefix + display)
            return results

        # give → inventory items, then "to", then creature name
        if cmd == "give":
            lower_words = [w.lower() for w in words[1:]]
            if "to" in lower_words:
                # After "to" — complete creature name
                to_idx = lower_words.index("to")
                after_to = " ".join(words[2 + to_idx :])
                after_lower = after_to.lower()
                prefix_before = " ".join(words[: 2 + to_idx]) + " "
                loc_name = self.ctx.player.location_name
                results = []
                for c in self.ctx.creatures:
                    at_loc = c.location_name == loc_name and not c.following
                    following = c.following and c.location_name == loc_name
                    name_lower = c.name.lower()
                    if (at_loc or following) and name_lower.startswith(after_lower) and name_lower != after_lower:
                        results.append(prefix_before + c.name)
                return results
            else:
                results = []
                for item in sorted(self.ctx.player.inventory.keys()):
                    display = item.replace("_", " ").title()
                    if display.lower().startswith(arg_lower) and display.lower() != arg_lower:
                        results.append(cmd_prefix + display)
                if "to".startswith(arg_lower) and arg_lower != "to":
                    results.append(cmd_prefix + "to")
                return results

        # inspect / examine → inventory items
        if cmd in ("inspect", "examine"):
            return [
                cmd_prefix + item.replace("_", " ").title()
                for item in sorted(self.ctx.player.inventory.keys())
                if item.replace("_", " ").title().lower().startswith(arg_lower)
                and item.replace("_", " ").title().lower() != arg_lower
            ]

        # upgrade → upgrade items in inventory (top-level alias for drone upgrade)
        if cmd == "upgrade":
            from src.drone import UPGRADE_EFFECTS as _UE

            results = []
            for key in _UE:
                if self.ctx.player.has_item(key):
                    display = key.replace("_", " ").title()
                    if display.lower().startswith(arg_lower) and display.lower() != arg_lower:
                        results.append(cmd_prefix + display)
            return results

        # load → save slot names
        if cmd == "load":
            from src.save_load import list_saves

            return [
                cmd_prefix + slot
                for slot in list_saves()
                if slot.lower().startswith(arg_lower) and slot.lower() != arg_lower
            ]

        return []
