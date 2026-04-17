"""Cross-platform tab-autocomplete input using prompt_toolkit and Textual."""

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

from src.drone import UPGRADE_EFFECTS

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
    "ship",
    "repair",
    "rest",
    "save",
    "load",
    "help",
    "config",
    "inspect",
    "examine",
    "tutorial",
    "sound",
    "charge",
    "screenshot",
    "clear",
    "cls",
    "quit",
    "exit",
    "dev",
    "devmode",
]


class GameCompleter(Completer):
    """Context-aware completer that updates from live game state."""

    def __init__(self, ctx):
        self.ctx = ctx

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()
        word_count = len(words)

        # If cursor is right after a space, we're completing the next word
        at_space = text.endswith(" ") if text else False
        if at_space:
            word_count += 1

        # First word: command completion
        if word_count <= 1:
            prefix = words[0].lower() if words else ""
            for cmd in BASE_COMMANDS:
                if cmd.startswith(prefix):
                    yield Completion(cmd, start_position=-len(prefix))
            return

        cmd = words[0].lower()
        partial = "" if at_space else (words[-1] if len(words) > 1 else "")
        partial_lower = partial.lower()

        # ship → bay sub-commands
        if cmd in ("ship", "repair"):
            bays = ["repair", "storage", "kitchen", "charging", "medical"]
            for bay in bays:
                if bay.startswith(partial_lower):
                    yield Completion(bay, start_position=-len(partial))

        # travel / go → known location names
        elif cmd in ("travel", "go"):
            for name in sorted(self.ctx.player.known_locations):
                if name.lower().startswith(partial_lower):
                    yield Completion(name, start_position=-len(partial))

        # talk / speak → creature at current location (residents + followers)
        elif cmd in ("talk", "speak"):
            loc_name = self.ctx.player.location_name
            seen = set()
            for c in self.ctx.creatures:
                at_loc = c.location_name == loc_name and not c.following
                following_here = c.following and c.location_name == loc_name
                if (at_loc or following_here) and c.name not in seen:
                    if c.name.lower().startswith(partial_lower):
                        yield Completion(c.name, start_position=-len(partial))
                    seen.add(c.name)

        # take / get / pick → items at current location
        elif cmd in ("take", "get", "pick"):
            loc = self.ctx.current_location()
            for item in loc.items:
                display = item.replace("_", " ").title()
                if display.lower().startswith(partial_lower) or item.lower().startswith(partial_lower):
                    yield Completion(display, start_position=-len(partial))

        # give → inventory items, then "to", then creature name
        elif cmd == "give":
            # Determine phase: before "to", the word "to", or after "to"
            lower_words = [w.lower() for w in words[1:]]
            if "to" in lower_words:
                # After "to" → creature name (residents + followers)
                loc_name = self.ctx.player.location_name
                for c in self.ctx.creatures:
                    at_loc = c.location_name == loc_name and not c.following
                    following_here = c.following and c.location_name == loc_name
                    if (at_loc or following_here) and c.name.lower().startswith(partial_lower):
                        yield Completion(c.name, start_position=-len(partial))
            else:
                # Before "to" → inventory items, then "to"
                for item in sorted(self.ctx.player.inventory.keys()):
                    display = item.replace("_", " ").title()
                    if display.lower().startswith(partial_lower):
                        yield Completion(display, start_position=-len(partial))
                if "to".startswith(partial_lower) and partial_lower != "to":
                    yield Completion("to", start_position=-len(partial))

        # inspect / examine → inventory items
        elif cmd in ("inspect", "examine"):
            for item in sorted(self.ctx.player.inventory.keys()):
                display = item.replace("_", " ").title()
                if display.lower().startswith(partial_lower):
                    yield Completion(display, start_position=-len(partial))

        # upgrade → upgrade items in inventory
        elif cmd == "upgrade":
            for upgrade_key in UPGRADE_EFFECTS:
                if self.ctx.player.has_item(upgrade_key):
                    display = upgrade_key.replace("_", " ").title()
                    if display.lower().startswith(partial_lower):
                        yield Completion(display, start_position=-len(partial))

        # load → save slot names
        elif cmd == "load":
            from src.save_load import list_saves

            for slot in list_saves():
                if slot.lower().startswith(partial_lower):
                    yield Completion(slot, start_position=-len(partial))


_PROMPT_STYLE = Style.from_dict(
    {
        "location": "bold ansicyan",
        "prompt": "bold",
        "chat-label": "bold",
        "bottom-toolbar": "bg:#1a1d2e #8890b0",
        "bottom-toolbar.text": "bg:#1a1d2e #b4bcd4",
    }
)


def _bottom_toolbar():
    """Return the fixed status bar for the bottom of the terminal."""
    from src import ui

    text = ui.get_toolbar_text()
    return HTML(text) if text else ""


def create_prompt_session(ctx) -> PromptSession:
    """Create a prompt_toolkit session with game-aware autocomplete and fixed status bar."""
    return PromptSession(
        completer=GameCompleter(ctx),
        style=_PROMPT_STYLE,
        complete_while_typing=False,
        bottom_toolbar=_bottom_toolbar,
    )


def get_input(session: PromptSession, location_name: str) -> str | None:
    """Get user input with autocomplete and fixed status bar. Returns stripped string or None."""
    try:
        prompt_text = [
            ("class:location", location_name),
            ("class:prompt", " > "),
        ]
        return session.prompt(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        return None


# ---------------------------------------------------------------------------
# Textual Suggester — reuses GameCompleter logic for inline suggestions
# ---------------------------------------------------------------------------

try:
    from textual.suggester import Suggester as _TextualSuggester
except ImportError:
    _TextualSuggester = object  # Fallback if textual not installed


class GameSuggester(_TextualSuggester):
    """Textual Suggester that provides inline tab-completion.

    Extends Textual's Suggester base class so _get_suggestion works.
    Returns the full completed text (not just the suffix).
    """

    def __init__(self, ctx):
        if _TextualSuggester is not object:
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

        # upgrade → upgrade items in inventory
        if cmd == "upgrade":
            results = []
            for key in UPGRADE_EFFECTS:
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
