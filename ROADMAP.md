# Moon Traveler Terminal — Product Roadmap

**Last updated:** 2026-04-16
**Current version:** v0.4.0-dev (unreleased)
**Stable release:** v0.3.2

This roadmap covers planned development from the current dev build through v1.0.0 (full release). Each feature entry includes a description, technical approach grounded in the existing architecture, effort estimate, dependencies, and affected files.

Effort scale: **S** (< 1 day), **M** (1–3 days), **L** (3–7 days), **XL** (1–3 weeks).

---

## Table of Contents

1. [v0.4.0 — Textual TUI & Game Polish](#v040--textual-tui--game-polish)
2. [v0.5.0 — Accessibility & Diagnostics](#v050--accessibility--diagnostics)
3. [v0.6.0 — World & Gameplay Expansion](#v060--world--gameplay-expansion)
4. [v0.7.0 — Multiplayer & Community](#v070--multiplayer--community)
5. [v1.0.0 — Full Release](#v100--full-release)
6. [Technical Debt](#technical-debt)
7. [Infrastructure](#infrastructure)

---

## v0.4.0 — Textual TUI & Game Polish

**Release target:** Next tag push after final QA pass.

This release delivers a fully interactive Textual-based TUI alongside the existing CLI (`play.py`), plus difficulty modes, drone improvements, and audio.

### What is built and ready

**Textual TUI (`play_tui.py` + `src/tui_app.py` + `src/tui_bridge.py`)**
- `MoonTravelerApp` runs the full game in a worker thread via `run_worker(thread=True)`
- `UIBridge` provides thread-safe `write()`, `print()`, `input()`, and `ask()` paths between the worker and Textual's async event loop
- `_BridgeConsoleShim` in `src/ui.py` intercepts all `console.print()` and `console.input()` calls so the entire game routes through Textual without changes to game logic
- Tab-cycling autocomplete via `GameSuggester` (Textual Suggester subclass) sharing logic with `GameCompleter` (prompt_toolkit)
- Up/down arrow command history (in-session, not persisted)
- F12 screenshot export to `assets/screenshot-TIMESTAMP.svg`
- Header bar, scrollable `RichLog` output pane, fixed status bar, and prompt label+input field layout defined in `src/game.tcss`
- Ctrl+C unblocks both the command queue and ask queue cleanly on exit

**4 Difficulty Modes (`src/difficulty.py`)**
- Easy, Medium, Hard (long alias), Brutal
- Per-mode scaling: trust gain per chat (2–5), gift trust bonus (5–20), item find chance (8–30%), food/water/suit drain multipliers (Brutal: 1.5×), additional hazard probability bonus (Brutal: +5%)
- Junk items easter egg: stash 5 unique junk items in ship storage (7 in Brutal) to activate a 2× trust multiplier for the rest of the game

**8 Drone Upgrades including Charge Module**
- `charge_module` enables auto-charge: drone battery recovers during travel, toggled with `charge` command
- `auto_charge_enabled` persisted in `drone.to_dict()` / `from_dict()`

**Sound System (`src/sound.py`)**
- 22 named game events with per-platform beep patterns, Windows `.wav` files, Linux freedesktop sounds
- Voice mode (macOS `say`, Samantha voice) activated by `voice_module` drone upgrade
- Non-blocking async playback via `threading.Lock` with skip-if-busy policy
- Beep path uses `os.write(2, b"\a")` to bypass Textual's stderr capture in TUI mode

**Inspect Command**
- `inspect <item>` / `examine <item>` shows descriptions from `ITEM_DESCRIPTIONS` in `src/difficulty.py`
- Covers all 8 repair materials, 8 drone upgrades, and 10 junk items
- Autocomplete wired in both `GameCompleter` and `GameSuggester`

**NPC Memory System** (shipped in v0.3.2)
- Structured markdown memory per creature, updated by LLM after each conversation
- Template fallback when LLM unavailable
- Stored in `creature_memory` SQLite table, injected into system prompt
- Capped at 20 bullet points managed by LLM

**231 automated tests** across 14 test files.

### Remaining v0.4.0 tasks

- [ ] Final QA pass of TUI on macOS, Linux, and Windows
- [ ] Verify `play_tui.py` entry point is included in PyInstaller build in `scripts/build_release.py`
- [ ] Add `textual` to `requirements.txt` and `pyproject.toml`
- [ ] Update `spec.md` version header to 0.4.0
- [ ] Update `README.md` with TUI launch instructions (`python play_tui.py`)
- [ ] Tag v0.4.0 to trigger release workflow

---

## v0.5.0 — Accessibility & Diagnostics

**Release target:** 4–6 weeks after v0.4.0

---

### Screen Reader Mode

**Description:** A mode that strips all Rich/Textual markup from output and produces plain text compatible with VoiceOver (macOS), NVDA (Windows), and any terminal screen reader. Panels degrade to plain section headers, tables degrade to tab-separated text, colors are removed.

**Technical approach:**
- Add `screen_reader_enabled: bool` to `src/config.py` (persisted in `~/.moonwalker/config.json`)
- Add `config screenreader on|off` subcommand to `cmd_config()` in `src/commands.py`
- Add `strip_markup(text: str) -> str` in `src/ui.py` using `rich.markup.strip()` to remove `[bold cyan]...[/bold cyan]` tags
- Gate all `console.print()` calls: when enabled, strip markup before handing to `_real_console`
- In the TUI path (`_BridgeConsoleShim`), render through `Console(no_color=True, highlight=False)` before writing to `RichLog`
- `rich.panel.Panel` degrades to `"--- {TITLE} ---\n{content}\n---"` via a wrapper `sr_panel(title, content)` in `src/ui.py`
- Tables degrade to header row + data rows joined with `\t`, one row per line
- ARIA and Drone markup prefixes render as plain `ARIA:` and `DRONE:`

**Estimated effort:** M

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `screen_reader_enabled` setting
- `/Users/elephantatech/projects/moon_traveler/src/ui.py` — `strip_markup()`, `sr_panel()`, gated render paths
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `config screenreader` subcommand
- `/Users/elephantatech/projects/moon_traveler/tests/test_ui.py` (new)

---

### Text-to-Speech Output Mode

**Description:** All game text is spoken aloud as it appears — narration, ARIA messages, creature dialogue, drone whispers. Builds on the existing voice module architecture. Platform-native TTS: `say` on macOS, `espeak`/`espeak-ng` on Linux, `pyttsx3` or SAPI on Windows.

**Technical approach:**
- Add `tts_enabled: bool` to `src/config.py`; add `config tts on|off` command
- Add `speak_text(text: str)` to `src/sound.py` distinct from the event-based `play(event)`:
  - macOS: `subprocess.run(["say", "-v", "Samantha", "-r", "200", text], timeout=30)`
  - Linux: detect `espeak`/`espeak-ng` via the existing `_find_linux_player()` pattern
  - Windows: use `pyttsx3` (optional dependency) or fall back to `winsound.MessageBeep`
- Add `tts_speak(text: str)` in `src/ui.py` that strips markup then calls `sound.speak_text()` via the existing `_play_async()` threading path
- Hook `tts_speak()` into `narrate_lines()`, `creature_speak()`, ARIA warning output, and drone `speak()` / `whisper()`
- Speech queue capped at depth 5: fast-scrolling text does not create a backlog. Uses `queue.Queue(maxsize=5)` with `put_nowait()` dropping overflow silently
- Creature dialogue TTS strips translation garbling words — the garble is visual-only; a `clean_for_tts(text)` pass replaces `zrrk`, `vvmm`, `kktch`, `bzzl` patterns with `...`

**Estimated effort:** L

**Dependencies:** Screen reader mode (shares markup-stripping infrastructure)

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/sound.py` — `speak_text()`, platform-specific TTS functions
- `/Users/elephantatech/projects/moon_traveler/src/ui.py` — `tts_speak()`, hooks in `narrate_lines()`, `creature_speak()`
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `tts_enabled` setting
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `config tts` subcommand
- `/Users/elephantatech/projects/moon_traveler/requirements.txt` — `pyttsx3` as optional (Windows)

---

### Voice Input via Whisper.cpp

**Description:** Press Space (or a configurable hotkey) to record speech. The recording is transcribed locally by Whisper.cpp (via subprocess call to a locally installed binary) and injected as a typed command. Fully offline — no cloud API. TUI mode only initially.

**Technical approach:**
- In `src/tui_app.py`, intercept Space key when the input field is focused and the input value is empty: toggle recording state
- Visual indicator in status bar: `[REC]` while capturing audio, `[TRANSCRIBING...]` while the subprocess runs
- Recording: use `sounddevice` (new optional dependency) to capture microphone audio to a temp `.wav` file at 16kHz mono, 16-bit PCM — the format Whisper.cpp expects. Record while Space is held or until a second Space press (toggle mode)
- Transcription: `subprocess.run([whisper_path, "--model", model_path, "--output-txt", "--no-timestamps", wav_path], capture_output=True, timeout=30)` — parse the `.txt` output file for the transcript line
- On transcription complete: set `self._game_input.value = transcript` and optionally call `on_input_submitted` to auto-execute
- Add `src/whisper_input.py` (new): `record_audio(seconds) -> Path`, `transcribe(wav_path, whisper_path, model_path) -> str | None`, temp file cleanup
- `whisper_path` and `whisper_model_path` configurable via `config whisperpath /path/to/whisper-main` and `config whispermodel /path/to/ggml-base.bin`
- Feature silently unavailable if `sounddevice` not installed or whisper binary not found — one-time hint on `config voiceinput on`

**Estimated effort:** XL

**Dependencies:** v0.4.0 TUI mode stable. User-provided Whisper.cpp binary.

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/tui_app.py` — Space key handler, recording toggle, visual indicator
- `/Users/elephantatech/projects/moon_traveler/src/whisper_input.py` (new) — recording, transcription, temp file management
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `voice_input_enabled`, `whisper_path`, `whisper_model_path`
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `config voiceinput`, `config whisperpath`, `config whispermodel` subcommands
- `/Users/elephantatech/projects/moon_traveler/requirements.txt` — `sounddevice` as optional

---

### Session Stats Tracker

**Description:** Tracks per-session gameplay statistics silently throughout play: commands typed, kilometers traveled, unique creatures spoken to, hazards survived, trades completed, gifts given, repair materials collected, and wall-clock time played.

**Technical approach:**
- Add `src/stats.py` (new) with `SessionStats` dataclass: integer/float fields per metric plus `session_start: float` (set to `time.time()` on instantiation)
- `SessionStats` instantiated in `game.main()` and attached to `GameContext` as `ctx.stats`
- Increment hooks:
  - `ctx.stats.commands += 1` in the main `dispatch()` loop in `src/commands.py`
  - `ctx.stats.km_traveled += distance` in `execute_travel()` in `src/travel.py`
  - `ctx.stats.creatures_talked.add(creature.id)` (unique set) in `cmd_talk()`
  - `ctx.stats.hazards_survived += 1` in hazard resolution in `src/travel.py`
  - `ctx.stats.trades += 1` in `cmd_trade()` and the TRADE action handler in `src/llm.py`
  - `ctx.stats.gifts_given += 1` in `cmd_give()`
- `SessionStats.elapsed_seconds` property: `time.time() - session_start`
- Stats are session-only by default (not persisted to save file). A `stats show` command displays current session stats as a Rich panel.

**Estimated effort:** S

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/stats.py` (new)
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `GameContext` gets `stats` field; increment hooks per handler
- `/Users/elephantatech/projects/moon_traveler/src/travel.py` — km and hazard hooks
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — instantiate `SessionStats`, pass to `GameContext`
- `/Users/elephantatech/projects/moon_traveler/tests/test_stats.py` (new)

---

### Post-Game Stats Screen

**Description:** On win or lose, display a full summary screen: real time survived (wall-clock hours:minutes), in-game hours, commands typed, km traveled, creatures befriended (trust > 50), hazards survived, trades completed, a numerical score, a letter grade (S through D), and an ARIA verdict line per grade.

**Technical approach:**
- Add `calculate_score(stats: SessionStats, ctx: GameContext) -> int` in `src/stats.py`:
  - Base: 100 points per in-game hour survived
  - Bonus: 50 per creature with trust > 50, 100 per repair material installed
  - Deduction: 20 per hazard damage taken, 50 per death resource hitting 0 (if game continues past it — applicable to Brutal future variants)
  - Score normalized to 0–1000
- Score brackets: S ≥ 900, A ≥ 750, B ≥ 600, C ≥ 450, D < 450
- Add `render_stats_screen(stats: SessionStats, ctx: GameContext)` in `src/ui.py` using `rich.table.Table` for column layout consistent with `show_status()`
- Extend `show_win_sequence()` and `show_lose_sequence()` in `src/game.py` to call `render_stats_screen()` after the narrative sequence
- ARIA verdict lines per grade (pre-written, 3 options each) added to `src/data/prompts.py`

**Estimated effort:** M

**Dependencies:** Session stats tracker

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/stats.py` — `calculate_score()`
- `/Users/elephantatech/projects/moon_traveler/src/ui.py` — `render_stats_screen()`
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — wire stats into win/lose sequences
- `/Users/elephantatech/projects/moon_traveler/src/data/prompts.py` — ARIA grade verdict lines (15 total)
- `/Users/elephantatech/projects/moon_traveler/tests/test_stats.py` — scoring formula coverage

---

### Performance Diagnostics in Dev Mode

**Description:** When dev mode is active, each LLM inference call is timed and the results (milliseconds, prompt tokens, completion tokens, RSS memory delta) are logged to the dev diagnostics JSONL file and displayed in the dev panel as a compact last-5-calls table.

**Technical approach:**
- In `src/llm.py`, wrap all `_llm_model.create_chat_completion()` and `_llm_model()` calls with `time.perf_counter()` before/after. Capture `response["usage"]["prompt_tokens"]` and `response["usage"]["completion_tokens"]` from the llama-cpp-python response (these are already in the response dict)
- Capture `psutil.Process().memory_info().rss` before and after each call; compute delta in MB
- Add `log_llm_call(event_type: str, ms: float, prompt_tokens: int, completion_tokens: int, rss_delta_mb: float)` to `DevMode` in `src/dev_mode.py`; writes a new `{"event": "llm_call", ...}` entry to the JSONL stream
- Add a "LLM Performance" subsection to the dev panel showing the last 5 calls as a Rich table: type | prompt_tok | completion_tok | ms | RSS delta

**Estimated effort:** S

**Dependencies:** Dev mode already exists in `src/dev_mode.py`

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/llm.py` — timing wrappers, usage capture
- `/Users/elephantatech/projects/moon_traveler/src/dev_mode.py` — `log_llm_call()`, panel rendering
- `/Users/elephantatech/projects/moon_traveler/tests/test_dev_mode.py` — test LLM events are logged

---

## v0.6.0 — World & Gameplay Expansion

**Release target:** 8–12 weeks after v0.5.0

---

### ASCII Minimap in GPS View

**Description:** The `gps` / `map` command shows a visual dot-map above the distance table. Player position is marked `@`, discovered-unvisited locations with `.`, visited locations with their type initial, crash site with `X`.

**Technical approach:**
- Add `render_minimap(locations: list[Location], player_x: float, player_y: float) -> Text` in `src/ui.py`
- Map dimensions: 40 cols × 20 rows. World coordinates normalized to grid space: `grid_x = int((loc.x - min_x) / world_width * MAP_COLS)`. Build a `list[list[str]]` grid initialized to spaces; place markers by coordinate
- Use Rich `Text` with per-character styling: crash site = yellow, player `@` = bright_cyan, unvisited = dim white, visited = type-specific color matching `loc_type` to a fixed palette
- In TUI mode, player marker `@` can blink via `time.time() % 1.0 > 0.5` toggle on each render — this is a nice-to-have, not required
- In screen reader mode (v0.5.0), the minimap is omitted entirely

**Estimated effort:** M

**Dependencies:** None — all required data (Location.x/y, discovered, visited, loc_type) is already on the Location dataclass

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/ui.py` — `render_minimap()`, update `show_gps()`
- `/Users/elephantatech/projects/moon_traveler/tests/test_ui.py` — minimap boundary conditions, player marker placement

---

### Weather System Overhaul

**Description:** Each location has a dynamic weather state (clear, light_frost, ice_storm, geyser_active, whiteout) that transitions over time based on hours elapsed. Weather affects GPS scan range, water source availability, and LLM creature mood framing.

**Technical approach:**
- Add `weather: str = "clear"` field to `Location` dataclass in `src/world.py`. Initial values assigned during generation weighted by `loc_type` (geyser fields default toward `geyser_active`, ice lakes toward `light_frost`)
- Add `src/weather.py` (new): `WeatherSystem` holds a `dict[str, str]` of `{location_name: weather_state}` and a Markov-chain transition matrix per location type. `tick(location_name, hours_elapsed, rng)` advances weather state for a given location
- `WeatherSystem` serialized as a single JSON blob under key `weather` in the SQLite saves table via `src/save_load.py`
- `cmd_look()` in `src/commands.py` shows current weather at location
- `cmd_scan()` applies range modifier: `whiteout` halves effective scan range; `geyser_active` adds 2 km
- Water source frozen: if `weather == "whiteout"` at a `water_source` location, `player.replenish_water()` is blocked and ARIA warns
- LLM system prompt: `build_system_prompt()` in `src/llm.py` appends `"Current weather at {location}: {weather}. Let this subtly color your mood."` using weather passed in from context

**Estimated effort:** L

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/world.py` — `weather` field on `Location`
- `/Users/elephantatech/projects/moon_traveler/src/weather.py` (new) — `WeatherSystem`, transition matrices
- `/Users/elephantatech/projects/moon_traveler/src/travel.py` — call `weather_system.tick()` on arrival
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `cmd_look()` weather display; `cmd_scan()` range modifier
- `/Users/elephantatech/projects/moon_traveler/src/llm.py` — weather appended to system prompt
- `/Users/elephantatech/projects/moon_traveler/src/save_load.py` — serialize/deserialize `WeatherSystem`
- `/Users/elephantatech/projects/moon_traveler/tests/test_weather.py` (new)

---

### Creature Relationships

**Description:** Creatures know specific other creatures by name. A creature can mention a neighbor, reveal their location, or vouch for them. Being vouched for by a trusted creature grants a +5 first-meeting trust bonus. Creates an emergent social graph that rewards thorough exploration.

**Technical approach:**
- Add `knows_creatures: list[str]` (creature IDs) and `vouched_by: list[str]` (creature IDs) to the `Creature` dataclass in `src/creatures.py`
- Population during generation: each creature knows 1–3 creatures at locations within `radius * 0.4`; `vouched_by` is set reciprocally when a creature's `knows_creatures` includes another
- `build_system_prompt()` in `src/llm.py` appends a brief known-creatures context: `"You know: {name} the {archetype} at {location}. Mention them if relevant."`
- New LLM action tag `[REVEAL_CREATURE:creature_id]`: when fired, calls `player.discover_location(creature.location_name)` in `apply_actions()` in `src/llm.py`
- Vouch bonus: on first `cmd_talk()` with a creature, if `creature.id` is in the `vouched_by` list of any creature the player has already talked to with trust > 40, apply `creature.trust = min(100, creature.trust + 5)`
- Template fallback: at trust ≥ 35, 30% chance per conversation of mentioning a known creature via canned templates added to `src/data/prompts.py`

**Estimated effort:** L

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/creatures.py` — `knows_creatures`, `vouched_by` fields; generation pass
- `/Users/elephantatech/projects/moon_traveler/src/llm.py` — system prompt extension, `REVEAL_CREATURE` tag parsing and application
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — vouch bonus on first talk
- `/Users/elephantatech/projects/moon_traveler/src/save_load.py` — serialize new fields
- `/Users/elephantatech/projects/moon_traveler/tests/test_creatures.py` — relationship generation, vouch bonus
- `/Users/elephantatech/projects/moon_traveler/tests/test_llm_actions.py` — `REVEAL_CREATURE` parsing

---

### Crafting System Expansion

**Description:** At the Crash Site's ship bays, players can combine raw materials into higher-tier components. Gives junk items a redemption arc (one recipe uses junk), reduces pressure on finding rare materials through NPCs, and adds meaningful choices for surplus items.

**Technical approach:**
- Add `src/crafting.py` (new) with `RECIPES: dict[str, dict]` — `{output_item: {"inputs": [(item, qty), ...], "description": str}}`
  - `thermal_paste` = `bio_gel` ×2 + `ice_crystal` ×1
  - `hull_patch` = `metal_shard` ×2
  - `power_cell` = `circuit_board` ×1 + `ice_crystal` ×2
  - `alien_relic` (cosmetic) = any 3 distinct junk items (triggers unique ARIA monologue)
- Add `can_craft(player, recipe) -> bool` and `execute_craft(player, recipe_key) -> str` in `src/crafting.py`
- Add `craft` as a new sub-menu option in `cmd_ship()` in `src/commands.py` — only accessible at Crash Site. Shows available recipes, highlights craftable ones, prompts selection, validates, deducts inputs, adds output
- Crafting costs 2 hours: `player.consume_resources(2)` deducted before crafting
- `ITEM_DESCRIPTIONS` in `src/difficulty.py` (or `src/data/items.py` after the tech-debt split) updated with recipe descriptions for craftable output items
- ARIA junk relic monologue (5 lines of lore about the assembled artifact) added to `src/data/prompts.py`

**Estimated effort:** M

**Dependencies:** None directly; cleaner with the `src/data/items.py` tech-debt split

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/crafting.py` (new)
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — craft sub-menu in `cmd_ship()`
- `/Users/elephantatech/projects/moon_traveler/src/difficulty.py` (or `src/data/items.py`) — recipe descriptions
- `/Users/elephantatech/projects/moon_traveler/src/data/prompts.py` — ARIA relic monologue
- `/Users/elephantatech/projects/moon_traveler/tests/test_crafting.py` (new)

---

### New Creature Archetypes: Scholar, Scout, Priest

**Description:** Three new archetypes expand the social landscape. The Scholar trades knowledge for knowledge and asks follow-up questions. The Scout reveals multiple locations at once at medium trust. The Priest provides suit repair via a "blessing" ritual with no battery cost.

**Technical approach:**
- Add three entries to `ROLE_CAPABILITIES` in `src/creatures.py`:
  - `Scholar`: provides `circuit_board`, `antenna_array`; trust thresholds similar to `Wise Elder`; gives +5 instead of +3 trust per conversation exchange (Scholar-specific override in `cmd_talk()`)
  - `Scout`: provides food/water and location reveals via new `[REVEAL_LOCATIONS:loc1,loc2]` action tag at trust 30+; materials `metal_shard`, `ice_crystal` at trust 45+
  - `Priest`: provides suit repair via new `[BLESS]` action tag (restores 15% suit, unlimited uses at trust 40+, no drone battery cost); provides `thermal_paste` at trust 60+
- Add 5 `FALLBACK_RESPONSES`, 1 `PERSONALITY_DETAILS` entry, and 3 `DRONE_ARCHETYPE_TIPS` per new archetype to `src/data/prompts.py`
- Add `REVEAL_LOCATIONS` and `BLESS` action tag patterns to `_ACTION_PATTERN` regex in `src/llm.py`; handle in `parse_actions()` and `apply_actions()`
- New archetypes enter the weighted selection pool in `src/creatures.py`; guaranteed spawn list (Merchant, Builder, Healer) is unchanged

**Estimated effort:** M

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/creatures.py` — `ROLE_CAPABILITIES`, archetype pool
- `/Users/elephantatech/projects/moon_traveler/src/data/prompts.py` — fallbacks, tips, personality
- `/Users/elephantatech/projects/moon_traveler/src/llm.py` — `REVEAL_LOCATIONS`, `BLESS` parsing and application
- `/Users/elephantatech/projects/moon_traveler/tests/test_creatures.py` — new archetype generation
- `/Users/elephantatech/projects/moon_traveler/tests/test_llm_actions.py` — new action tag parsing

---

### Location Events

**Description:** Each location type has a pool of 5 unique one-time narrative scenes that fire on first visit. Scenes add lore, and some provide small bonuses (a free item, a small trust hint for the next NPC, a minor stat restore). Makes exploration feel rewarding beyond finding creatures and items.

**Technical approach:**
- Add `event_triggered: bool = False` to `Location` dataclass in `src/world.py`; persist in `to_dict()` / `from_dict()`
- Add `src/data/events.py` (new) with `LOCATION_EVENTS: dict[str, list[EventData]]` where `EventData` is `{"narrative": [str, ...], "bonus": dict | None}`. 10 location types × 5 events each = 50 event entries
  - Example bonuses: `{"type": "item", "item": "bio_gel"}`, `{"type": "trust_bonus", "amount": 5}`, `{"type": "suit_repair", "amount": 5}`, `None` (pure lore)
- In `cmd_look()` in `src/commands.py`: after `look` at a newly arrived location (`not loc.visited`), if `not loc.event_triggered`, pick a random event, narrate it via `ui.narrate_lines()`, apply bonus, set `loc.event_triggered = True`
- Trust bonus stored as a temporary `ctx.pending_trust_bonus: int = 0` on `GameContext`; consumed on the next `cmd_talk()` call

**Estimated effort:** M

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/world.py` — `event_triggered` field
- `/Users/elephantatech/projects/moon_traveler/src/data/events.py` (new) — `LOCATION_EVENTS`
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `cmd_look()` event trigger; `cmd_talk()` consumes trust bonus
- `/Users/elephantatech/projects/moon_traveler/tests/test_world.py` — event trigger, one-time-only enforcement

---

### Day/Night Cycle

**Description:** Enceladus's 32.9-hour orbital period is modeled as a day/night counter based on `player.hours_elapsed`. Time of day is shown in the status bar, affects hazard probabilities, creature trust modifiers, and LLM mood framing.

**Technical approach:**
- Add `time_of_day(hours_elapsed: int) -> str` in `src/world.py`: returns `"day"` if `(hours_elapsed % 33) < 16`, else `"night"`
- Add optional `active_time: str = "any"` to `ROLE_CAPABILITIES` entries in `src/creatures.py`: `"day"`, `"night"`, or `"any"`. Apply `+5` trust per exchange during preferred time, `-3` during non-preferred (floor at 0)
- Display time of day in `show_status()` in `src/ui.py` and in the TUI status bar markup
- Separate night-mode hazard probability dict in `src/travel.py`: thin ice collapse +3% at night, geyser eruption -2% at night, ice storm +2% at night
- LLM system prompt: append `"It is currently {time_of_day} on Enceladus."` to the base prompt in `src/llm.py`
- ARIA adds 5 new orbital-transition musings to the pool in `src/travel.py` / `ARIA_MUSINGS`

**Estimated effort:** M

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/world.py` — `time_of_day()` utility
- `/Users/elephantatech/projects/moon_traveler/src/creatures.py` — `active_time` in `ROLE_CAPABILITIES`; trust modifier in `cmd_talk()`
- `/Users/elephantatech/projects/moon_traveler/src/travel.py` — night hazard probability table
- `/Users/elephantatech/projects/moon_traveler/src/llm.py` — time of day in system prompt
- `/Users/elephantatech/projects/moon_traveler/src/ui.py` — `show_status()` time display
- `/Users/elephantatech/projects/moon_traveler/tests/test_world.py` — `time_of_day()` correctness

---

## v0.7.0 — Multiplayer & Community

**Release target:** 12–16 weeks after v0.6.0

---

### Leaderboards

**Description:** A local SQLite leaderboard stores high scores from completed (win) games. Optional cloud leaderboard submits scores to a REST API for a global top-10 view. Local-first; cloud is opt-in.

**Technical approach:**
- Add `leaderboard` table to `~/.moonwalker/saves/moon_traveler.db` in `src/save_load.py`: `(id INTEGER PK, score INTEGER, grade TEXT, mode TEXT, seed TEXT, survival_hours INTEGER, real_time_seconds INTEGER, created_at TIMESTAMP)`
- `record_score(score, grade, mode, seed, stats)` called from `show_win_sequence()` in `src/game.py`
- Add `scores` command in `src/commands.py` displaying local top-10 as a Rich table sorted by score desc
- Cloud opt-in: `config leaderboard on` sets `leaderboard_enabled: true` in config. When enabled, `record_score()` spawns a background thread that POSTs the score JSON to a configurable `leaderboard_url` (default `https://api.moontraveler.game/scores`) — fails silently, never blocks gameplay
- Cloud server endpoint is a separate deployment (not in this repo) that validates the seed + score plausibility

**Estimated effort:** L (local: S; cloud integration: M; server: separate project)

**Dependencies:** Session stats tracker, post-game stats screen

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/save_load.py` — `leaderboard` table, `record_score()`, `get_top_scores()`
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — call `record_score()` on win
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `scores` command
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `leaderboard_enabled`, `leaderboard_url`
- `/Users/elephantatech/projects/moon_traveler/tests/test_save_load.py` — leaderboard insert and query

---

### Seed Sharing

**Description:** Players can share their world seed as a short Base62 code. Another player enters it at new-game time to play the same world. A curated list of 5 challenge seeds ships with the game.

**Technical approach:**
- World seed already exists as `world_seed` (integer) on `GameContext` and in the save system
- Add Base62 encode/decode functions in `src/world.py` or a new `src/seed.py`: 6–8 character codes using `[0-9A-Za-z]` alphabet. `encode_seed(n: int) -> str`, `decode_seed(s: str) -> int`
- Add `seed` command in `src/commands.py`: displays current world seed as both integer and Base62 code
- In the new-game flow in `src/game.py`, after mode selection, prompt: `"Enter a seed (or press Enter for random):"`. Decode Base62 input → integer → pass as `seed` to `generate_world(seed=...)`
- Add `src/data/seeds.py` (new): `CHALLENGE_SEEDS: list[dict]` — 5 entries with `{"name": str, "code": str, "description": str}`. Shown as a menu option at new-game seed prompt

**Estimated effort:** S

**Dependencies:** None

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/world.py` or `src/seed.py` (new) — Base62 encode/decode
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — seed prompt in new-game flow
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `seed` display command
- `/Users/elephantatech/projects/moon_traveler/src/data/seeds.py` (new) — curated challenge seeds
- `/Users/elephantatech/projects/moon_traveler/tests/test_world.py` — seed encode/decode round-trip

---

### Mod Support

**Description:** YAML/JSON files in `~/.moonwalker/mods/` add custom creature archetypes, location types, and LLM prompt overrides without modifying source code. Malformed mods are skipped with a warning; they never crash the game.

**Technical approach:**
- Add `src/mod_loader.py` (new): `load_mods() -> dict` scans `~/.moonwalker/mods/*.yaml` and `*.json` at startup. Validates each file against a minimal JSON Schema before merging
- Creature archetype mod schema: `{archetype_name, personality_detail, fallback_responses: [str ×5], role_capabilities: {provides, trust_threshold, materials}}`
- Location type mod schema: `{type_name, weight, possible_items, possible_upgrades, descriptions: [str ×3], food_source_chance, water_source_chance}`
- Prompt override schema: `{archetype_name, system_prompt_append: str}` — appended to the base prompt, never replacing it. This prevents mods from stripping safety framing.
- `load_mods()` called before world generation in `src/game.py`. Loaded data merged into module-level dicts in `src/creatures.py`, `src/world.py`, and `src/data/prompts.py` — these dicts must be made mutable (currently they are module-level constants defined inline)
- Add `--no-mods` flag to `src/game.py` main entry for reproducible challenge runs
- Add `mods_enabled: bool = True` to `src/config.py`

**Estimated effort:** XL

**Dependencies:** Seed sharing (mods must be declared alongside seeds for full reproducibility)

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/mod_loader.py` (new)
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — `load_mods()` call; `--no-mods` flag
- `/Users/elephantatech/projects/moon_traveler/src/creatures.py` — `ROLE_CAPABILITIES` made mutable
- `/Users/elephantatech/projects/moon_traveler/src/world.py` — `LOCATION_TYPES` made mutable
- `/Users/elephantatech/projects/moon_traveler/src/data/prompts.py` — `PERSONALITY_DETAILS`, `FALLBACK_RESPONSES` made mutable
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `mods_enabled`
- `/Users/elephantatech/projects/moon_traveler/install.sh` — create `~/.moonwalker/mods/` directory
- `/Users/elephantatech/projects/moon_traveler/tests/test_mod_loader.py` (new)

---

### Achievement System

**Description:** 30+ achievements covering milestones, social interaction, exploration, and Easter eggs. Stored locally in SQLite. Non-intrusive unlock notification (auto-dismissed panel). Secret achievements show as `???` until earned.

**Technical approach:**
- Add `src/achievements.py` (new): `ACHIEVEMENTS: dict[str, AchievementDef]` where `AchievementDef = {name, description, secret: bool, condition_fn: Callable[[GameContext], bool]}`
- `AchievementTracker` class: holds `unlocked: set[str]` persisted in a new `achievements` table in `moon_traveler.db`; `check_all(ctx: GameContext)` evaluates every locked achievement's `condition_fn` and calls `unlock(id)` on success
- `check_all()` called in the main dispatch loop after each command and after key events (win, lose, trade, give, trust change)
- Unlock notification: `ui.show_panel("Achievement Unlocked", name + description, style="bold yellow")` with a 2-second pause. In TUI mode this renders into the `RichLog` log naturally
- `achievements` command: table of all achievements — unlocked show full name+description, locked non-secret show name with `[LOCKED]`, locked secret show `??? [LOCKED]`
- Sample achievements:
  - First Contact — talk to first creature
  - Diplomat — trust > 70 with 5 creatures in one game
  - Pack Rat — collect all 10 junk items in one game
  - Speedrunner — win in under 20 in-game hours
  - Peacemaker — reach trust 50 with a creature that started hostile
  - Cartographer — visit all locations in a Long game
  - Junk Sculptor — trigger the junk easter egg
  - Brutal Survivor — win on Brutal difficulty
  - Ghost — win without any escort companions
  - Whisper Network — meet 3 creatures via `REVEAL_CREATURE` referrals (v0.6.0 dependency)

**Estimated effort:** L

**Dependencies:** Session stats tracker (some conditions use session metrics). Some achievements require v0.6.0 features.

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/achievements.py` (new)
- `/Users/elephantatech/projects/moon_traveler/src/save_load.py` — `achievements` table
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — `AchievementTracker` on `GameContext`; evaluate in game loop
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `achievements` command
- `/Users/elephantatech/projects/moon_traveler/src/ui.py` — unlock notification panel
- `/Users/elephantatech/projects/moon_traveler/tests/test_achievements.py` (new)

---

### Challenge Modes

**Description:** Three structured challenge run variants selectable at new game: Speedrun (real-time countdown display), Ironman/Permadeath (save deleted on game over), and Pacifist (score multiplier for avoiding angering hostile creatures).

**Technical approach:**
- Add `challenge_mode: str | None` to `GameContext` and persist under key `challenge_mode` in the save system
- **Speedrun:** `ctx.stats.session_start` already exists via the stats tracker. In the TUI status bar markup, append `⏱ MM:SS` in bright_cyan, updated each status bar refresh. On win, record real-time alongside in-game hours in the leaderboard with a `challenge: "speedrun"` flag
- **Ironman:** on game over in `show_lose_sequence()`, call `delete_save(ctx.save_slot)` in `src/save_load.py` before rendering the game-over screen. `cmd_load()` refuses with an error message if `ctx.challenge_mode == "ironman"`
- **Pacifist:** track `ctx.stats.hostile_creatures_angered: int` (incremented when a hostile creature's trust < 15 triggers the chase-away branch in `cmd_talk()`). Final score multiplied by `1.0 + 0.5 * (total_hostile / total_all)` if `hostile_creatures_angered == 0`, with partial credit per unangered hostile
- `delete_save(slot)` added to `src/save_load.py`: drops all rows for the slot from `saves`, `save_meta`, `chat_history`, `creature_memory` tables

**Estimated effort:** M

**Dependencies:** Session stats tracker, post-game stats screen, leaderboards

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `GameContext.challenge_mode`; Ironman load block; hostile-anger increment
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — challenge mode prompt at new game
- `/Users/elephantatech/projects/moon_traveler/src/ui.py` — speedrun timer in TUI status bar
- `/Users/elephantatech/projects/moon_traveler/src/save_load.py` — persist `challenge_mode`; `delete_save()` utility
- `/Users/elephantatech/projects/moon_traveler/src/stats.py` — `hostile_creatures_angered` counter; pacifist score multiplier
- `/Users/elephantatech/projects/moon_traveler/tests/test_challenge.py` (new)

---

## v1.0.0 — Full Release

**Release target:** 12–16 weeks after v0.7.0. Targets Steam Early Access and broad distribution.

---

### Steam Release Preparation

**Description:** Steamworks SDK integration for Steam achievements, Steam Cloud saves, and the Steam build pipeline. `steamworks.py` is an optional dependency — the game runs fully without it.

**Technical approach:**
- Integrate `steamworks.py` (Python Steamworks wrapper) as an optional import guarded by `try/except ImportError`
- `AchievementTracker.unlock()` in `src/achievements.py` calls `steam.StatsAndAchievements.SetAchievement(achievement_id)` when the library is loaded
- Steam Cloud: optional `SteamCloudBackend` class in `src/save_backends.py` (new) that mirrors SQLite writes to Steam's remote storage API. The existing local SQLite path remains primary.
- New `scripts/build_steam.py`: wraps PyInstaller with Steam redistribution settings, includes Steamworks redistributable, produces a Steam depot directory structure
- App ID, store assets (capsule art 460×215, hero 1920×620, screenshots ×5, trailer), and content descriptors are managed through Steamworks partner portal (outside the codebase)

**Estimated effort:** XL

**Dependencies:** Achievement system, stable v0.7.0 codebase

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/achievements.py` — Steam achievement sync hook
- `/Users/elephantatech/projects/moon_traveler/src/save_backends.py` (new) — `SaveBackend` ABC, `LocalFSBackend`, `SteamCloudBackend`
- `/Users/elephantatech/projects/moon_traveler/src/save_load.py` — use injected backend instead of hard-coded SQLite path
- `/Users/elephantatech/projects/moon_traveler/scripts/build_steam.py` (new)
- `/Users/elephantatech/projects/moon_traveler/requirements-steam.txt` (new) — `steamworks` optional

---

### Full Documentation and Tutorials

**Description:** Comprehensive in-game tutorial expansion (context-sensitive post-tutorial tips), offline HTML manual bundled with the game, mod author documentation, and a contributor guide.

**Technical approach:**
- Extend `src/tutorial.py` with a `TipsManager` that fires optional one-shot context tips when the player uses a new feature for the first time (crafting bay, achievements command, challenge mode selection). Tips are non-blocking: shown once, dismissed immediately by any input
- Add `manual` command in `src/commands.py` that calls `webbrowser.open(docs_path)` where `docs_path` resolves to the bundled `docs/how-to-play.html` (in PyInstaller builds, detected via `sys._MEIPASS`)
- Update `docs/how-to-play.html` to cover all commands and features added through v0.7.0
- Add `docs/modding.md` covering the full mod schema with annotated examples for each mod type
- Add `CONTRIBUTING.md` at project root: architecture overview (data flow from entry point through to LLM and back), test running instructions, coding style guide (ruff, no type: ignore, docstrings on public functions)

**Estimated effort:** L

**Dependencies:** All v0.5.0–v0.7.0 features must be stable and complete before docs are written

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/tutorial.py` — `TipsManager` for post-tutorial tips
- `/Users/elephantatech/projects/moon_traveler/src/commands.py` — `manual` command
- `/Users/elephantatech/projects/moon_traveler/docs/how-to-play.html` — comprehensive update
- `/Users/elephantatech/projects/moon_traveler/docs/modding.md` (new)
- `/Users/elephantatech/projects/moon_traveler/CONTRIBUTING.md` (new)
- `/Users/elephantatech/projects/moon_traveler/scripts/build_release.py` — include `docs/` in PyInstaller `--add-data`

---

### Localization (i18n Framework)

**Description:** A translation framework enabling community-contributed locale files. Initial target: French, German, Spanish, Japanese, Brazilian Portuguese. Creature dialogue is inherently language-flexible via LLM system prompt directive.

**Technical approach:**
- Add `src/i18n.py` (new): `_(key: str) -> str` looks up the current locale in a `dict[str, str]` loaded from `~/.moonwalker/locale/{lang}.json` at startup; falls back to `en` key value if the translation is missing
- String replacement across all source files is the bulk of the effort: `"Commander, food reserves..."` becomes `_("aria.food.50")`. This is done in phases over multiple PRs, starting with the most visible strings (ARIA warnings, Drone speech, status UI labels)
- Locale JSON format: flat key-value, `{"aria.food.50": "Commander, food reserves have dropped below 50%..."}`. Rich markup tags within values are preserved as-is since `_()` returns the raw string before rendering
- `config lang en|fr|de|es|ja|pt` command: sets `lang` in config, reloads locale dict at next command
- LLM creature dialogue: append `"Respond in {language_name}."` to the system prompt in `build_system_prompt()` when `lang != "en"`
- Community translation files live in `translations/` directory in the repo; CI validates their JSON syntax and checks for missing keys against `en.json`

**Estimated effort:** XL (framework: M; string extraction across all files: L; each translation: XL each by community contributors)

**Dependencies:** All features must be complete before string extraction to avoid constant churn on translation keys

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/i18n.py` (new)
- All `src/*.py` files — string replacement in phases (large-scale refactor)
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `lang` setting
- `/Users/elephantatech/projects/moon_traveler/src/llm.py` — language directive in system prompt
- `/Users/elephantatech/projects/moon_traveler/translations/` (new directory) — `en.json`, `fr.json`, etc.

---

### Custom Soundtrack and Ambient Audio

**Description:** Replace the beep-pattern sound system events with an original composed soundtrack: boot theme, exploration ambient loop, tension music (low resources), and victory/game-over fanfares in OGG format. Existing beep patterns remain for event sounds that play over music.

**Technical approach:**
- Add `src/music.py` (new): `MusicSystem` wrapping `pygame.mixer` (optional dependency) with `play_track(name: str, loop: bool = True)`, `fade_to(name: str, ms: int = 2000)`, `stop()`, `set_volume(v: float)`. If `pygame` unavailable, all methods are no-ops.
- Track files as OGG in `src/data/audio/`: `boot.ogg`, `explore.ogg`, `tension.ogg`, `victory.ogg`, `game_over.ogg`
- Music transitions: `explore.ogg` loops during normal play; transition to `tension.ogg` when any vital drops below 20% (`ShipAI` already tracks these thresholds — hook into the 15% warning); `fade_to("explore")` on recovery
- Volume: `config music 0-100` command; `music_volume: int = 70` in `src/config.py`
- In PyInstaller builds: `--add-data src/data/audio:src/data/audio`
- Original soundtrack is a separate creative deliverable; OGG files are not included in the repository until composed and licensed

**Estimated effort:** L (implementation: M; original soundtrack: separate deliverable by composer)

**Dependencies:** None (implementation); original audio assets required for full feature

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/music.py` (new)
- `/Users/elephantatech/projects/moon_traveler/src/game.py` — `music.play_track("boot")` at startup; `music.play_track("explore")` in game loop
- `/Users/elephantatech/projects/moon_traveler/src/ship_ai.py` — hook `fade_to("tension")` at 15% vitals warning
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `music_volume`
- `/Users/elephantatech/projects/moon_traveler/src/data/audio/` (new directory)
- `/Users/elephantatech/projects/moon_traveler/requirements.txt` — `pygame` as optional

---

### Web Version

**Description:** Run Moon Traveler Terminal in a browser via Textual's built-in `textual serve` web mode, which exposes a full terminal emulator over WebSocket. LLM inference is unavailable in-browser; the game uses fallback dialogue or connects to an optional backend inference server.

**Technical approach:**
- `textual serve play_tui.py --port 8000` already works in Textual 0.47+ with no code changes for basic functionality. The primary engineering work is the save/config storage abstraction.
- Add `src/save_backends.py` (new): `SaveBackend` abstract base class with `read(key)`, `write(key, value)`, `delete(key)`, `list_slots()`. `LocalFSBackend` wraps the existing SQLite path. `InMemoryBackend` (for web: no persistent storage unless cookies or server-side storage is added later)
- Refactor `src/save_load.py` to use an injected `SaveBackend` instance rather than calling SQLite directly. The backend is set once during `game.main()` based on whether `web_mode` is detected (via env var `MOON_WEB=1` or Textual's `App.is_web` property)
- LLM inference: in web mode, `src/llm.py` checks for `MOON_INFERENCE_URL` env var. If set, inference calls go to a POST endpoint (`/infer`) on a separately deployed llama-cpp-python server. If unset, fallback dialogue is used.
- Sound system is disabled in web mode (browser terminal emulator does not support terminal bell or `say`)
- Add `scripts/serve_web.py` (new): sets `MOON_WEB=1`, calls `textual serve play_tui.py`

**Estimated effort:** XL

**Dependencies:** Stable v0.7.0. Save backend abstraction is a prerequisite. Textual web mode must be production-ready.

**Files affected:**
- `/Users/elephantatech/projects/moon_traveler/src/save_backends.py` (new)
- `/Users/elephantatech/projects/moon_traveler/src/save_load.py` — use injected backend
- `/Users/elephantatech/projects/moon_traveler/src/llm.py` — REST inference backend option
- `/Users/elephantatech/projects/moon_traveler/src/sound.py` — no-op in web mode
- `/Users/elephantatech/projects/moon_traveler/src/config.py` — `web_mode` detection
- `/Users/elephantatech/projects/moon_traveler/scripts/serve_web.py` (new)

---

## Technical Debt

These items are not blocking any release but accumulate friction as the codebase grows. Each is actionable before the release milestone noted.

### Architecture

**`src/commands.py` handles too many responsibilities.**
At 800+ lines, `commands.py` contains the dispatch table, all handler functions, the full conversation loop, and `GameContext`. Split into a `src/commands/` package: `src/commands/__init__.py` (GameContext + dispatch), `src/commands/travel.py`, `src/commands/social.py`, `src/commands/ship.py`, `src/commands/meta.py`. This is a pure refactor — no behavior change.
- Effort: M | Priority: before v0.6.0 (new commands worsen the problem)

**`src/ui.py` has implicit global state.**
`get_toolbar_text()` reads game state via module-level global references. The clean fix is to pass the toolbar markup string explicitly from `GameContext` after each command dispatch, eliminating the implicit coupling. This is a prerequisite for proper screen reader mode.
- Effort: S | Priority: v0.5.0

**`src/llm.py` uses module-level mutable globals.**
`_llm_model` and `_llm_available` are module-level. This works for single-game use but prevents multiple game instances (required for web mode where concurrent sessions are possible). Wrap in an `LLMEngine` class with `load()`, `generate()`, `is_available()` methods. Inject via `GameContext`.
- Effort: M | Priority: v1.0.0 (prerequisite for web mode backend)

**Dual input system duplicates completion logic.**
`GameCompleter` (prompt_toolkit) and `GameSuggester` (Textual) both implement the same completion rules. Extract a `CompletionProvider(ctx)` class with a single `get_all_suggestions(text: str) -> list[str]` method. Both front-ends delegate to it. Eliminates the current synchronization risk where adding a new completion to one but not the other.
- Effort: S | Priority: v0.5.0

**`ITEM_DESCRIPTIONS` is misplaced in `src/difficulty.py`.**
Difficulty scaling and item descriptions are unrelated concerns. Move descriptions, junk item lists, and (future) crafting recipes to `src/data/items.py`. `src/difficulty.py` retains only `MODE_DIFFICULTY`, `get_difficulty()`, and the easter egg logic.
- Effort: S | Priority: v0.6.0 (natural home for crafting recipes)

### Testing Gaps

**TUI integration — zero coverage.**
`src/tui_app.py` and `src/tui_bridge.py` have no automated tests. Textual provides `App.run_test()` for headless async testing. Add `tests/test_tui.py` covering: the command queue/response flow, ask mode toggling, tab cycling through candidates, history navigation, and the Ctrl+C unblock behavior.
- Effort: M

**Sound system — zero coverage.**
`src/sound.py` has no tests. The primary risk is the threading behavior — a test verifying that `play("success")` is non-blocking, that `_lock` is released on exception, and that the Linux player detection falls back gracefully to beep patterns would catch regressions.
- Effort: S

**Save version migration — no fixture tests.**
`tests/test_save_load.py` tests the current (v4) format but has no tests for loading v1/v2/v3 saves. Add fixtures: minimal v3 SQLite blobs (missing `memory`, `role_inventory`, `given_items` columns) loaded and confirmed to produce valid defaults.
- Effort: S

**LLM action tag edge cases — gaps.**
Malformed tags are not tested: `[GIVE_MATERIAL:]` (missing item), `[TRADE::]` (empty fields), `[GIVE_MATERIAL:unknown_item]` (item not in role_inventory). The `parse_actions()` regex requires the colon and a non-empty param, but behavior on edge cases needs explicit test coverage.
- Effort: S

**Difficulty multiplier integration — untested end-to-end.**
`tests/test_difficulty.py` tests `get_difficulty()` in isolation but does not verify that Brutal mode drain rates (1.5× multiplier) are actually applied during `consume_resources()` in `src/travel.py`. An integration test using a Brutal `GameContext` and a mocked travel run would catch regression if the multiplier wiring breaks.
- Effort: S

**`cmd_ship()` bay menus — untestable without input mocking.**
The ship bay interactive sub-menus call `ui.console.input()` directly. These need a `FakeConsole` fixture (similar to how the test suite already patches other console calls) to enable coverage of install, cook, charge, and repair flows.
- Effort: M

### Performance

**LLM context growth in long games.**
`update_creature_memory()` in `src/llm.py` fires a secondary LLM inference after every conversation. In a long game with 20 creatures and frequent conversations, this can double the total inference count. Consider batching: only run memory updates every 3 conversations per creature, or only on save. A `creature.conversation_count` field (already inferable from `len(conversation_history)`) can gate the update.
- Effort: S | Priority: v0.5.0

**Autosave write frequency.**
Autosave fires after every travel, conversation, give, and trade — potentially 20+ SQLite writes per minute in active play. The payload is small today, but v0.6.0 additions (weather state, creature relationships, location events) will grow it. Debounce to fire at most once every 30 seconds with a mandatory flush on quit.
- Effort: S | Priority: v0.6.0

---

## Infrastructure

### CI/CD Improvements

**Cross-platform test matrix.**
`ci.yml` runs tests only on `ubuntu-latest`. Windows and macOS behavior diverges (path separators, `say` availability, ANSI terminal codes). Add:

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
```

Effort: S | Priority: v0.5.0

**Python version matrix.**
Add Python 3.12 and 3.13 to the test matrix alongside 3.11 to detect forward-compatibility breaks early. The `str | None` type hint syntax requires 3.10+ and is already satisfied.
- Effort: S | Priority: v0.5.0

**Test coverage reporting.**
Add `pytest-cov` to CI. Report coverage percentage as a README badge. Gate PRs on coverage not dropping below 80%. The 231-test suite is healthy in count but coverage percentage is currently unknown.
- Effort: S | Priority: v0.5.0

**Pre-commit hooks.**
Add `.pre-commit-config.yaml` with `ruff` (lint), `ruff format` (formatting), and a `pytest --collect-only` sanity hook. Catches failures before they reach CI. The repo already uses ruff in CI lint — pre-commit makes it local.
- Effort: S | Priority: immediately

**Changelog automation.**
Add `scripts/check_changelog.py` that verifies `CHANGELOG.md` has an entry matching the current version in `pyproject.toml`. Runs as a required CI check on release-candidate branches. Prevents shipping versions without documented changes.
- Effort: S | Priority: before v0.5.0

**Extract CHANGELOG section for release notes.**
The current release workflow uses `generate_release_notes: true` (GitHub auto-generated from PR titles). Replace with a `scripts/extract_changelog.py` that outputs the CHANGELOG.md block for the current tag and passes it as the release body. Produces professional, handwritten release notes.
- Effort: S | Priority: next release after v0.4.0

### Automated Testing on All Platforms

**Sound system CI exclusion.**
When sound tests are added, CI must not play actual system sounds. Use `MOON_TEST_NOSOUND=1` environment variable to make `src/sound.py` all functions return immediately. Set this var in all CI job environments.

**LLM tests without a model.**
All tests in `tests/test_llm_actions.py` mock the LLM model out already — this pattern must be enforced for all future LLM-dependent tests. CI should never require a real GGUF file.

**TUI tests in headless CI.**
Textual's `App.run_test()` runs without a real TTY and works in GitHub Actions. All `tests/test_tui.py` tests must use this harness — never call `app.run()` directly in tests.

### Documentation Generation

**Auto-generate command reference.**
The command table in `spec.md` Section 11 and `docs/how-to-play.html` is maintained by hand. Add `scripts/gen_docs.py` that introspects the command dispatch table in `src/commands.py` (once it is refactored into a registry dict with metadata) and emits the markdown table. Keeps docs synchronized with code automatically.
- Effort: M | Priority: v1.0.0 (requires commands refactor first)

### Release Automation

**Version bumping script.**
`pyproject.toml` and `spec.md` both contain the version string and must be updated in sync. Add `scripts/bump_version.py <new_version>` that updates both files atomically and creates a git commit + tag. Prevents the version skew seen across the v0.3.x series.
- Effort: S | Priority: before v0.5.0

**macOS notarization.**
PyInstaller binaries on macOS trigger Gatekeeper warnings on first launch without notarization. Required for Steam and broad distribution. Wire `codesign` + `notarytool` into the macOS job in `release.yml`. Requires an Apple Developer account and certificates stored as GitHub Actions secrets.
- Effort: L | Priority: v1.0.0

**Windows code signing.**
Unsigned `.exe` files trigger Windows SmartScreen. Required for Steam. Wire `signtool.exe` into the Windows job in `release.yml`. Requires a code signing certificate purchase and private key stored as a GitHub Actions secret.
- Effort: L | Priority: v1.0.0

---

## Known Issues & Enhancements (post v0.4.0)

### Responsive Status Bar (#1)
The TUI status bar truncates when the terminal window is narrowed. Items are lost off-screen. The bar should detect terminal width and wrap to multiple lines, or prioritize which items to show at narrow widths (vitals first, creature info second, followers third).
- Effort: M | Priority: v0.5.0
- Files: `src/ui.py` (render_status_bar), `src/game.tcss` (#status-bar height)

### Drone Service Boot Messages (#2)
Replace generic "Loading LLM model... CPU only" messages with immersive drone service boot sequence:
- "Initializing ARIA drone service..."
- "Loading AI model: {model_name} ({mode})"
- "AI service active — ARIA online" / "AI service unavailable — fallback dialogue"
- Show model name and compute mode as drone status (visible in `drone` command and dev mode)
- Keep load duration timer
- Effort: S | Priority: v0.5.0
- Files: `src/llm.py` (load_model messages), `src/game.py` (boot flow), `src/drone.py` (model info field)

---

*This roadmap is a living document. Update it alongside each release by moving completed sections into CHANGELOG.md and revising effort estimates based on actual implementation experience.*

---