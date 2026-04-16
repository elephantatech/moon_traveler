"""Cross-platform tab-autocomplete input using prompt_toolkit."""

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
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

        # talk / speak → creature at current location
        elif cmd in ("talk", "speak"):
            creature = self.ctx.creature_at_location(self.ctx.player.location_name)
            if creature and creature.name.lower().startswith(partial_lower):
                yield Completion(creature.name, start_position=-len(partial))

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
                # After "to" → creature name
                creature = self.ctx.creature_at_location(self.ctx.player.location_name)
                if creature and creature.name.lower().startswith(partial_lower):
                    yield Completion(creature.name, start_position=-len(partial))
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
    }
)


def create_prompt_session(ctx) -> PromptSession:
    """Create a prompt_toolkit session with game-aware autocomplete."""
    return PromptSession(
        completer=GameCompleter(ctx),
        style=_PROMPT_STYLE,
        complete_while_typing=False,
    )


def get_input(session: PromptSession, location_name: str) -> str | None:
    """Get user input with autocomplete. Returns stripped string or None on EOF/interrupt."""
    try:
        prompt_text = [
            ("class:location", location_name),
            ("class:prompt", " > "),
        ]
        return session.prompt(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        return None
