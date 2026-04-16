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


# Slash commands available in the conversation (chat) prompt.
# These are the /‑prefixed game commands plus chat-specific shortcuts.
CHAT_SLASH_COMMANDS = [
    "/end",
    "/bye",
    "/quit",
    "/exit",
    "/help",
    "/?",
    "/history",
    # Game commands useful mid-conversation
    "/status",
    "/inventory",
    "/inv",
    "/i",
    "/look",
    "/l",
    "/scan",
    "/gps",
    "/map",
    "/travel",
    "/go",
    "/give",
    "/trade",
    "/escort",
    "/drone",
    "/ship",
    "/repair",
    "/rest",
    "/save",
    "/load",
    "/upgrade",
    "/clear",
    "/cls",
]

# Exit words that don't need a "/" prefix
CHAT_EXIT_WORDS = ["bye", "leave"]


class ChatCompleter(Completer):
    """Autocomplete for the conversation (chat) prompt.

    Completes:
    - Slash commands (/status, /give, /end, etc.)
    - Arguments for slash commands (/travel <location>, /give <item> to <creature>, /ship <bay>)
    - Bare exit words (bye, leave)
    """

    def __init__(self, ctx, creature):
        self.ctx = ctx
        self.creature = creature

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text:
            return

        # --- Bare exit words (no slash) ---
        words = text.split()
        if len(words) <= 1 and not text.startswith("/"):
            partial = words[0].lower() if words else ""
            for w in CHAT_EXIT_WORDS:
                if w.startswith(partial) and partial != w:
                    yield Completion(w, start_position=-len(partial))
            return

        # --- Everything below requires a "/" prefix ---
        if not text.startswith("/"):
            return

        # Strip the leading "/" for parsing
        inner = text[1:]
        inner_words = inner.split()
        word_count = len(inner_words)
        at_space = text.endswith(" ")
        if at_space:
            word_count += 1

        # First word: complete the slash command itself
        if word_count <= 1:
            prefix = ("/" + inner_words[0].lower()) if inner_words else "/"
            for cmd in CHAT_SLASH_COMMANDS:
                if cmd.startswith(prefix):
                    yield Completion(cmd, start_position=-len(prefix))
            return

        # Subsequent words: context-aware argument completion
        cmd = inner_words[0].lower()
        partial = "" if at_space else (inner_words[-1] if len(inner_words) > 1 else "")
        partial_lower = partial.lower()

        # /ship → bay sub-commands
        if cmd in ("ship", "repair"):
            bays = ["repair", "storage", "kitchen", "charging", "medical"]
            for bay in bays:
                if bay.startswith(partial_lower):
                    yield Completion(bay, start_position=-len(partial))

        # /travel, /go → known locations
        elif cmd in ("travel", "go"):
            for name in sorted(self.ctx.player.known_locations):
                if name.lower().startswith(partial_lower):
                    yield Completion(name, start_position=-len(partial))

        # /give → inventory items, then "to", then creature name
        elif cmd == "give":
            lower_words = [w.lower() for w in inner_words[1:]]
            if "to" in lower_words:
                # After "to" → creature name (current creature + followers at location)
                loc_name = self.ctx.player.location_name
                for c in self.ctx.creatures:
                    at_loc = c.location_name == loc_name and not c.following
                    following_here = c.following and c.location_name == loc_name
                    if (at_loc or following_here) and c.name.lower().startswith(partial_lower):
                        yield Completion(c.name, start_position=-len(partial))
            else:
                for item in sorted(self.ctx.player.inventory.keys()):
                    display = item.replace("_", " ").title()
                    if display.lower().startswith(partial_lower):
                        yield Completion(display, start_position=-len(partial))
                if "to".startswith(partial_lower) and partial_lower != "to":
                    yield Completion("to", start_position=-len(partial))

        # /upgrade → upgradeable items in inventory
        elif cmd == "upgrade":
            for upgrade_key in UPGRADE_EFFECTS:
                if self.ctx.player.has_item(upgrade_key):
                    display = upgrade_key.replace("_", " ").title()
                    if display.lower().startswith(partial_lower):
                        yield Completion(display, start_position=-len(partial))

        # /escort → "dismiss" sub-command
        elif cmd == "escort":
            if "dismiss".startswith(partial_lower):
                yield Completion("dismiss", start_position=-len(partial))

        # /load → save slot names
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
    }
)


def create_prompt_session(ctx) -> PromptSession:
    """Create a prompt_toolkit session with game-aware autocomplete."""
    return PromptSession(
        completer=GameCompleter(ctx),
        style=_PROMPT_STYLE,
        complete_while_typing=False,
    )


def create_chat_session(ctx, creature) -> PromptSession:
    """Create a prompt_toolkit session for the conversation (chat) prompt."""
    return PromptSession(
        completer=ChatCompleter(ctx, creature),
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


def get_chat_input(session: PromptSession) -> str | None:
    """Get user input during a conversation, with slash-command autocomplete."""
    try:
        prompt_text = [("class:chat-label", "You> ")]
        return session.prompt(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        return None
