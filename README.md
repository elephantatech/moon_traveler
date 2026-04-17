# Moon Traveler CLI

<p align="center">
  <img src="assets/banner.svg" alt="Moon Traveler CLI" width="800"/>
</p>

A text-based survival game set on Enceladus, Saturn's icy moon. You've crash-landed and must explore procedurally generated locations, befriend alien creatures through LLM-powered conversations, and gather materials to repair your ship.

<p align="center">
  <img src="assets/screenshot-location-with-creature-and-items.svg" alt="Gameplay" width="700"/>
</p>

## Features

- **Procedural world generation** with seeded RNG and chain-connected locations for replayable maps
- **LLM-powered creature dialogue** using a local AI model (Qwen3.5 2B default, Gemma 4 E2B optional — auto-downloads on first run)
- **Creature-centric gameplay** — creatures are the primary source of repair materials and survival resources, gated by role and trust
- **10 creature archetypes** including Merchant (trades item-for-item) and Enforcer (advises who to talk to)
- **Trade system** — barter with Merchant creatures for repair materials
- **Escort system** — befriend creatures and bring them to your ship for hands-on repair help (per-companion dismiss)
- **AI drone companion** with context-aware hints, alien speech translation, and travel commentary
- **Hostile environment** — hazardous travel events (geyser eruptions, ice storms, crevasse falls) with late-game weather escalation
- **Trust-based relationships** with role-specific thresholds (Healers heal at trust 0, Hermits need trust 80)
- **Ship bays** — Storage (with stash-all), Kitchen, Charging, Medical, and Repair
- **Survival mechanics** tracking food, water, suit integrity, and drone battery
- **Live status bar** showing all vitals, inventory count, ship progress, creature info, and followers
- **GPS with resource markers** showing food/water sources at visited locations
- **Skip tutorial** option for returning players
- **GPU acceleration** with automatic detection and user-selectable CPU/GPU mode
- **Rich terminal UI** with styled text, progress bars, and ASCII art
- **Save/load system** with silent auto-save and manual slots
- **CI/CD pipeline** with GitHub Actions for cross-platform builds

## System Requirements

### Minimum (fallback dialogue, no AI model)

| Resource | Requirement |
|----------|-------------|
| **CPU** | Any modern CPU (x86_64 or ARM64) |
| **RAM** | 256 MB |
| **Disk** | 50 MB (game only) |
| **OS** | Windows 10+, macOS 12+, Linux (glibc 2.31+) |
| **Python** | 3.11+ (not needed for pre-built releases) |

### Recommended — Qwen3.5 2B (default model)

| Resource | Requirement |
|----------|-------------|
| **CPU** | 4+ cores (inference uses 4 threads) |
| **RAM** | 4 GB (game ~50 MB + model ~2.3 GB in memory) |
| **Disk** | 1.5 GB (game 50 MB + model 1.3 GB) |
| **GPU** | Optional — CUDA/Metal/Vulkan for faster inference |

### Full Quality — Gemma 4 E2B (optional)

| Resource | Requirement |
|----------|-------------|
| **RAM** | 6 GB (game ~50 MB + model ~4.4 GB in memory) |
| **Disk** | 3.5 GB (game 50 MB + model 3.1 GB) |
| **GPU** | Optional — 4 GB+ VRAM for full model offload |

> On first launch you choose which model to download. Qwen3.5 2B (1.3 GB) is recommended for most machines. Gemma 4 E2B (3.1 GB) offers slightly richer dialogue. The game also runs without any model using pre-written dialogue.

## Installation

### Quick install (pre-built binary)

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex
```

This downloads the latest release, extracts it, and adds `moon-traveler-cli` to your PATH. No Python required.

### From source

```bash
git clone https://github.com/elephantatech/moon_traveler.git
cd moon_traveler
uv sync            # or: pip install -r requirements.txt
python play.py
```

### 3. LLM Model (optional)

On first launch, the game offers to download an AI model:

| Model | Size | RAM | Quality |
|-------|------|-----|---------|
| **Qwen3.5 2B** (default) | 1.3 GB | ~2.3 GB | Good — best for most machines |
| **Gemma 4 E2B** (optional) | 3.1 GB | ~4.4 GB | Very Good — richer dialogue |

You can also place any `.gguf` model file manually in `~/.moonwalker/models/`. The game falls back to pre-written dialogue if no model is found.

## Running

```bash
python play.py          # Classic CLI mode
python play_tui.py      # Textual TUI mode (recommended)
```

**TUI mode** features a fixed status bar, scrollable game log, tab-autocomplete with cycling, command history (Up/Down arrows), and F12 screenshots.

**Flags:**
```bash
python play_tui.py --dev     # Start with dev mode enabled
python play_tui.py --super   # Start with max trust, all items, full upgrades (testing)
python play_tui.py --dev --super  # Both
```

On startup you'll choose:
1. **Difficulty** — Easy (~30 min), Medium (~1-2 hours), Hard (~3+ hours), Brutal (~5+ hours)
2. **Compute mode** (auto-detected from config, changeable with `config gpu`)

## How to Play

For a comprehensive guide covering survival mechanics, creature interactions, drone upgrades, and strategy tips, see **[HOW_TO_PLAY.md](HOW_TO_PLAY.md)**.

### Commands

| Command | Description |
|---------|-------------|
| `look` | Describe current location |
| `scan` | Use drone to discover nearby locations |
| `gps` / `map` | Show known locations with distances |
| `travel <location>` | Travel to a discovered location |
| `take <item>` | Pick up an item |
| `inventory` / `inv` | Show your inventory |
| `talk <creature>` | Talk to a creature (LLM dialogue) |
| `give <item> to <creature>` | Give an item to build trust |
| `trade` | Trade items with a Merchant creature |
| `escort` | Ask a creature to travel with you / dismiss companions |
| `rest` | Rest for 1 hour to recover food/water |
| `drone` | Show drone status |
| `upgrade <component>` | Install a drone upgrade |
| `inspect <item>` | Examine an item to see what it's used for |
| `charge` | Toggle drone auto-charge (requires Charge Module) |
| `status` | Show food, water, suit, and repair progress |
| `ship` | Ship bays menu (repair, storage, kitchen, charging, medical) |
| `save` / `load` | Save or load game |
| `sound` | Toggle sound effects on/off |
| `tutorial` | Replay the ARIA boot sequence |
| `config` | View/change settings (save dir, GPU mode, context size) |
| `clear` / `cls` | Clear the screen |
| `help` | Show all commands |
| `quit` | Exit game (auto-saves) |

### During Conversations

<p align="center">
  <img src="assets/screenshot-creature-conversation.svg" alt="Creature Conversation" width="700"/>
</p>

- Type normally to speak through the drone translator
- Type `/end` or `bye` to leave the conversation
- Type `/?` for conversation help
- Use `/<command>` to run game commands mid-conversation (e.g., `/status`, `/inventory`)
- The drone whispers private advice that the creature can't hear

### Winning

Build trust with creatures to obtain repair materials through conversation and trade. Bring materials to the Crash Site and install them via `ship repair`. Escort friendly creatures to the ship — Builders install materials, Healers restore your vitals.

<p align="center">
  <img src="assets/screenshot-ship-bays-menu.svg" alt="Ship Bays" width="700"/>
</p>

### Survival Tips

- Watch your food and water — they deplete during travel, and hazards can drain them further
- Creatures are your main source of repair materials — build trust to unlock their help
- Healers help at very low trust (it's their calling) — find one early for survival
- Trade with Merchants — they always want something in return but have valuable materials
- Ask the Enforcer who can help with your ship — they know everyone in the area
- Cook bio_gel (food) and ice_crystal (water) at the ship's Kitchen Bay
- Use Ship Storage's "stash all" to quickly free up drone cargo for exploration
- Late-game weather gets worse — finish repairs before conditions deteriorate

## Game Modes

| Mode | Locations | Creatures | Radius | Duration |
|------|-----------|-----------|--------|----------|
| Short | ~8 | 5 | ~20 km | ~30 min |
| Medium | ~16 | 12 | ~40 km | ~1-2 hours |
| Long | ~30 | 20 | ~60 km | ~3+ hours |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Model download fails** | Manually place any `.gguf` file in `~/.moonwalker/models/` |
| **GPU not detected** | Game auto-falls back to CPU. Check CUDA/Metal/Vulkan drivers if you want GPU acceleration |
| **Model won't load / crashes** | Game continues with pre-written fallback dialogue. Delete and re-download the model |
| **Dialogue feels repetitive** | Run `dev` to check if LLM is loaded (`model_loaded: true` in log). Upgrade the Translator Chip |
| **Game hangs during conversation** | LLM inference can be slow on CPU. Press `Ctrl+C` to exit safely. Progress is auto-saved |
| **Where are save files?** | `~/.moonwalker/saves/` (SQLite). Run `config` to view/change location |

### User Data

All persistent data is stored in `~/.moonwalker/` by default:

```
~/.moonwalker/
  config.json       # game configuration
  saves/            # save files (SQLite)
  models/           # downloaded AI models (.gguf)
  dev/              # dev mode diagnostic logs
```

### Dev Mode

Type `dev` in-game to toggle developer diagnostics. Logs game state, creature details, chat history, LLM status, and event tracking to `~/.moonwalker/dev/dev_diagnostics.jsonl` (JSON Lines format). Use `/history` during conversations to view the last 10 exchanges with a creature.

See **[HOW_TO_PLAY.md](HOW_TO_PLAY.md#troubleshooting)** for the full troubleshooting guide and dev mode reference.

## Building a Release

A cross-platform build script is included:

```bash
python scripts/build_release.py
```

This creates standalone executables for Windows, macOS, and Linux in the `dist/` directory using PyInstaller. See `scripts/build_release.py` for details.

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### Code Style

The project uses [ruff](https://github.com/astral-sh/ruff) for linting:
```bash
ruff check src/ tests/
```

## Project Structure

```
moon-traveler-cli/
  play.py              Entry point
  src/
    game.py            Main game loop, init, win/lose
    world.py           Procedural world generation
    player.py          Player state, inventory, survival meters
    creatures.py       Creature generation, roles, trust, dialogue
    drone.py           Drone: scanning, speech, translation, smart advice
    travel.py          Movement, hazard events, late-game weather
    commands.py        Command registry, NPC chat, trade, escort
    llm.py             LLM interface, GPU detection, action tags
    ship_ai.py         ARIA ship AI: warnings, summaries
    ui.py              Rich console output, ASCII art
    tutorial.py        Boot sequence, guided tutorial
    save_load.py       SQLite save/load
    input_handler.py   Autocomplete
    dev_mode.py        Developer diagnostics (JSON log)
    data/
      names.py         Name pools
      prompts.py       LLM prompts + drone message pools
  ~/.moonwalker/       User data (saves, models, config, dev logs)
  tests/               Test suite
  scripts/             Build and release scripts
```

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
