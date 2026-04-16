# Changelog

All notable changes to Moon Traveler CLI will be documented in this file.

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
