"""LLM interface: llama-cpp-python with fallback to canned responses."""

import os
import random
import sys
import urllib.request
from pathlib import Path

from src import ui
import re

from src.data.prompts import (
    BASE_CREATURE_PROMPT,
    CREATURE_ACTION_INSTRUCTIONS,
    DISPOSITION_INSTRUCTIONS,
    FALLBACK_RESPONSES,
    PERSONALITY_DETAILS,
    TRANSLATION_QUALITY,
    TRUST_INSTRUCTIONS,
)

# Try to import llama-cpp-python
_llm_model = None
_llm_available = False

try:
    from llama_cpp import Llama

    _LLAMA_AVAILABLE = True
except (ImportError, OSError, FileNotFoundError):
    _LLAMA_AVAILABLE = False
    Llama = None


def detect_gpu() -> dict:
    """Detect whether GPU acceleration is available for llama-cpp-python.

    Returns dict with 'available' (bool) and 'backend' (str).
    """
    if not _LLAMA_AVAILABLE:
        return {"available": False, "backend": "none"}

    try:
        import llama_cpp

        # Check for CUDA support
        if hasattr(llama_cpp, "llama_supports_gpu_offload") and llama_cpp.llama_supports_gpu_offload():
            return {"available": True, "backend": "cuda/metal/vulkan"}
        # Fallback: try to check via backend info
        if hasattr(llama_cpp, "LLAMA_SUPPORTS_GPU_OFFLOAD"):
            if llama_cpp.LLAMA_SUPPORTS_GPU_OFFLOAD:
                return {"available": True, "backend": "gpu"}
    except Exception:
        pass

    # Last resort: check if the compiled lib mentions GPU backends
    try:
        import llama_cpp.llama_cpp as _ll

        if hasattr(_ll, "GGML_USE_CUDA") or hasattr(_ll, "GGML_USE_METAL") or hasattr(_ll, "GGML_USE_VULKAN"):
            return {"available": True, "backend": "gpu"}
    except Exception:
        pass

    return {"available": False, "backend": "none"}


# Available models — ordered by preference (smallest first)
AVAILABLE_MODELS = [
    {
        "name": "Qwen3.5 2B (Lite — recommended)",
        "filename": "Qwen3.5-2B-Q4_K_M.gguf",
        "url": "https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf",
        "size": "1.3 GB",
        "ram": "~2.3 GB",
    },
    {
        "name": "Gemma 4 E2B (Full quality)",
        "filename": "gemma-4-E2B-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf",
        "size": "3.1 GB",
        "ram": "~4.4 GB",
    },
]

# Default model (Qwen3.5 2B — best balance of size and quality for this game)
DEFAULT_MODEL = AVAILABLE_MODELS[0]


def _get_models_dir() -> Path:
    """Get the models directory, handling both dev and frozen (PyInstaller) contexts."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "models"
    return Path(__file__).parent.parent / "models"


def find_model_path() -> str | None:
    """Find a GGUF model file. Checks for any .gguf, then known model filenames."""
    models_dir = _get_models_dir()
    candidates = []

    # Any .gguf in models/ takes priority (user-placed model)
    if models_dir.exists():
        for f in models_dir.glob("*.gguf"):
            candidates.insert(0, f)

    # Check known model filenames
    for model in AVAILABLE_MODELS:
        candidates.append(models_dir / model["filename"])

    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _download_file(url: str, target: Path) -> bool:
    """Download a file with progress bar. Returns True on success."""
    try:
        def _progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                pct = min(100.0, downloaded * 100.0 / total_size)
                gb_down = downloaded / 1e9
                gb_total = total_size / 1e9
                print(f"\r  Progress: {pct:5.1f}%  ({gb_down:.2f} / {gb_total:.2f} GB)", end="", flush=True)

        urllib.request.urlretrieve(url, str(target), reporthook=_progress)
        print()
        return True
    except Exception as e:
        print()
        ui.error(f"Download failed: {e}")
        if target.exists():
            target.unlink()
        return False


def maybe_download_model() -> bool:
    """Prompt the user to choose and download a model if none present. Returns True if model is ready."""
    if find_model_path():
        return True

    import platform as _platform

    ui.console.print()
    ui.warn(f"No GGUF model found in {_get_models_dir()}")
    ui.info("The game uses a local AI model for creature conversations.")
    ui.info("Without it, creatures will use simpler pre-written dialogue.")
    ui.console.print()

    # Detect system and show relevant info
    system = _platform.system()
    machine = _platform.machine()
    gpu_info = detect_gpu()
    sys_label = f"{system} ({machine})"
    if gpu_info["available"]:
        sys_label += f" [green]GPU: {gpu_info['backend']}[/green]"
    ui.dim(f"  System: {sys_label}")

    # Recommend model based on available RAM
    try:
        import psutil
        total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        ui.dim(f"  RAM: {total_ram_gb:.0f} GB total")
        if total_ram_gb < 4:
            ui.dim("  [yellow]Low RAM detected — Qwen3.5 2B (Lite) recommended[/yellow]")
        elif total_ram_gb >= 8:
            ui.dim("  Enough RAM for either model")
    except ImportError:
        pass
    ui.console.print()

    ui.console.print("[bold]Available models:[/bold]")
    for i, model in enumerate(AVAILABLE_MODELS, 1):
        ui.console.print(
            f"  [cyan]{i}[/cyan]. {model['name']}  "
            f"[dim]({model['size']} download, {model['ram']} RAM)[/dim]"
        )
    ui.console.print(f"  [cyan]{len(AVAILABLE_MODELS) + 1}[/cyan]. Skip (use fallback dialogue)")
    ui.console.print()

    try:
        answer = ui.console.input("[bold]Choose model > [/bold]").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    try:
        idx = int(answer) - 1
    except ValueError:
        if answer.lower() in ("y", "yes"):
            idx = 0  # default to first model
        else:
            ui.dim("Skipping download. Fallback dialogue will be used.")
            return False

    if idx < 0 or idx >= len(AVAILABLE_MODELS):
        ui.dim("Skipping download. Fallback dialogue will be used.")
        return False

    model = AVAILABLE_MODELS[idx]
    models_dir = _get_models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    target = models_dir / model["filename"]

    ui.info(f"Downloading {model['name']}...")
    ui.dim(f"File: {model['filename']} ({model['size']})")
    ui.console.print()

    if _download_file(model["url"], target):
        ui.success(f"Model downloaded to {target}")
        return True
    else:
        ui.dim("You can manually download a .gguf model and place it in the models/ directory.")
        return False


def load_model(callback=None, gpu_mode: str = "cpu"):
    """Load the LLM model.

    gpu_mode: "cpu" for CPU only, "gpu" for GPU offload.
    Call callback(success: bool) when done.
    """
    global _llm_model, _llm_available

    if not _LLAMA_AVAILABLE:
        ui.warn("llama-cpp-python not installed. Using fallback dialogue.")
        if callback:
            callback(False)
        return

    model_path = find_model_path()
    if not model_path:
        ui.warn("No GGUF model found. Using fallback dialogue.")
        if callback:
            callback(False)
        return

    n_gpu_layers = -1 if gpu_mode == "gpu" else 0
    mode_label = "CPU + GPU" if gpu_mode == "gpu" else "CPU only"

    ui.info(f"Loading LLM model: {os.path.basename(model_path)} ({mode_label})...")
    ui.dim("(This may take 30-60 seconds on first load)")

    try:
        _llm_model = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=4,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        _llm_available = True
        ui.success(f"LLM model loaded successfully! ({mode_label})")
    except Exception as e:
        ui.error(f"Failed to load LLM model: {e}")
        if gpu_mode == "gpu":
            ui.warn("GPU loading failed. Retrying with CPU only...")
            try:
                _llm_model = Llama(
                    model_path=model_path,
                    n_ctx=4096,
                    n_threads=4,
                    n_gpu_layers=0,
                    verbose=False,
                )
                _llm_available = True
                ui.success("LLM model loaded successfully! (CPU fallback)")
            except Exception as e2:
                ui.error(f"CPU fallback also failed: {e2}")
                ui.warn("Using fallback dialogue.")
                _llm_available = False
        else:
            ui.warn("Using fallback dialogue.")
            _llm_available = False

    if callback:
        callback(_llm_available)


def is_available() -> bool:
    return _llm_available


def build_system_prompt(creature) -> str:
    """Build a system prompt for a creature based on its attributes."""
    personality_detail = PERSONALITY_DETAILS.get(creature.archetype, "")
    disposition_instruction = DISPOSITION_INSTRUCTIONS.get(creature.disposition, "")
    trust_instruction = TRUST_INSTRUCTIONS.get(creature.trust_level, "")
    knowledge_text = "\n".join(f"- You {k}" for k in creature.knowledge)
    if creature.knows_food_source:
        knowledge_text += f"\n- You know there is food at {creature.knows_food_source}"
    if creature.knows_water_source:
        knowledge_text += f"\n- You know there is water at {creature.knows_water_source}"

    base = BASE_CREATURE_PROMPT.format(
        name=creature.name,
        species=creature.species,
        archetype=creature.archetype,
        personality_detail=personality_detail,
        disposition_instruction=disposition_instruction,
        knowledge=knowledge_text,
        trust_instruction=trust_instruction,
        translation_instruction="",
    )

    # Add action tag instructions so the LLM can give items to the player
    materials_list = ", ".join(creature.can_give_materials) if creature.can_give_materials else "none"
    action_instructions = CREATURE_ACTION_INSTRUCTIONS.format(available_materials=materials_list)
    return base + action_instructions


def build_system_prompt_with_translation(creature, translation_quality: str) -> str:
    """Build system prompt with translation quality factored in."""
    base = build_system_prompt(creature)
    translation_mod = TRANSLATION_QUALITY.get(translation_quality, "")
    return base + translation_mod


def generate_response(creature, player_message: str, translation_quality: str = "low") -> str:
    """Generate a response from a creature. Uses LLM if available, fallback otherwise."""
    if not _llm_available or _llm_model is None:
        return fallback_response(creature)

    system_prompt = build_system_prompt_with_translation(creature, translation_quality)

    # Build messages from conversation history
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history (includes the current player message)
    for msg in creature.conversation_history[-10:]:
        messages.append(msg)

    try:
        response = _llm_model.create_chat_completion(
            messages=messages,
            max_tokens=200,
            temperature=0.8,
            top_p=0.9,
            stop=["Human:", "Player:", "\n\n\n"],
        )
        text = response["choices"][0]["message"]["content"].strip()
        if text:
            return text
        return fallback_response(creature)
    except Exception as e:
        ui.dim(f"(LLM error: {e})")
        return fallback_response(creature)


# --- Action tag parsing ---

# Pattern matches [GIVE_WATER], [GIVE_FOOD], [REPAIR_SUIT], [HEAL], [GIVE_MATERIAL:item_name]
_ACTION_PATTERN = re.compile(
    r"\[(?P<action>GIVE_WATER|GIVE_FOOD|REPAIR_SUIT|HEAL)\]"
    r"|\[(?P<mat_action>GIVE_MATERIAL):(?P<param>[a-zA-Z_]+)\]",
    re.IGNORECASE,
)


def parse_actions(response: str) -> tuple[str, list[dict]]:
    """Extract action tags from an LLM response.

    Returns (cleaned_text, actions) where actions is a list of
    dicts like {"action": "GIVE_WATER"} or {"action": "GIVE_MATERIAL", "item": "ice_crystal"}.
    """
    actions = []
    for match in _ACTION_PATTERN.finditer(response):
        # Simple actions: GIVE_WATER, GIVE_FOOD, REPAIR_SUIT, HEAL
        action = match.group("action")
        if action:
            actions.append({"action": action.upper()})
            continue
        # Material action: GIVE_MATERIAL:item_name
        mat_action = match.group("mat_action")
        if mat_action:
            param = match.group("param").strip().lower()
            entry = {"action": "GIVE_MATERIAL"}
            if param:
                entry["item"] = param
            actions.append(entry)

    # Strip action tags from displayed text and collapse double spaces
    cleaned = _ACTION_PATTERN.sub("", response).strip()
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned, actions


def apply_actions(actions: list[dict], player, drone, creature, repair_checklist: dict) -> list[str]:
    """Apply parsed actions to game state. Returns list of UI messages."""
    # Trust guard: ignore actions from creatures that shouldn't be giving things
    if creature.trust_level == "low":
        return []

    messages = []
    for act in actions:
        action = act["action"]

        if action == "GIVE_WATER":
            player.replenish_water()
            messages.append(f"[bold cyan]{creature.name} shared water with you! Water fully restored.[/bold cyan]")

        elif action == "GIVE_FOOD":
            player.replenish_food()
            messages.append(f"[bold cyan]{creature.name} shared food with you! Food fully restored.[/bold cyan]")

        elif action == "HEAL":
            # Heal restores 30% food and 30% water
            player.food = min(100.0, player.food + 30.0)
            player.water = min(100.0, player.water + 30.0)
            messages.append(
                f"[bold cyan]{creature.name} healed you! Food +30%, Water +30%.[/bold cyan]"
            )

        elif action == "REPAIR_SUIT":
            # Restores 25% suit integrity
            restore = min(25.0, 100.0 - player.suit_integrity)
            if restore > 0:
                player.suit_integrity = min(100.0, player.suit_integrity + restore)
                messages.append(
                    f"[bold cyan]{creature.name} repaired your suit! "
                    f"Suit integrity: {player.suit_integrity:.0f}%[/bold cyan]"
                )

        elif action == "GIVE_MATERIAL":
            item = act.get("item", "")
            if item and item in creature.can_give_materials:
                player.add_item(item)
                creature.can_give_materials.remove(item)
                display = item.replace("_", " ").title()
                messages.append(
                    f"[bold cyan]{creature.name} gave you: {display}![/bold cyan]"
                )

    return messages


def fallback_response(creature, rng: random.Random | None = None) -> str:
    """Get a pre-written response based on creature archetype."""
    if rng is None:
        rng = random.Random()
    responses = FALLBACK_RESPONSES.get(
        creature.archetype,
        [
            "The creature regards you silently.",
            "It makes a sound you can't interpret.",
        ],
    )
    return rng.choice(responses)
