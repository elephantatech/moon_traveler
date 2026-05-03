# Changelog

All notable changes to Moon Traveler CLI will be documented in this file.

## [0.5.3] - 2026-05-02

### Fixed

- **Windows freeze fix** — `_create_llama()` wrapper prevents llama-cpp-python's `suppress_stdout_stderr` from killing Textual's WriterThread by redirecting only stderr (fd 2), not stdout (fd 1)
- **Bridge deadlock fix** — replaced all `call_from_thread` with heartbeat-drained `_bridge_queue` pattern. Textual's `call_from_thread` deadlocked on Windows ProactorEventLoop when the main thread was busy
- **Boot sequence hang** — narrative intro no longer freezes on Windows/Linux during rapid `ui.console.print()` calls
- **Animation deadlock** — `animate_frame()` uses fire-and-forget queue instead of blocking cross-thread call
- **Windows UTF-8 fix** — `stdout`/`stderr` reconfigured to `utf-8` with `errors="replace"` on startup

### Changed

- **Sound system rewrite** — replaced platform-specific beep patterns with `chime` library (bundled `.wav` files, cross-platform). macOS voice mode via `say` preserved
- **Logging consolidated** — single log file `~/.moonwalker/dev/game.log` replaces separate `startup.log` + `dev_diagnostics.jsonl`. All modules use Python `logging`
- **Silent failure audit** — 29 bare `except: pass` replaced with `logger.debug(exc_info=True)` across 11 files. Visible in `game.log` with `--dev`
- **Debug logging** — `_setup_logging()` configures file + stderr handlers when `--dev` active. All game stages logged: startup, mode selection, LLM loading, boot sequence, game loop

### Added

- **Model switching** — `model` command now shows installed models and download options. Selected model is persisted in `config.json`. Manually placed `.gguf` files appear in the menu automatically
- **`chime` dependency** — cross-platform sound effects via bundled `.wav` files
- **`_create_llama()` wrapper** — safe model loading that preserves stdout for Textual
- **Heartbeat timer** — 30 FPS timer drains `_bridge_queue` on the main thread, replacing `call_from_thread`/`call_soon_threadsafe`

## [0.5.2] - 2026-04-22

### Added

- **ASCII animation system** — dedicated `#animation-bar` widget with in-place 2-line sprites for scan, travel, look, drone, hazard, exchange, and model loading (#29)
- **Drone sprite evolution** — drone ASCII art evolves with upgrades: eyes `o`→`O`, belly fills with `[]` per upgrade
- **In-place upgrade system** — `update` command + `--upgrade` flag checks GitHub Releases API and downloads updates safely (#49)
- **Model download progress bars** — 10% interval progress during model download + `model` command to switch models (#54)
- **LLM performance diagnostics** — `_timed_inference()` wrapper logs timing, token count, and RSS memory delta in dev mode (#9)
- **CI test matrix** — 3 OS (ubuntu, windows, macos) × 2 Python (3.11, 3.12) = 6 parallel test jobs (#25)
- **Test coverage reporting** — `pytest-cov` integrated into CI pipeline (#26)
- **`--disable-animation` CLI flag** — disables animations for the session without affecting `--super` mode
- **Late-game animation variants** — intensified scan and hazard sprites after 24 hours elapsed
- **Release announcement pages** — individual HTML pages for every version (v0.2.0–v0.5.2) + releases index
- **Shared release CSS** — `release-style.css` for consistent design across release pages

### Fixed

- Drone sprite alignment — top and bottom lines now consistently 13 characters
- `[o]` in drone sprite no longer eaten by Rich markup (escaped `\[`)
- `animations` import moved before `initial_tip` check in `cmd_talk` (was causing NameError)
- `beat()` only fires after valid command dispatch (not on invalid commands)
- `--super` no longer disables animations
- `cmd_model` wrapped in try/except for graceful error handling
- Bare `except` on `model_loading` narrowed to `ImportError`
- Download size verification added to upgrade system
- Windows path traversal protection via `os.path.normpath` + `os.sep` split

## [0.5.1] - 2026-04-20

### Added

- **Drone scan report** — plays every session with live data (suit %, food %, surface temp)
- **Flight recorder narrative** — crash-landing story sets the stakes before gameplay
- **Screenshot pipeline** — captures the intro sequence with validation

## [0.5.0] - 2026-04-18

### Removed

- **CLI mode** — `play.py` deleted; `play_tui.py` is now the sole entry point
- **prompt_toolkit** dependency removed (GameCompleter, bottom toolbar, CLI input handler)
- All CLI fallback paths in `ui.py`, `game.py`, `commands.py` stripped
- Renamed package `moon-traveler-cli` → `moon-traveler`

### Changed

- **Drone subcommands** — `drone status`, `drone upgrade <part>`, `drone charge` (upgrade/charge still work as top-level shortcuts)
- **Help text reorganized** — categorized sections (Navigation, Items, Creatures, Drone, Player, Ship, System)
- **Ship bays context-aware** — ship sub-commands shown in help only at Crash Site
- **Rest consistency** — medical bay rest now uses same location-based recovery as standalone rest (+10% away, +20% at ship)
- Added `[build-system]` and `[project.scripts]` to pyproject.toml — `moon-traveler` command available after `pip install`

### Added

- **Escort requirement for ship repair** — Easy=1, Medium=2, Hard=3, Brutal=4 creatures must help at the ship before final repairs (#28)
- **Local leaderboard** — scores saved to SQLite after every win/lose; `scores` command shows top 10 (#45)
- **Session stats tracker** — tracks commands, km traveled, creatures talked, hazards, trades, gifts, items (#7)
- **Post-game score screen** — score (0-1000), letter grade (S-D), ARIA verdict after win/lose (#8)
- **Model checksum verification** — SHA-256 verification on downloaded models (#33)
- **Save file validation** — chat history and creature memory validated on load (#34)
- **Custom model download** — paste a HuggingFace URL to download any GGUF model
- **Pre-commit hooks** — 12 hooks: ruff, markdownlint, shellcheck, yamllint, file hygiene
- **CI pipeline** — 6 jobs: test, lint, markdown, shellcheck, powershell-lint, actionlint
- **Player name** — prompted at game start, creatures address you by name, persisted in save/load, `name` command to change (#50)
- **Drone boot messages** — immersive boot sequence showing model name, variant, context window, inference mode (#2)
- **Responsive status bar** — wraps to 2-3 lines on narrow terminals instead of truncating (#1)
- **Screen clear** — clears mode selection UI before boot sequence for clean startup
- Escort hint shown after talk when trust reaches 50+
- `tutorial`, `screenshot`, `stats`, `scores`, `name` commands visible in help text
- 285 tests (was 240) — integration tests, score calculation, sentinel filtering, player name, autocomplete coverage

### Fixed

- Screenshot command guard for missing bridge
- Autocomplete wiring now logs errors instead of silently swallowing
- Screenshot script victory capture loop handles companion repair prompts
- Closes #23 (unify completers — resolved by CLI removal)

## [0.4.1] - 2026-04-18

### Fixed

- **NPC memory captures full conversation** — memory update now uses the entire current chat session instead of a hardcoded last 6 messages (#35)
- **Game returns to menu after win/lose** — "Play again?" prompt after win/lose, quit exits the app cleanly (#27)
- **Status bar updates during conversations** — trust and vitals now refresh after every NPC exchange (#3)
- **Unicode action tag smuggling** — NFKC normalization applied before regex sanitizer blocks fullwidth character bypass (#32)
- **Memory poisoning defense** — `_sanitize_memory()` strips instruction-like patterns from LLM-generated creature memory (#31)
- **Crash site auto-recharge removed** — drone no longer auto-recharges on arrival at crash site; must use `ship charging` bay manually
- **Play-again loop refactored** — replaced recursive `main()` calls with iterative loop; LLM model not reloaded on play-again
- **Easter egg guard** — easter egg check no longer fires on "Back" button with empty inventory
- **UIBridge timeout safety** — ask-mode enter/exit timeouts now raise or recover instead of silently deadlocking
- **Quit confirmation** — prompt text visible in both game log and input label in TUI mode

### Added

- C4 architecture diagrams (Excalidraw) — System Context, Container, and 5 Component-level diagrams in `docs/diagrams/`
- Section 23 in `spec.md` documenting C4 architecture

## [0.4.0] - 2026-04-17

### Added

- **Textual TUI mode** — `play_tui.py` launches a full terminal UI with fixed status bar, scrollable game log, input with tab-autocomplete and command history (Up/Down arrows), F12 screenshots
- **4 difficulty modes**: Easy (~30 min), Medium (~1-2 hours), Hard (~3+ hours), Brutal (~5+ hours)
- **Brutal mode**: 40 locations, 25 creatures (12 hostile), 1.5x resource drain, +5% hazard bonus, late-game weather at 25h, scarce item drops
- **Difficulty scaling**: trust gain per chat/gift, item find chance, and extra location drops all scale by mode
- **Charge Module drone upgrade**: enables auto-charge (+5% battery/hr during travel), toggled with `charge` command
- **`inspect` command**: examine any item to see what it's used for (repair status, cooking uses, upgrade effects)
- **`charge` command**: toggle auto-charge on/off (requires Charge Module upgrade)
- **`screenshot` command**: save TUI screenshots as SVG files (also F12 hotkey)
- **`--dev` flag**: start with dev mode enabled (`python play_tui.py --dev`)
- **`--super` flag**: start with max trust, all items, full drone upgrades (`python play_tui.py --super`)
- **Junk items**: 10 collectible souvenirs found during travel (baseball, rubber duck, fossilized tooth, etc.)
- **Easter egg**: stash 5+ junk items in ship storage to activate 2x trust multiplier (7 in Brutal mode)
- **Creature junk reactions**: creatures mock you for trying to give them junk, but hint to keep collecting
- **Item descriptions** for all 26 items (8 repair materials, 8 drone upgrades, 10 junk items)
- Up/Down arrow command history in TUI mode
- Tab-cycling through multiple autocomplete candidates
- 36 new tests (195 → 231 total)

### Fixed

- 40+ TUI bugs across 10 review passes (threading races, markup injection, memory leaks, app exit hangs, etc.)
- Trust display now shows actual gain (was hardcoded "+3" regardless of difficulty)
- Auto-charge skipped at crash site (message no longer appears when full recharge supersedes it)
- Super mode checks both inventory and ship storage before adding materials
- Easter egg fires once per session (was re-firing on every stash after threshold)
- Easter egg only fires on stash operations, not retrieve
- Junk items can only be found once (checks both inventory and storage)

### Changed

- Game mode menu: Short/Medium/Long renamed to Easy/Medium/Hard + new Brutal mode
- `_BridgeConsoleShim` routes all console.print/input through Textual when TUI bridge is set
- Worker thread architecture: game logic runs synchronously while Textual UI stays responsive
- All source files linted and formatted with ruff

## [0.3.2] - 2026-04-16

### Added

- **NPC Memory System** — creatures remember facts about the player across conversations (stored as markdown in SQLite)
- **Configurable LLM context size** — `config context 16384` (default 8192, range 2048–131072)
- Guaranteed food/water sources in all world seeds (post-generation pass)
- Auto-save on quit — no more lost progress
- Save version validation on load — warns about incompatible saves

### Fixed

- LLM TRADE action: `given_items` not tracked when item was only in `can_give_materials` — caused ValueError on re-offer
- LLM TRADE action: capacity guard used `<=` instead of `<` — inconsistent with all other guards
- Companion donations could overflow cargo capacity — overflow now goes to ship storage
- LLM GIVE_MATERIAL bypassed cargo capacity check
- Post-travel summary showed `--20` (double-negative) when arriving at food/water source
- Trust hint showed "100 for max trust" when trust was already 100
- Tutorial from_dict crashed on invalid step values from corrupted saves
- Empty LLM response (all action tags, no text) now falls back to `*nods thoughtfully*`
- macOS `say` subprocess had no timeout — added 5s limit

### Changed

- Chat history is now unlimited (no pruning) — creatures remember everything
- LLM receives last 20 messages + structured memory (efficient context usage)
- Drone upgrades spread across more location types for better availability in short mode
- Removed dead ChatCompleter code (110 lines)

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
