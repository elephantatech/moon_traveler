"""LLM interface: llama-cpp-python with fallback to canned responses."""

import os
import random
from pathlib import Path

from src import ui
from src.data.prompts import (
    BASE_CREATURE_PROMPT,
    DISPOSITION_INSTRUCTIONS,
    FALLBACK_RESPONSES,
    PERSONALITY_DETAILS,
    TRANSLATION_QUALITY,
    TRUST_INSTRUCTIONS,
)

# Try to import llama-cpp-python
_llm_model = None
_llm_available = False
_loading = False

try:
    from llama_cpp import Llama

    _LLAMA_AVAILABLE = True
except ImportError:
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


def find_model_path() -> str | None:
    """Find the GGUF model file."""
    candidates = [
        Path(__file__).parent.parent / "models" / "gemma-4-E2B-it-Q4_K_M.gguf",
        Path("D:/projects/moon_traveler/models/gemma-4-E2B-it-Q4_K_M.gguf"),
    ]
    # Also check for any .gguf in models/
    models_dir = Path(__file__).parent.parent / "models"
    if models_dir.exists():
        for f in models_dir.glob("*.gguf"):
            candidates.insert(0, f)

    for path in candidates:
        if path.exists():
            return str(path)
    return None


def load_model(callback=None, gpu_mode: str = "cpu"):
    """Load the LLM model.

    gpu_mode: "cpu" for CPU only, "gpu" for GPU offload.
    Call callback(success: bool) when done.
    """
    global _llm_model, _llm_available, _loading

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

    _loading = True
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

    _loading = False
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

    return BASE_CREATURE_PROMPT.format(
        name=creature.name,
        species=creature.species,
        archetype=creature.archetype,
        personality_detail=personality_detail,
        disposition_instruction=disposition_instruction,
        knowledge=knowledge_text,
        trust_instruction=trust_instruction,
        translation_instruction="",
    )


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

    # Add conversation history
    for msg in creature.conversation_history[-10:]:
        messages.append(msg)

    # Add current message
    messages.append({"role": "user", "content": player_message})

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
