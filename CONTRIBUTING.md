# Contributing to Moon Traveler Terminal

Thank you for your interest in contributing. This document covers how to get started, our expectations, and how to submit changes.

## Code of Conduct

Be respectful. Be constructive. Assume good intentions. We're building a game about earning trust through conversation — the same principle applies here.

Unacceptable behavior includes harassment, personal attacks, trolling, and publishing others' private information. Violations will result in removal from the project.

## Getting Started

```bash
git clone https://github.com/elephantatech/moon_traveler.git
cd moon_traveler
uv sync
pip install pre-commit && pre-commit install
uv run python play_tui.py  # Launch game
```

## Development Workflow

1. **Fork** the repository
2. **Create a branch** from `main`: `git checkout -b feat/your-feature`
3. **Make your changes** — keep commits focused and well-described
4. **Pre-commit hooks run automatically** on `git commit` — they check:
   - Python lint + format (ruff)
   - Markdown lint (markdownlint-cli2)
   - Shell script lint (shellcheck)
   - YAML/JSON/TOML syntax
   - Trailing whitespace, line endings (LF), merge conflicts
   - No debug statements (`breakpoint()`, `pdb`)
5. **Run tests** before pushing:

   ```bash
   uv run pytest tests/
   ```

6. **Open a pull request** against `main` with a clear description

### CI Pipeline

PRs trigger 6 automated checks:

| Job | Tool | What it checks |
|-----|------|----------------|
| test | pytest | All tests pass |
| lint | ruff | Python lint + format |
| markdown | markdownlint-cli2 | Markdown formatting |
| shellcheck | shellcheck | Bash scripts (install.sh) |
| powershell-lint | PSScriptAnalyzer | PowerShell scripts (install.ps1) |
| actionlint | actionlint | GitHub Actions workflow syntax |

All 6 must pass before a PR can be merged.

## Code Style

- Python 3.11+
- Formatted and linted with [ruff](https://github.com/astral-sh/ruff)
- Line length: 120 characters
- No type: ignore comments without explanation
- Imports: sorted by ruff (isort rules)
- Line endings: LF only (no CRLF)
- All new features should have tests

## Architecture

```
play_tui.py              Entry point (Textual TUI)
src/
  game.py                Main loop, init, win/lose
  commands.py            Command handlers (the largest file)
  ui.py                  Rich console output + Textual bridge shim
  tui_app.py             Textual App, widgets, worker thread
  tui_bridge.py          Thread-safe bridge between worker and TUI
  input_handler.py       Tab-autocomplete (GameSuggester)
  llm.py                 LLM loading, inference, NPC memory
  stats.py               Session gameplay statistics
  creatures.py           Creature generation, trust, roles
  travel.py              Movement, hazards, resource drain
  difficulty.py          Mode scaling, junk items
  drone.py               Drone upgrades, battery, speech
  sound.py               Cross-platform sound effects
  config.py              User preferences (~/.moonwalker/)
  save_load.py           SQLite save/load
  ship_ai.py             ARIA warnings, summaries
  tutorial.py            Boot sequence, tutorial hints
  world.py               Procedural world generation
  data/                  Name pools, LLM prompts, fallbacks
tests/                   240+ tests across 17 files
docs/                    GitHub Pages site
docs/diagrams/           C4 architecture diagrams (Excalidraw)
```

## What to Work On

Check the [ROADMAP.md](ROADMAP.md) for planned features and the [Issues](https://github.com/elephantatech/moon_traveler/issues) page for bugs and enhancements. Issues labeled `good first issue` are suitable for new contributors.

## Submitting Issues

- **Bugs**: include steps to reproduce, expected vs actual behavior, game mode, and platform
- **Features**: describe the gameplay impact and reference the relevant ROADMAP section if applicable
- **Screenshots**: use `screenshot` command or F12 in TUI mode to capture SVGs

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
