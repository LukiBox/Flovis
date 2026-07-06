"""
Integration with a local Ollama model.

Default model: qwen3:30b-a3b (installed locally by the user). The client is given
the full analysis context (geometry + polars + stability) and returns a written
interpretation in the app's current language (English by default, Polish when
selected). Fully offline (Ollama listens on http://localhost:11434).
"""
from __future__ import annotations

import json

from ..i18n import get_language, t

DEFAULT_MODEL = "qwen3:30b-a3b"
DEFAULT_HOST = "http://localhost:11434"

_BASE_SYSTEM = (
    "You are an experienced aerodynamics engineer and model-aircraft instructor. "
    "You explain analysis results to a hobbyist: in plain, concrete language, "
    "without excessive math, but technically correct. Do not invent numbers - use "
    "only the data given in the prompt. Write in paragraphs, no markdown headings."
)

# preset key -> (english label, structure instruction)
PRESETS = {
    "full": (
        "Full analysis",
        "Answer structure:\n"
        "1. Overall assessment (will the model fly well).\n"
        "2. Stability (interpret the static margin and neutral point).\n"
        "3. Performance (CL_max, L/D efficiency, suggested flight speed).\n"
        "4. Recommendations / what to improve.\n"
        "Be concise, 4 paragraphs."),
    "short": (
        "Short assessment",
        "Write a short (3-4 sentence) assessment: whether the model is stable and "
        "will fly well, plus the single most important tip."),
    "construction": (
        "Build tips",
        "Focus on practical construction tips for the builder: balancing (CG), "
        "airfoil and thickness choice, tail sizing and flight speed. Concrete, "
        "step by step."),
}


def is_available(host: str = DEFAULT_HOST) -> bool:
    try:
        import ollama
        ollama.Client(host=host).list()
        return True
    except Exception:
        return False


def list_models(host: str = DEFAULT_HOST) -> list[str]:
    try:
        import ollama
        data = ollama.Client(host=host).list()
        return [m.get("model") or m.get("name") for m in data.get("models", [])]
    except Exception:
        return []


def model_available(model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST) -> bool:
    models = list_models(host)
    return any(m == model or m.split(":")[0] == model.split(":")[0] for m in models)


def missing_model_hint(model: str = DEFAULT_MODEL) -> str:
    return t("Model '{m}' was not found in Ollama.\nPull it with:\n\n    "
             "ollama pull {m}\n\nAlso make sure the server is running: "
             "'ollama serve'.").format(m=model)


def _language_directive() -> str:
    if get_language() == "pl":
        return "\nRespond in Polish (odpowiadaj po polsku)."
    return "\nRespond in English."


def _system_prompt(preset: str) -> str:
    _, structure = PRESETS.get(preset, PRESETS["full"])
    return _BASE_SYSTEM + "\n" + structure + _language_directive()


def _build_prompt(payload: dict) -> str:
    return (
        "Analyze the following aerodynamic analysis of a flying model and write an "
        "interpretation for a hobbyist builder.\n\n"
        "DATA (JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=2,
                                      default=str)
    )


def build_context(result, model=None, polar2d=None) -> dict:
    """Assemble the full context (geometry + polars + stability) for the prompt."""
    payload = result.to_dict()
    payload["summary"] = result.summary_text()
    if model is not None:
        payload["geometry"] = model.to_dict()
    if polar2d is not None:
        payload["airfoil_polars_2D"] = {
            "method": polar2d.method,
            "Cl_max": round(polar2d.cl_max, 3),
            "alpha_stall_deg": round(polar2d.alpha_stall, 2),
            "Cl_Cd_max": round(polar2d.ld_max, 1),
            "Reynolds": polar2d.reynolds,
        }
    return payload


def interpret(payload: dict, model: str = DEFAULT_MODEL,
              host: str = DEFAULT_HOST, preset: str = "full",
              think: bool = False) -> str:
    """Return a written interpretation (call from a worker thread)."""
    import ollama
    client = ollama.Client(host=host)
    resp = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt(preset)},
            {"role": "user", "content": _build_prompt(payload)},
        ],
        options={"temperature": 0.4},
        think=think,
    )
    return resp["message"]["content"].strip()


def interpret_stream(payload: dict, model: str = DEFAULT_MODEL,
                     host: str = DEFAULT_HOST, preset: str = "full",
                     think: bool = True):
    """
    Streaming generator. Yields tuples ("thinking"|"content", text).

    For reasoning models (e.g. qwen3) the model's default routes the chain of
    thought to the 'thinking' field (progress) while 'content' holds the clean
    answer. Non-reasoning models simply never produce 'thinking'.
    """
    import ollama
    client = ollama.Client(host=host)
    for chunk in client.chat(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt(preset)},
            {"role": "user", "content": _build_prompt(payload)},
        ],
        options={"temperature": 0.4},
        stream=True,
    ):
        msg = chunk["message"]
        th = msg.get("thinking")
        if th:
            yield ("thinking", th)
        ct = msg.get("content")
        if ct:
            yield ("content", ct)
