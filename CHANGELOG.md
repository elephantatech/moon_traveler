# Changelog

All notable changes to Moon Traveler CLI will be documented in this file.

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
- Default model changed to Qwen3.5 2B (1.3 GB, ~2.6 GB RAM)
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
