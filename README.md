# Moon Traveler CLI

A text-based survival game set on Enceladus, Saturn's icy moon. You've crash-landed and must explore procedurally generated locations, befriend alien creatures through LLM-powered conversations, and gather materials to repair your ship.

## Features

- **Procedural world generation** with seeded RNG for replayable maps
- **LLM-powered creature dialogue** using a local Gemma 4 E2B model (no internet required)
- **AI drone companion** that translates alien speech, gives tactical advice, and comments during travel
- **Trust-based relationships** with 8 creature archetypes and 3 dispositions
- **Survival mechanics** tracking food, water, and suit integrity
- **GPU acceleration** with automatic detection and user-selectable CPU/GPU mode
- **Rich terminal UI** with styled text, progress bars, and ASCII art
- **Save/load system** with auto-save and manual slots

## Requirements

- Python 3.11+
- ~3.1 GB disk space for the LLM model
- (Optional) CUDA/Metal/Vulkan-capable GPU for faster LLM inference

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/moon-traveler-cli.git
cd moon-traveler-cli
```

### 2. Install dependencies

Using uv (recommended):
```bash
uv sync
```

Using pip:
```bash
pip install -r requirements.txt
pip install rich prompt_toolkit psutil
```

### 3. Download the LLM model

Place a GGUF model file in the `models/` directory. The game looks for:
```
models/gemma-4-E2B-it-Q4_K_M.gguf
```

Any `.gguf` file in `models/` will work. The game falls back to pre-written dialogue if no model is found.

## Running

```bash
python play.py
```

On startup you'll choose:
1. **Game length** (Short / Medium / Long)
2. **Compute mode** (CPU + GPU or CPU Only, if GPU detected)

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
| `drone` | Show drone status |
| `upgrade <component>` | Install a drone upgrade |
| `status` | Show food, water, suit, and repair progress |
| `ship` | Show ship repair checklist |
| `save` / `load` | Save or load game |
| `help` | Show all commands |
| `quit` | Exit game |

### During Conversations

- Type normally to speak through the drone translator
- Type `/end` or `bye` to leave the conversation
- Type `/?` for conversation help
- Use `/<command>` to run game commands mid-conversation (e.g., `/status`, `/inventory`)
- The drone whispers private advice that the creature can't hear

### Winning

Collect all required repair materials, deliver them to the Crash Site, and befriend enough creatures to help with repairs. The requirements scale with game length.

### Survival Tips

- Watch your food and water — they deplete during travel
- Your suit degrades slowly; longer games require careful resource management
- The drone's battery drains during scanning and travel; recharge at the Crash Site
- Build trust by having conversations (+3 per exchange) and giving gifts (+10-15)
- The drone's coaching tips tell you how to approach each creature type

## Game Modes

| Mode | Locations | Creatures | Radius | Duration |
|------|-----------|-----------|--------|----------|
| Short | ~8 | 5 | ~20 km | ~30 min |
| Medium | ~16 | 12 | ~40 km | ~1-2 hours |
| Long | ~30 | 20 | ~60 km | ~3+ hours |

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
ruff check src/
```

## Project Structure

```
moon-traveler-cli/
  play.py              Entry point
  src/
    game.py            Main game loop, init, win/lose
    world.py           Procedural world generation
    player.py          Player state, inventory, survival meters
    creatures.py       Creature generation, trust, dialogue
    drone.py           Drone: scanning, speech, translation, advice
    travel.py          Movement, events, drone musings
    commands.py        Command registry, NPC chat with drone interjections
    llm.py             LLM interface, GPU detection
    ship_ai.py         ARIA ship AI: warnings, summaries
    ui.py              Rich console output, ASCII art
    tutorial.py        Boot sequence, guided tutorial
    save_load.py       JSON serialization
    input_handler.py   Autocomplete
    dev_mode.py        Developer panel
    data/
      names.py         Name pools
      prompts.py       LLM prompts + drone message pools
  models/              GGUF model files
  saves/               Save game files
  tests/               Test suite
  scripts/             Build and release scripts
```

## License

MIT
