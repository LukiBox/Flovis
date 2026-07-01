"""
Integracja z lokalnym modelem Ollama.

Model domyslny: qwen3:30b-a3b (zainstalowany lokalnie przez uzytkownika).
Klient otrzymuje pelny kontekst analizy (geometria + bieguny + statecznosc)
i zwraca interpretacje slowna po polsku, gotowa do raportu PDF.

Dziala w pelni offline (Ollama nasluchuje na http://localhost:11434).
Raport mozna wygenerowac takze bez AI - sekcja jest opcjonalna.
"""
from __future__ import annotations

import json

DEFAULT_MODEL = "qwen3:30b-a3b"
DEFAULT_HOST = "http://localhost:11434"

_BASE_SYSTEM = (
    "Jestes doswiadczonym inzynierem aerodynamikiem i instruktorem modelarstwa "
    "lotniczego. Tlumaczysz wyniki analiz dla pasjonata-hobbysty: jezykiem "
    "prostym, konkretnym, bez nadmiaru matematyki, ale merytorycznie poprawnie. "
    "Odpowiadasz po polsku. Nie zmyslasz liczb - korzystasz wylacznie z danych "
    "podanych w prompcie. Pisz w akapitach, bez markdownowych naglowkow."
)

# presety promptow: (etykieta UI, instrukcja struktury odpowiedzi)
PRESETS = {
    "full": (
        "Pelna analiza",
        "Struktura odpowiedzi:\n"
        "1. Ocena ogolna (czy model bedzie dobrze latal).\n"
        "2. Statecznosc (interpretacja zapasu statecznosci i punktu neutralnego).\n"
        "3. Osiagi (CL_max, doskonalosc L/D, sugerowana predkosc lotu).\n"
        "4. Zalecenia / co poprawic.\n"
        "Pisz zwiezle, 4 akapity."),
    "short": (
        "Krotka ocena",
        "Napisz krotka (3-4 zdania) ocene: czy model jest stateczny i czy bedzie "
        "dobrze latal, oraz jedna najwazniejsza rada."),
    "construction": (
        "Porady konstrukcyjne",
        "Skup sie na praktycznych poradach konstrukcyjnych dla budowniczego: "
        "wywazenie (CG), dobor profilu i grubosci, sugestie co do usterzenia i "
        "predkosci lotu. Konkretnie i po kolei."),
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
    return (f"Nie znaleziono modelu '{model}' w Ollama.\n"
            f"Pobierz go poleceniem:\n\n    ollama pull {model}\n\n"
            "Upewnij sie tez, ze dziala serwer: 'ollama serve'.")


def _system_prompt(preset: str) -> str:
    _, structure = PRESETS.get(preset, PRESETS["full"])
    return _BASE_SYSTEM + "\n" + structure


def _build_prompt(payload: dict) -> str:
    return (
        "Przeanalizuj ponizsze wyniki analizy aerodynamicznej modelu latajacego "
        "i przygotuj interpretacje dla konstruktora-hobbysty.\n\n"
        "DANE (JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=2,
                                      default=str)
    )


def build_context(result, model=None, polar2d=None) -> dict:
    """Sklada pelny kontekst (geometria + bieguny + statecznosc) do promptu."""
    payload = result.to_dict()
    payload["podsumowanie"] = result.summary_text()
    if model is not None:
        payload["geometria"] = model.to_dict()
    if polar2d is not None:
        payload["profil_bieguny_2D"] = {
            "metoda": polar2d.method,
            "Cl_max": round(polar2d.cl_max, 3),
            "alpha_stall_deg": round(polar2d.alpha_stall, 2),
            "Cl_Cd_max": round(polar2d.ld_max, 1),
            "Reynolds": polar2d.reynolds,
        }
    return payload


def interpret(payload: dict, model: str = DEFAULT_MODEL,
              host: str = DEFAULT_HOST, preset: str = "full",
              think: bool = False) -> str:
    """Zwraca interpretacje slowna wynikow (nieblokujaco wywoluj w watku)."""
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
    Generator strumieniowy. Yielduje krotki ("thinking"|"content", tekst).

    Dla modeli rozumujacych (np. qwen3) think=True kieruje lancuch myslowy do
    pola 'thinking' (podglad postepu), a 'content' zawiera czysta odpowiedz po
    polsku. Dla modeli nierozumujacych 'thinking' po prostu nie wystapi.
    """
    import ollama
    client = ollama.Client(host=host)
    # Nie wymuszamy 'think' - domyslne ustawienie modelu jest bezpieczne:
    # modele rozumujace (qwen3) same kieruja lancuch myslowy do pola 'thinking'
    # (czysta odpowiedz trafia do 'content'), a modele zwykle daja od razu content.
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
