# Changelog

All notable changes to Moon Traveler CLI will be documented in this file.

## [0.3.1] - 2026-04-16

### Fixed
- Fixed crash when talking to NPCs caused by prompt_toolkit session conflict
- Fixed GPU Metal segfault on macOS — auto-detects compute mode from config, no startup prompt
- Sound effects no longer write to stdout (was corrupting Rich console terminal state)

### Added
- **Sound effects** — beep patterns for game events, spoken voice announcements via Voice Module drone upgrade
- **Drone upgrades**: Voice Module (spoken announcements) and Autopilot Chip (auto-look/scan on arrival)
- **`sound` command** — toggle sound effects on/off
- **`config gpu auto|gpu|cpu`** — configure compute mode without restart prompt
- **`tutorial` command** — replay the ARIA boot sequence and tutorial at any time
- Tutorial auto-skips on subsequent launches (persisted in `~/.moonwalker/config.json`)
- GPU smoke test during model load — catches inference failures before gameplay starts

### Changed
- Removed GPU/CPU selection prompt at startup — auto-detects or reads from config
- Removed "Skip tutorial?" prompt — tutorial runs once automatically, then skips
- All user data defaults to `~/.moonwalker/` (saves, models, config, dev logs)

## [0.3.0] - 2026-04-16

### Added

**Creature-Centric Redesign**
- Creatures are now the primary source of repair materials and survival resources
- 10 archetypes (added Merchant and Enforcer) with role-based capabilities
- `ROLE_CAPABILITIES` system: each archetype has specific trust thresholds for what they provide
- Healers heal at trust 0, Builders share at 35, Guardians at 70, Hermits at 80
- Guaranteed spawns: every game has at least 1 Merchant, 1 Builder, 1 Healer
- Material coverage guarantee: every required repair material exists on at least one creature
- Creature backstories generated from family, concern, and opinion pools
- Natural conversation prompts: creatures feel like real people with lives and communities

**Merchant & Trade System**
- Merchant archetype: trades item-for-item, never gives free
- `trade` command with interactive menu (pick item to receive + item to give)
- `[TRADE:offered:wanted]` LLM action tag for in-conversation trades
- Trust-gated: 20+ to trade, 50+ for repair materials, 70+ for bonus items
- Fallback trade menu when LLM is unavailable

**Enforcer Archetype**
- Authority figure who advises which creatures can help with ship repairs
- Knows everyone in the area, methodical and fair
- Provides creature intel at trust 15, materials at trust 60

**Hostile Environment**
- 6 hazardous travel events: geyser eruptions, crevasse falls, ice storms, thin ice collapse, toxic vents, thermal shocks
- Mechanical effects: suit damage, food/water loss, time delays
- Hazard probability scales with trip length (1 roll per 2 hours, max 3)
- Actionable ARIA feedback: suggests medical bay, Healers, or kitchen after damage

**Late-Game Weather Escalation**
- After threshold (30h short, 40h medium, 60h long), weather deteriorates
- Hazard probabilities increase +5% per 10 hours past threshold
- Extra water drain during travel in late game
- Dramatic weather narration during travel

**AI-Powered Drone Hints**
- `get_smart_advice()` replaces static tip pools with context-aware suggestions
- LLM secondary call for specific question recommendations
- Smart template fallback: knows what each creature has, what player needs, trust gaps
- Archetype-specific coaching: "This Healer can help even at low trust"

**UI Improvements**
- Skip tutorial option for returning players (with context before the prompt)
- Tutorial completion now mentions give, trade, escort, and ship commands
- GPS shows food/water resource markers (visit-gated) with Resources column
- Inventory count in status bar (`Inv 7/10`)
- Food and water bars always visible in exploring status bar (was hidden above 50%)
- Stash all option in storage bay
- Per-companion escort dismiss (choose which follower to release)
- Trust tier label consistency ("max trust" everywhere)

**Dev Mode**
- Logs to JSON file (`logs/dev_diagnostics.jsonl`) instead of printing to screen
- Debug logging across all key actions: commands, travel, trust changes, trades, scans, saves, repairs
- Full RAM breakdown: RSS, VMS, system RAM, LLM model estimate
- Never crashes the game (all logging wrapped in try/except)

### Fixed
- Followers now visible to `talk`, `give`, and `look` commands during escort
- Autocomplete suggests follower names for `talk` and `give`
- Material duplication: `can_give_materials` synced with `role_inventory` on all code paths
- Double-remove ValueError when legacy `can_give_materials` was used as primary inventory
- `save_game` wrapped in try/except: disk full no longer crashes the game
- ARIA post-travel summary shows actual resource costs (not static estimates)
- Travel danger estimate accounts for late-game extra water drain
- Late-game water drain uses pre-trip hours (not post-consume_resources hours)
- `HEAL` action resets food/water warning flags so ARIA re-warns after healing
- ShipAI `from_dict` merges loaded warnings into defaults (prevents KeyError on old saves)
- `_ensure_guaranteed_archetypes` handles edge case with fewer creatures than guaranteed slots
- `_ensure_material_coverage` prevents duplicate materials in role_inventory
- Dev mode log path resolved relative to project root (not CWD)
- Removed dead code: `narrate()`, `drone_speak()`, `drone_whisper()` from ui.py

### Changed
- World item drops reduced: creatures are primary resource source, locations provide 0-1 survival items
- `cmd_give` no longer auto-dumps materials at trust 70 (materials come through conversation)
- `LOCATION_ITEMS` simplified: only survival items (ice_crystal, bio_gel, metal_shard) at most locations
- Action tags are now role-aware: LLM only sees actions the archetype can perform
- Creature prompts rewritten for natural, humane conversation
- Hostile creatures are verbally aggressive but not violent — protecting their community
- SAVE_VERSION bumped to 4

**Testing**
- 195 tests (up from 170): new tests for role-based trust, trade actions, guaranteed spawns, material coverage, hazard events, dev mode logging

## [0.2.0] - 2026-04-16

### Added

**Ship Bays** (at Crash Site)
- Repair Bay: install repair materials interactively
- Storage Bay: stash/retrieve items to free drone cargo
- Kitchen Bay: cook bio_gel into food (+40%) or ice_crystal into water (+40%)
- Charging Bay: recharge drone or overcharge with Power Cell (+10% max)
- Medical Bay: suit repair and rest recovery

**Creature Actions in Conversation**
- NPCs can give water, food, materials, healing, and suit repair via LLM action tags
- Trust-gated: low trust blocks all actions, medium allows food/water, high allows everything
- Action tags stripped from displayed text — player sees natural dialogue

**Escort System**
- Ask creatures with trust 50+ to follow you (`escort` command)
- Companions move with you during travel, shown in status bar
- At Crash Site: Healers restore vitals, Builders install materials, all donate resources
- Send companions home or keep them after helping

**Status Bar**
- Full vitals (food, water, suit, battery, ship progress) at Crash Site with bay summary
- Minimal bar (suit, battery, time) when exploring — food/water appear when below 50%
- Creature info line with trust bar when NPC is present
- Follower line when escorting creatures

**Drone Vitals Whisper**
- Drone whispers status updates at every 10% resource drop while exploring
- Yellow warnings at 30%, red critical alerts at 10%
- Resets tracking when returning to Crash Site

**Model Selection**
- Default model changed to Qwen3.5 2B (1.3 GB, ~2.3 GB RAM)
- Gemma 4 E2B remains as optional full-quality model (3.1 GB, ~4.4 GB RAM)
- First-run model selection menu with system info (platform, RAM, GPU)
- Low RAM detection recommends lite model

**Save System**
- Migrated from JSON files to SQLite key-value database
- Chat history stored in dedicated table — NPCs remember conversations across saves
- Configurable save path (first-run prompt, `config` command)
- Backwards compatible with legacy JSON saves
- Silent auto-save (no UI noise)

**UX Improvements**
- `rest` command: recover food/water anywhere (+10%, or +20% at Crash Site)
- Travel confirmation for trips >=3 hours with estimated resource cost
- Dangerous trip warning when resources would drop below 10%
- Inventory items tagged as repair/upgrade/cookable
- Help text includes win condition and survival info
- Trust feedback during conversations (+3 per exchange with tier progress)
- Gift trust feedback shows distance to next tier
- Cooking repair materials triggers a warning
- Hostile creature take-block includes resolution hint
- Picking up repair materials shows "needed for ship repair" hint
- `/history` command in conversations to review chat log
- ARIA post-travel summary shows resource deltas
- `clear`/`cls` command to clear screen
- `config` command to view/change save directory

**World Generation**
- Rewritten as chain-growth algorithm (all locations reachable by scanning)
- Scan capped at 3 closest discoveries per scan
- Cluster limit prevents overcrowding

**Win Sequence**
- Ship launch ASCII art animation
- Personalized creature recognition naming allies who helped

**Dev Mode**
- Location table with coords, distances, items, creatures, food/water markers
- Scan reachability tree (2-depth)
- Chat history panels for all creatures spoken to

**CI/CD**
- GitHub Actions: CI (tests + lint on PR) and Release (cross-platform builds on tag)
- Build script reads version from pyproject.toml, generates SHA-256 checksums
- Missing hidden imports added for PyInstaller

**Testing**
- 170 tests (up from 45): player, creatures, drone, LLM actions, world gen, game, save/load, travel

**Assets**
- 19 auto-generated SVG screenshots via Rich export
- Hand-crafted banner, icon, archetype guide, map visualization, splash

### Fixed
- Lose condition: changed from AND to OR (can now die from dehydration or starvation alone)
- Suit integrity=0 is now a lose condition (was cosmetic-only despite fatal ARIA warnings)
- Duplicate LLM message: player input was sent twice to the model
- creature_at_location: followers no longer shadow resident creatures
- Auto-repair bypassing interactive ship command removed
- cargo_used never updated in drone status display
- Creature-revealed locations now set loc.discovered=True
- ARIA warnings reset after kitchen/medical/charging bay use
- Action tag regex now requires colon for GIVE_MATERIAL (prevents silent misparse)
- cmd_give clears can_give_materials after donation (prevents LLM re-delivery)
- Companion help at ship is one-time only (no infinite healing exploit)
- Rest command consumes 1 hour of resources before applying bonus (no infinite survival)
- RNG reseeded with time on load (prevents savescumming)
- from_dict on all dataclasses strips unknown keys (forward compatibility)
- llama_cpp import catches FileNotFoundError for PyInstaller builds
- requirements.txt synced with pyproject.toml
- Phantom dependencies (diskcache, numpy) removed
- Auto-save is silent
- Save version key matches spec ("save_version" not "version")

### Changed
- Default model: Qwen3.5 2B (was Gemma 4 E2B)
- System requirements: 4 GB RAM recommended (was 6 GB)

## [0.1.0] - 2026-04-15

### Added

**Core Game**
- Procedural world generation with seeded RNG (Short/Medium/Long modes)
- Player survival system: food, water, suit integrity meters
- 8 creature archetypes (Wise Elder, Trickster, Guardian, Healer, Builder, Wanderer, Hermit, Warrior)
- 3 creature dispositions (friendly, neutral, hostile) with trust system (0-100)
- Ship repair checklist with materials and creature helper requirements
- Win condition (all repairs complete) and lose condition (starvation/dehydration)
- Save/load system with auto-save and manual named slots
- Developer diagnostics panel (`dev` command)

**Drone Companion**
- Scout drone with battery, scanner, cargo, and speed boost stats
- Drone speech system with distinct voice (`DRONE:` in magenta)
- Travel musings: drone comments during journeys with observations and tips
- Translation framing: visible translation quality indicators during creature dialogue
- Private coaching channel: drone whispers interaction advice only the player can see
- Coaching adapts to creature archetype, disposition, and trust level
- Drone goes silent when battery is depleted
- 5 upgrade types: range module, translator chip, cargo rack, thruster pack, battery cell

**Suit Integrity**
- Suit starts at 92% (damaged from crash landing)
- Degrades 0.5% per hour of travel
- Displayed in status command, post-travel summary, and boot diagnostics
- ARIA warns at 50%, 30%, 15%, 5% thresholds

**GPU/CPU Mode Selection**
- Auto-detects GPU availability (CUDA/Metal/Vulkan) at startup
- User can choose between "CPU + GPU" and "CPU Only" modes
- Automatic CPU fallback if GPU loading fails

**LLM Integration**
- Local LLM inference via llama-cpp-python (Gemma 4 E2B GGUF)
- Context-aware creature dialogue with personality, disposition, trust, and translation quality
- Pre-written fallback responses when LLM is unavailable
- Drone message pools (pool-based, no LLM required)

**Travel System**
- Distance-based travel time with drone speed boost
- Screen clears on departure for immersion
- Scaled narration: environmental events, atmospheric details, drone musings
- Resource depletion during travel (food, water, suit, battery)
- Item discovery chance (15%) during travel
- Route suggestions on longer trips
- Arrival prompt to look around

**UI**
- Rich terminal interface with styled text, panels, and tables
- ASCII art title screen and crash site illustration
- Character-by-character narrative animation
- Travel progress bar
- Drone speech (`DRONE:`) and private whisper (`< DRONE >`) formatting
- Color-coded creature names and status indicators
- Autocomplete for commands, locations, creatures, and items

**ARIA Ship AI**
- Status warnings for food, water, suit integrity, and drone battery
- Post-travel resource summaries
- Periodic objective reminders
- Boot sequence with system diagnostics

**Documentation**
- README with installation, usage, and gameplay guide
- CLAUDE.md consolidated spec document
- CHANGELOG tracking all features

**Ship Repair System**
- Repair checklist is materials-only (no creature helper requirements)
- Interactive `ship` command at Crash Site: install materials and repair suit
- Suit repair uses drone battery (2% suit per 1% battery)

**Build & Release**
- Cross-platform build script for Windows, macOS, and Linux (PyInstaller)
