# Moon Traveler CLI - Technical Specification

**Version:** 0.1.0
**Platform:** Python 3.11+, Windows / macOS / Linux
**Genre:** Text-based survival adventure

---

## 1. Overview

Moon Traveler CLI is a terminal-based survival game set on Enceladus, Saturn's icy moon. The player crash-lands, must explore procedurally generated locations, build relationships with alien creatures through LLM-powered conversation, collect repair materials, and fix their ship to escape.

### 1.1 Core Loop

```
Crash Land → Scan → Travel → Explore → Talk/Trade → Collect Materials → Repair Ship → Win
```

### 1.2 Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11 |
| Terminal UI | rich |
| Input | prompt_toolkit |
| LLM | llama-cpp-python |
| Model | Gemma 4 E2B (Q4_K_M GGUF, ~3.1 GB) |
| Build | PyInstaller |

### 1.3 Dependencies

```
rich
prompt_toolkit
llama-cpp-python
jinja2>=3.1.6
diskcache>=5.6.3
markupsafe>=3.0.3
numpy>=2.4.4
typing-extensions>=4.15.0
psutil>=7.2.2
```

---

## 2. Entry Point

### `play.py`
Adds project root to `sys.path`, imports and calls `src.game.main()`.

### `src/game.py` — `main()`
1. Show title screen
2. Check for existing saves → offer "New Game" / "Load Game"
3. If new game: prompt game length, detect GPU, prompt CPU/GPU mode, load LLM, init world, run boot sequence, start game loop
4. If load game: detect GPU, prompt CPU/GPU mode, load LLM, restore state, start game loop

---

## 3. Game Modes

| Parameter | Short | Medium | Long |
|-----------|-------|--------|------|
| Locations | 8 | 16 | 30 |
| Creatures | 5 | 12 | 20 |
| World Radius | 20 km | 40 km | 60 km |
| Hostile Creatures | 0 | 4 | 6 |
| Repair Materials Required | 3 | 5 | 8 |

### 3.1 Repair Materials by Mode

- **Short:** ice_crystal, metal_shard, bio_gel
- **Medium:** + circuit_board, power_cell
- **Long:** + thermal_paste, hull_patch, antenna_array

---

## 4. World Generation (`src/world.py`)

### 4.1 Location Data

```python
@dataclass
class Location:
    name: str              # e.g. "Frost Ridge"
    loc_type: str          # crash_site, plains, ridge, cave, etc.
    x: float               # X coordinate in km
    y: float               # Y coordinate in km
    items: list[str]       # Items present
    creature_id: str|None  # Linked creature
    discovered: bool       # Visible on GPS
    visited: bool          # Player has been here
    description: str       # Narrative text
    food_source: bool      # Renewable food
    water_source: bool     # Renewable water
```

### 4.2 Location Types (10 types)

| Type | Weight | Possible Items | Possible Upgrades | Food Source | Water Source |
|------|--------|---------------|-------------------|-------------|--------------|
| crash_site | — | — | — | No | No |
| plains | 3 | ice_crystal, metal_shard | — | No | No |
| ridge | 2 | metal_shard, antenna_array | thruster_pack | No | No |
| cave | 2 | bio_gel, power_cell, ice_crystal | battery_cell | 50% chance | No |
| geyser_field | 2 | thermal_paste, bio_gel | — | No | 50% chance |
| ice_lake | 1 | ice_crystal, circuit_board | — | No | 50% chance |
| ruins | 2 | circuit_board, power_cell, hull_patch | range_module, translator_chip | No | No |
| forest | 2 | bio_gel, ice_crystal | — | 50% chance | No |
| canyon | 2 | metal_shard, hull_patch, thermal_paste | range_module | No | No |
| settlement | 1 | circuit_board, antenna_array | cargo_rack, translator_chip | No | No |

### 4.3 Generation Algorithm

1. Crash Site placed at origin (0, 0), always discovered and visited
2. Remaining locations placed randomly within world radius
3. Minimum spacing: `radius * 0.15` between any two locations
4. Maximum isolation: `radius * 0.6` from nearest existing location
5. Up to 500 placement attempts before stopping
6. Each location gets 0-2 items from its type pool
7. 40% chance of a drone upgrade at eligible location types
8. Descriptions chosen randomly from 2-3 per type

### 4.4 Name Generation (`src/data/names.py`)

Format: `{Prefix} {Suffix}`

- **28 prefixes:** Frost, Crystal, Shadow, Geyser, Silent, Frozen, Deep, Bright, Hollow, Shattered, Ancient, Pale, Iron, Salt, Ember, Drift, Storm, Vapor, Glass, Obsidian, Lunar, Cobalt, Azure, Ashen, Veiled, Sunken, Titan, Crest
- **Suffixes per type:** 3-6 options each (e.g., Ridge: Ridge, Spine, Crest, Bluff, Escarpment, Edge)

### 4.5 Distance Calculation

Euclidean distance: `sqrt((x1-x2)^2 + (y1-y2)^2)` in kilometers.

---

## 5. Player (`src/player.py`)

```python
@dataclass
class Player:
    location_name: str = "Crash Site"
    inventory: dict[str, int]     # item_name → quantity
    food: float = 100.0           # percentage
    water: float = 100.0          # percentage
    suit_integrity: float = 92.0  # starts damaged from crash
    hours_elapsed: int = 0
    known_locations: set[str] = {"Crash Site"}
    food_warning_given: bool = False
    water_warning_given: bool = False
```

### 5.1 Resource Consumption (per hour of travel)

| Resource | Rate | Replenishment |
|----------|------|---------------|
| Food | -2% / hour | Food source locations → 100% |
| Water | -3% / hour | Water source locations → 100% |
| Suit Integrity | -0.5% / hour | Repair at Crash Site using drone battery |

### 5.2 Suit Repair

At the Crash Site, the `ship` command offers suit repair:
- Cost: 1% drone battery per 2% suit integrity restored
- Restores up to 100% or until battery runs out
- Requires minimum 10% drone battery

### 5.3 Lose Condition

`food <= 0 AND water <= 0`

---

## 6. Creatures (`src/creatures.py`)

```python
@dataclass
class Creature:
    id: str                         # "creature_0", "creature_1", ...
    name: str                       # From CREATURE_NAMES pool (30 names)
    species: str                    # From SPECIES_NAMES pool (20 species)
    archetype: str                  # One of 8 archetypes
    disposition: str                # friendly, neutral, hostile
    location_name: str              # Where creature lives
    trust: int = 0                  # 0-100
    knowledge: list[str]            # 1-3 from KNOWLEDGE_POOL (15 entries)
    conversation_history: list[dict] # Last 20 messages (10 exchanges)
    has_helped_repair: bool = False
    can_give_materials: list[str]   # 1-2 from MATERIALS_POOL
    knows_food_source: str|None     # Location name or None (40% chance)
    knows_water_source: str|None    # Location name or None (40% chance)
    color: str                      # Rich color from 20-color palette
```

### 6.1 Archetypes (8)

| Archetype | Personality |
|-----------|------------|
| Wise Elder | Patient, speaks in metaphors, values respect |
| Trickster | Loves riddles and wordplay, tests wits |
| Guardian | Protective, suspicious, respects strength |
| Healer | Gentle, empathetic, knows medicinal flora |
| Builder | Practical, curious about technology |
| Wanderer | Restless, knows terrain, speaks of distant places |
| Hermit | Prefers solitude, rare but weighty speech |
| Warrior | Fierce, direct, tests courage |

### 6.2 Dispositions

| Disposition | Initial Trust | Behavior |
|-------------|--------------|----------|
| Friendly | 25 | Inclined to help, concerned about player |
| Neutral | 10 | Must earn interest, won't volunteer info |
| Hostile | 0 | Deeply suspicious, may chase away at trust <15 |

### 6.3 Trust System

| Level | Range | Behavior |
|-------|-------|----------|
| Low | 0-34 | Guarded, reveals nothing significant |
| Medium | 35-69 | Warming up, shares some info |
| High | 70-100 | Will share knowledge, give materials, reveal sources |

**Trust gain:**
- Conversation: +3 per message exchange
- Gift: +15 (friendly/neutral), +10 (hostile)

### 6.4 Species Names (20)

Crystallith, Vapormaw, Glacien, Thermovore, Silicarn, Cryoform, Lumivex, Echoshell, Driftspore, Plumecrest, Geotherm, Frostweaver, Tidecrawler, Shardwing, Nebulite, Coralith, Voltspine, Mirrorscale, Boilback, Icemantis

### 6.5 Creature Names (30)

Kael, Threnn, Mivari, Ossek, Yuleth, Drenn, Xochi, Pallax, Zirren, Quelth, Bivorn, Tessik, Aurren, Feyth, Gorran, Lissel, Nahren, Pyreth, Sarvik, Torvun, Vessen, Wyndle, Arlox, Crynn, Dakren, Elthis, Fikken, Halvex, Iyren, Jassik

### 6.6 Knowledge Pool (15 entries)

Rare metal deposits, geyser eruption patterns, safe ice paths, old settlement locations, power cell ruins, crystal growth patterns, safe caves, ice weather reading, migration patterns, builder construction, bio-gel pools, subsurface water currents, deep canyon paths, edible organisms, trade routes.

### 6.7 Materials Pool (8)

ice_crystal, metal_shard, bio_gel, circuit_board, power_cell, thermal_paste, hull_patch, antenna_array

---

## 7. Drone Companion (`src/drone.py`)

```python
@dataclass
class Drone:
    scanner_range: int = 10         # km
    translation_quality: str = "low" # low → medium → high
    cargo_capacity: int = 10
    cargo_used: int = 0
    speed_boost: int = 0            # km/h
    battery: float = 100.0          # percentage
    battery_max: float = 100.0
    upgrades_installed: list[str]
```

### 7.1 Costs

| Action | Battery Cost |
|--------|-------------|
| Scan | 10% |
| Travel | 0.5% per km |
| Suit Repair | 1% per 2% suit restored |

### 7.2 Upgrades (5)

| Upgrade | Effect |
|---------|--------|
| range_module | +10 km scanner range |
| translator_chip | Translation quality: low → medium → high |
| cargo_rack | +5 cargo slots |
| thruster_pack | +5 km/h travel speed |
| battery_cell | +25% battery max (also adds charge) |

### 7.3 Speech System

Two voice modes:
- **`speak(message)`** — Visible drone commentary: `[bold magenta]DRONE:[/bold magenta] message`
- **`whisper(message)`** — Private to player: `  [dim magenta]< DRONE >[/dim magenta] message`

### 7.4 Travel Musings

Pool of 15 pre-written observations. Selected via `get_travel_musing(rng)`. Returns `None` if battery is 0.

### 7.5 Interaction Coaching

`get_interaction_advice(creature, rng)` selects from:
- **DRONE_ARCHETYPE_TIPS:** 3 tips per archetype (24 total)
- **DRONE_TRUST_TIPS:** 3 tips per trust level (9 total)
- **DRONE_DISPOSITION_TIPS:** 1-2 tips per disposition (3 total)

Returns `None` if battery is 0.

### 7.6 Translation Framing

`get_translation_frame(rng)` selects flavor text per quality level:
- **Low:** 3 options (e.g., "Signal noisy... reconstructing meaning...")
- **Medium:** 3 options (e.g., "Translation mostly clear. A few gaps.")
- **High:** 2 options (e.g., "Clear signal. Translation is clean.")

### 7.7 Recharge

Battery fully restores when player visits Crash Site.

---

## 8. ARIA Ship AI (`src/ship_ai.py`)

### 8.1 Voice Format

`[bold bright_white]ARIA:[/bold bright_white] message`

### 8.2 Resource Warning Thresholds

All four resource types use `THRESHOLDS = [50, 30, 15, 5]`. Each threshold fires once until the resource is replenished (`reset_warnings()`).

| Resource | 50% Warning | 30% Warning | 15% Warning | 5% Warning |
|----------|------------|------------|------------|-----------|
| Food | "dropped below 50%" | "Nutritional reserves at 30%" | "Food reserves critical" | "you are starving" |
| Water | "below 50%" | "Water at 30%" | "Water reserves critical" | "severely dehydrated" |
| Suit | "dropping below 50%" | "Thermal regulation degrading" | "Exposure risk climbing" | "barely holding" |
| Battery | "below 50%" | "Battery at 30%" | "Battery critical" | "barely maintain sensor contact" |

### 8.3 Post-Travel Summary

Shows: location name, food%, water%, suit%, battery% after each travel.

### 8.4 Objective Reminder

Every 10 commands, shows repair progress (e.g., "Repair progress: 2/5").

---

## 9. Travel System (`src/travel.py`)

### 9.1 Travel Formula

```
base_speed = 10.0 km/h
actual_speed = base_speed + drone.speed_boost
travel_time = distance / actual_speed  (hours)
```

### 9.2 Resource Costs Per Trip

| Resource | Formula |
|----------|---------|
| Food | `hours * 2.0%` |
| Water | `hours * 3.0%` |
| Suit | `hours * 0.5%` |
| Battery | `distance * 0.5%` |

### 9.3 Travel Animation

Real-time progress bar: `min(hours * 0.3, 3.0)` seconds, 20 steps.

### 9.4 Travel Narration

Events scale with trip length: `min(5, max(1, hours // 2))` events per trip.

**Event pools:**

| Pool | Count | Type | Source |
|------|-------|------|--------|
| TRAVEL_EVENTS | 12 | World observations | travel.py |
| ATMOSPHERE_EVENTS | 15 | Sensory details | travel.py |
| WEATHER_UPDATES | 8 | Environmental data | travel.py (via ARIA) |
| DRONE_TRAVEL_MUSINGS | 15 | Companion commentary | prompts.py (via Drone) |

Max 2 events of the same type per trip. Events shuffled and interleaved with `...` separators.

### 9.5 Item Discovery

15% chance per trip to find ice_crystal or metal_shard.

### 9.6 Route Suggestion

On trips >= 3 hours, drone suggests closer alternative locations within 15 km of destination.

### 9.7 Screen Behavior

Screen clears before travel. On arrival, player is prompted to `look`.

---

## 10. LLM System (`src/llm.py`)

### 10.1 GPU Detection

`detect_gpu()` checks for GPU offload support via:
1. `llama_cpp.llama_supports_gpu_offload()`
2. `llama_cpp.LLAMA_SUPPORTS_GPU_OFFLOAD`
3. Backend-specific constants (GGML_USE_CUDA, GGML_USE_METAL, GGML_USE_VULKAN)

Returns `{"available": bool, "backend": str}`.

### 10.2 Model Loading

```python
load_model(callback=None, gpu_mode="cpu")
```

| Parameter | CPU Mode | GPU Mode |
|-----------|----------|----------|
| n_ctx | 4096 | 4096 |
| n_threads | 4 | 4 |
| n_gpu_layers | 0 | -1 (all layers) |
| verbose | False | False |

If GPU loading fails, automatically retries with CPU.

### 10.3 Model Search Path

1. Any `.gguf` in `models/` directory
2. `models/gemma-4-E2B-it-Q4_K_M.gguf`
3. `D:/projects/moon_traveler/models/gemma-4-E2B-it-Q4_K_M.gguf`

### 10.4 Response Generation

```python
generate_response(creature, player_message, translation_quality="low")
```

| Parameter | Value |
|-----------|-------|
| max_tokens | 200 |
| temperature | 0.8 |
| top_p | 0.9 |
| stop sequences | "Human:", "Player:", "\n\n\n" |
| context window | Last 10 messages from conversation_history |

### 10.5 System Prompt Structure

```
You are {name}, a {species} on Enceladus.
You are a {archetype} by nature. {personality_detail}
{disposition_instruction}
Knowledge: {knowledge_list}
Rules: stay in character, 2-4 sentences, no AI breaking
{trust_instruction}
{translation_quality_modifier}
```

### 10.6 Translation Quality Modifiers

| Level | LLM Instruction |
|-------|----------------|
| Low | Replace 1-2 words/sentence with garbled nonsense (zrrk, vvmm, kktch, bzzl) |
| Medium | Occasional unusual word choice suggesting imperfect translation |
| High | (no modification) |

### 10.7 Fallback Responses

5 pre-written responses per archetype (40 total). Used when LLM unavailable, loading, or generation fails.

---

## 11. Commands (`src/commands.py`)

### 11.1 Command Table

| Command | Aliases | Description |
|---------|---------|-------------|
| look | l | Describe current location |
| scan | — | Use drone to discover nearby locations (costs 10% battery) |
| gps | map | Show known locations with distances |
| travel | go | Travel to a known location |
| take | get, pick | Pick up an item |
| inventory | inv, i | Show inventory |
| talk | speak | Talk to creature at location (LLM chat) |
| give | — | Give item to creature (trust +10/+15) |
| drone | — | Show drone status panel |
| upgrade | — | Install drone upgrade from inventory |
| status | — | Show food/water/suit/repair progress |
| ship | repair | Interactive repair at Crash Site |
| save | — | Save game to named slot (default: "manual") |
| load | — | Load game from slot |
| dev | devmode | Toggle developer diagnostics panel |
| help | — | Show command list |
| quit | exit | Quit game (with confirmation) |

### 11.2 Conversation System (cmd_talk)

1. Validates creature at location
2. Hostile + trust <15 → chases player away
3. Opens ARIA Communicator with header showing creature info
4. **Drone initial coaching:** whispers archetype-based tip
5. **Chat loop:**
   - Player input (no `/` prefix) → sent as dialogue
   - `/end`, `bye` → exit conversation
   - `/?`, `/help` → show chat help
   - `/<command>` → execute game command mid-conversation
6. **Per exchange:**
   - Message added to creature's conversation_history
   - LLM generates response
   - Translation frame shown (always on 1st exchange, 40% after)
   - Creature response displayed
   - Trust +3
   - Drone may whisper advice (probability varies: 80% first, 60% hostile+low, 40% low, 30% medium, 15% high)
   - High trust reveals: food/water sources, materials
7. Post-conversation ARIA trust commentary

**Key design:** Drone whispers are printed to console but NEVER added to `creature.conversation_history`. The LLM never sees drone advice.

### 11.3 Ship Repair (cmd_ship)

At Crash Site:
1. Shows repair checklist table
2. Lists installable materials from inventory → prompts to install
3. Offers suit repair using drone battery (if suit <100% and battery >=10%)

Away from Crash Site:
- Shows checklist only with hint to return

---

## 12. UI System (`src/ui.py`)

### 12.1 Display Functions

| Function | Purpose |
|----------|---------|
| `show_title()` | ASCII art title banner (cyan) |
| `show_crash()` | Crashed ship ASCII art (yellow) |
| `narrate(text, style, delay)` | Character-by-character animation (default 0.02s/char) |
| `narrate_lines(lines, style, pause)` | Line-by-line with pauses (default 0.5s) |
| `info(text)` | Cyan text |
| `warn(text)` | Yellow text |
| `error(text)` | Red text |
| `success(text)` | Green text |
| `dim(text)` | Dimmed text |
| `show_panel(title, content, style)` | Rich panel |
| `show_location(...)` | Location info panel with items and creatures |
| `show_inventory(items)` | Table of items with quantities |
| `show_gps(locations, x, y)` | Location table with distances |
| `show_status(...)` | Status table: food, water, suit, time, repair progress |
| `show_drone_status(drone_dict)` | Drone stats panel (magenta border) |
| `show_ship_repair(checklist)` | Repair progress table |
| `creature_speak(name, text, color)` | Creature dialogue line |
| `drone_speak(text)` | Drone speech (bold magenta) |
| `drone_whisper(text)` | Private drone message (dim magenta italic) |
| `travel_progress(dest, duration)` | Progress bar with spinner |
| `loading_spinner(msg, duration)` | Transient spinner |
| `prompt_choice(text, choices)` | Numbered selection menu |

### 12.2 Color System

20-color creature palette: green, magenta, yellow, cyan, bright_red, bright_green, bright_magenta, bright_cyan, bright_yellow, dark_orange, deep_pink4, spring_green3, steel_blue1, orchid, turquoise2, salmon1, chartreuse3, medium_purple1, hot_pink, dark_sea_green.

### 12.3 Status Colors

| Resource | Green | Yellow | Red |
|----------|-------|--------|-----|
| Food/Water | >50% | 20-50% | <20% |
| Suit | >60% | 30-60% | <30% |
| Battery | >50% | 20-50% | <20% |

---

## 13. Tutorial System (`src/tutorial.py`)

### 13.1 Tutorial Steps

```
NOT_STARTED → BOOT_SEQUENCE → PROMPT_LOOK → PROMPT_SCAN →
PROMPT_GPS → PROMPT_TRAVEL → PROMPT_TALK → COMPLETED
```

### 13.2 Step Triggers

| Step | Trigger Commands | Next Hint |
|------|-----------------|-----------|
| PROMPT_LOOK | look, l | "Now use scan to discover nearby locations." |
| PROMPT_SCAN | scan | "Use gps to review mapped locations." |
| PROMPT_GPS | gps, map | "Travel to the nearest location." |
| PROMPT_TRAVEL | travel, go | "If there's a life form, try talk." |
| PROMPT_TALK | talk, speak | "You're on your own now, Commander." |

Non-blocking: wrong commands don't nag.

### 13.3 Boot Sequence

1. Title screen + crash art
2. `ARIA SYSTEM v4.2.1 — INITIALIZING`
3. Ship Diagnostics: hull 23%, life support degraded, propulsion/nav/comms offline, power backup
4. Environment Scan: temp -201C, gravity 0.0113g, atmosphere trace, radiation low
5. Crew Vitals: food%, water%, suit%
6. Repair Assessment: components needed, components found, repair class
7. Drone deployment: `"Deploying ARIA Scout Drone..."`
8. `CONNECTION ESTABLISHED`
9. Drone intro: `"Online and operational. I'll handle translation, scanning, and keeping you alive out there."`
10. ARIA opening lines + tutorial hint

---

## 14. Save System (`src/save_load.py`)

### 14.1 Storage

- Directory: `saves/`
- Format: JSON files named `{slot}.json`
- Save version: 2

### 14.2 Saved State

```json
{
  "save_version": 2,
  "player": { ... },
  "drone": { ... },
  "locations": [ ... ],
  "creatures": [ ... ],
  "world_seed": int,
  "world_mode": "short|medium|long",
  "repair_checklist": { ... },
  "ship_ai": { ... },
  "tutorial": { ... }
}
```

### 14.3 Auto-save

Triggered after every travel and conversation end. Slot: `"autosave"`.

### 14.4 Backwards Compatibility

- v1 saves: missing `ship_ai` and `tutorial` → created with defaults
- New Player fields: `suit_integrity` defaults to 92.0 for old saves

---

## 15. Input Handler (`src/input_handler.py`)

### 15.1 Autocomplete

Context-aware completions via prompt_toolkit:

| Command | Completes To |
|---------|-------------|
| (empty) | All 23 base commands |
| travel / go | Known location names |
| talk / speak | Creature at current location |
| take / get / pick | Items at current location |
| give | Inventory items → "to" → creature name |
| upgrade | Upgrade items in inventory |
| load | Available save slot names |

### 15.2 Prompt Style

```
{location_name} >
```

Location in bold cyan, prompt in bold.

---

## 16. Developer Mode (`src/dev_mode.py`)

Session-only (not saved). Toggle with `dev` command.

### 16.1 Panel Contents

- System: RAM (RSS via psutil), CPU%
- Game: mode, seed, location, food/water%, hours, inventory count
- World: known/total locations, drone battery
- Creatures: name, disposition tag (F/N/H), trust/100, helped-repair marker (*)
- Repair: done/total
- Tutorial: current step name
- LLM: loaded/unavailable

---

## 17. LLM Prompts (`src/data/prompts.py`)

### 17.1 Constants

| Constant | Type | Entries |
|----------|------|---------|
| BASE_CREATURE_PROMPT | str template | 1 |
| PERSONALITY_DETAILS | dict[archetype → str] | 8 |
| DISPOSITION_INSTRUCTIONS | dict[disposition → str] | 3 |
| TRUST_INSTRUCTIONS | dict[trust_level → str] | 3 |
| TRANSLATION_QUALITY | dict[quality → str] | 3 |
| FALLBACK_RESPONSES | dict[archetype → list[str]] | 8 archetypes x 5 responses |
| DRONE_TRAVEL_MUSINGS | list[str] | 15 |
| DRONE_ARCHETYPE_TIPS | dict[archetype → list[str]] | 8 x 3 = 24 |
| DRONE_TRUST_TIPS | dict[trust_level → list[str]] | 3 x 3 = 9 |
| DRONE_DISPOSITION_TIPS | dict[disposition → list[str]] | 3 total |
| DRONE_TRANSLATION_FRAMES | dict[quality → list[str]] | 8 total |

---

## 18. Build & Release (`scripts/build_release.py`)

### 18.1 Usage

```bash
python scripts/build_release.py [--platform windows|macos|linux|all] [--no-archive]
```

### 18.2 Build Process

1. Detect platform (or use specified)
2. Check/install PyInstaller
3. Build with `--onedir --console`
4. Include `src/` as `--add-data`
5. Hidden imports: rich, prompt_toolkit, psutil
6. Create empty `models/` and `saves/` directories in output
7. Create `PLACE_MODEL_HERE.txt` in models/
8. Archive: `.zip` for Windows, `.tar.gz` for macOS/Linux

### 18.3 Output

```
dist/
  moon-traveler-cli-{platform}/
    moon-traveler-cli/
      moon-traveler-cli[.exe]
      models/
      saves/
```

### 18.4 Cross-Compilation

Not supported. Must build on each target platform.

---

## 19. Win/Lose Conditions

### 19.1 Win

All entries in `repair_checklist` are `True` (all materials installed at Crash Site).

**Win sequence:** Narrative about ship repair, thrusters igniting, rising from Enceladus. Shows survival time. "MISSION COMPLETE".

### 19.2 Lose

`player.food <= 0 AND player.water <= 0`

**Lose sequence:** Narrative about exhaustion and collapse. Shows survival time. "GAME OVER".

---

## 20. File Manifest

```
play.py                    Entry point (12 lines)
pyproject.toml             Project config, dependencies
requirements.txt           Minimal pip requirements
README.md                  User-facing documentation
CHANGELOG.md               Version history
spec.md                    This document
scripts/
  build_release.py         Cross-platform build script
src/
  __init__.py              Package marker
  __main__.py              Module entry point
  game.py                  Main loop, init, win/lose, GPU prompt
  world.py                 World generation, Location dataclass
  player.py                Player dataclass, resource management
  creatures.py             Creature dataclass, trust, generation
  drone.py                 Drone dataclass, speech, advice, upgrades
  travel.py                Travel mechanics, narration, events
  commands.py              Command registry, handlers, chat system
  llm.py                   LLM loading, GPU detection, generation
  ship_ai.py               ARIA warnings, summaries, reminders
  ui.py                    Rich console output, panels, animations
  tutorial.py              Boot sequence, tutorial progression
  save_load.py             JSON save/load, versioning
  input_handler.py         prompt_toolkit autocomplete
  dev_mode.py              Developer diagnostics panel
  data/
    __init__.py             Package marker
    names.py                Name pools (28 prefixes, 20 species, 30 creature names)
    prompts.py              LLM prompts, fallbacks, drone message pools
tests/
  __init__.py               Package marker
  test_ship_ai.py           ARIA warnings, summary, serialization (16 tests)
  test_tutorial.py          Tutorial progression, serialization (13 tests)
  test_dev_mode.py          Dev panel toggle, system metrics (5 tests)
  test_input_handler.py     Autocomplete for all command types (11 tests)
```

**Total test count:** 45
