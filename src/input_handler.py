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
    "tutorial",
    "sound",
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

class GameSuggester:
    """Textual-compatible suggester that provides inline tab-completion.

    Textual's Suggester protocol: async get_suggestion(value) -> str | None
    Returns the full completed text (not just the suffix).
    """

    def __init__(self, ctx):
        self.ctx = ctx

    async def get_suggestion(self, value: str) -> str | None:
        """Return the best completion for the current input value."""
        try:
            return self._suggest(value)
        except Exception:
            return None

    def _suggest(self, text: str) -> str | None:
        if not text:
            return None

        words = text.split()
        word_count = len(words)
        at_space = text.endswith(" ")
        if at_space:
            word_count += 1

        # First word: command completion
        if word_count <= 1:
            prefix = words[0].lower() if words else ""
            for cmd in BASE_COMMANDS:
                if cmd.startswith(prefix) and cmd != prefix:
                    return cmd
            return None

        cmd = words[0].lower()
        partial = "" if at_space else (words[-1] if len(words) > 1 else "")
        partial_lower = partial.lower()
        before = text[:len(text) - len(partial)] if partial else text

        # ship → bay sub-commands
        if cmd in ("ship", "repair"):
            for bay in ["repair", "storage", "kitchen", "charging", "medical"]:
                if bay.startswith(partial_lower) and bay != partial_lower:
                    return before + bay

        # travel / go → known location names
        elif cmd in ("travel", "go"):
            for name in sorted(self.ctx.player.known_locations):
                if name.lower().startswith(partial_lower) and name.lower() != partial_lower:
                    return before + name

        # talk / speak → creature at current location
        elif cmd in ("talk", "speak"):
            loc_name = self.ctx.player.location_name
            for c in self.ctx.creatures:
                at_loc = c.location_name == loc_name and not c.following
                following = c.following and c.location_name == loc_name
                if (at_loc or following) and c.name.lower().startswith(partial_lower) and c.name.lower() != partial_lower:
                    return before + c.name

        # take / get / pick → items at location
        elif cmd in ("take", "get", "pick"):
            loc = self.ctx.current_location()
            for item in loc.items:
                display = item.replace("_", " ").title()
                if display.lower().startswith(partial_lower) and display.lower() != partial_lower:
                    return before + display

        # give → inventory items, then "to", then creature name
        elif cmd == "give":
            lower_words = [w.lower() for w in words[1:]]
            if "to" in lower_words:
                loc_name = self.ctx.player.location_name
                for c in self.ctx.creatures:
                    at_loc = c.location_name == loc_name and not c.following
                    following = c.following and c.location_name == loc_name
                    if (at_loc or following) and c.name.lower().startswith(partial_lower) and c.name.lower() != partial_lower:
                        return before + c.name
            else:
                for item in sorted(self.ctx.player.inventory.keys()):
                    display = item.replace("_", " ").title()
                    if display.lower().startswith(partial_lower) and display.lower() != partial_lower:
                        return before + display
                if "to".startswith(partial_lower) and partial_lower != "to":
                    return before + "to"

        # upgrade → upgrade items in inventory
        elif cmd == "upgrade":
            for key in UPGRADE_EFFECTS:
                if self.ctx.player.has_item(key):
                    display = key.replace("_", " ").title()
                    if display.lower().startswith(partial_lower) and display.lower() != partial_lower:
                        return before + display

        # load → save slot names
        elif cmd == "load":
            from src.save_load import list_saves
            for slot in list_saves():
                if slot.lower().startswith(partial_lower) and slot.lower() != partial_lower:
                    return before + slot

        return None
