"""User configuration: save path and preferences. Persisted as config.json."""

import json
import sys
from pathlib import Path

from src import ui

# Config file lives next to the executable (frozen) or project root (dev)
if getattr(sys, "frozen", False):
    _CONFIG_DIR = Path(sys.executable).parent
else:
    _CONFIG_DIR = Path(__file__).parent.parent

CONFIG_PATH = _CONFIG_DIR / "config.json"

# Defaults
_DEFAULT_SAVE_DIR = _CONFIG_DIR / "saves"

_config: dict | None = None


def _load() -> dict:
    global _config
    if _config is not None:
        return _config
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                _config = json.load(f)
        except Exception:
            _config = {}
    else:
        _config = {}
    return _config


def _save():
    if _config is None:
        return
    with open(CONFIG_PATH, "w") as f:
        json.dump(_config, f, indent=2)


def get_save_dir() -> Path:
    """Get the configured save directory."""
    cfg = _load()
    path_str = cfg.get("save_dir")
    if path_str:
        return Path(path_str)
    return _DEFAULT_SAVE_DIR


def set_save_dir(path: Path):
    """Set and persist the save directory."""
    cfg = _load()
    cfg["save_dir"] = str(path.resolve())
    _save()


def is_first_run() -> bool:
    """True if no config file exists yet (first launch)."""
    return not CONFIG_PATH.exists()


def prompt_save_location():
    """Prompt the user to choose a save location on first run."""
    default = str(_DEFAULT_SAVE_DIR)

    ui.console.print()
    ui.info("First time setup: Where should game saves be stored?")
    ui.console.print(f"  Default: [cyan]{default}[/cyan]")
    ui.console.print()

    try:
        answer = ui.console.input(
            "[bold]Save location (press Enter for default) > [/bold]"
        ).strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if answer:
        save_path = Path(answer).expanduser().resolve()
    else:
        save_path = Path(default)

    # Validate the path
    try:
        save_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        ui.error(f"Cannot create directory: {e}")
        ui.warn(f"Using default: {default}")
        save_path = Path(default)
        save_path.mkdir(parents=True, exist_ok=True)

    set_save_dir(save_path)
    ui.success(f"Saves will be stored in: {save_path}")
    ui.dim(f"(Change later with the 'config' command)")
    ui.console.print()
