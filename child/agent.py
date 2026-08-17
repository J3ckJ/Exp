from __future__ import annotations

import re

from child.learn import run_night
from child.memory import remember, retrieve
from child.talk import format_prompt
from child.tools import lookup, moscow_now, safe_calc
from child.wish import is_learn_command, parse_wish

TIME_MARKERS = (
    "который час",
    "сколько времени",
    "который час?",
    "время в москве",
    "what time",
    "time in moscow",
    "сколько сейчас",
)
REMEMBER_MARKERS = ("запомни", "запомнить", "remember that", "remember:")
LOOKUP_MARKERS = (
    "узнай",
    "найди",
    "посмотри",
    "look up",
    "что такое",
    "who is",
    "what is the capital",
)
CALC_MARKERS = ("сколько будет", "посчитай", "compute", "calculate")


def _after_marker(text: str, markers: tuple[str, ...]) -> str:
    low = text.casefold()
    for marker in markers:
        idx = low.find(marker)
        if idx >= 0:
            return text[idx + len(marker) :].strip(" :,-")
    return ""


def route_tools(user: str) -> str | None:
    low = user.casefold().strip()
    if any(marker in low for marker in TIME_MARKERS) or low in {"время", "time"}:
        return f"В Москве сейчас {moscow_now()}."
    if any(marker in low for marker in REMEMBER_MARKERS):
        fact = _after_marker(user, REMEMBER_MARKERS)
        return remember(fact or user)
    if any(marker in low for marker in CALC_MARKERS) or re.fullmatch(r"[0-9+\-*/().\s]+", user):
        expr = _after_marker(user, CALC_MARKERS) or user
        value = safe_calc(expr)
        if value:
            return value
    if any(marker in low for marker in LOOKUP_MARKERS):
        query = _after_marker(user, LOOKUP_MARKERS) or user
        query = re.sub(r"^(что такое|who is|look up)\s+", "", query, flags=re.I).strip(" ?")
        return lookup(query)
    return None


def speak_prompt(user: str, history: list[tuple[str, str]], block_size: int) -> str:
    notes = retrieve(user, limit=2)
    tail = format_prompt(user, history, block_size)
    if not notes:
        return tail
    prefix = "Заметка: " + " ".join(notes) + "\n"
    candidate = prefix + tail
    if len(candidate.encode("utf-8")) <= block_size:
        return candidate
    return tail


def study_command(user: str, learn_steps: int, checkpoint: str) -> str | None:
    if not is_learn_command(user):
        return None
    parsed = parse_wish(user)
    print(f"Хорошо. Сам учусь: topic={parsed.topic} web={parsed.use_web}")
    run_night(
        wish=user,
        sources=[],
        urls=[],
        use_web=parsed.use_web,
        steps=learn_steps,
        batch_size=32,
        lr=8e-5,
        seed=42,
        resume=checkpoint,
        out=checkpoint,
        sample_every=0,
        keep_inbox=True,
        skip_exam=True,
    )
    return "Я поучился. Спроси меня."


def jarvis_pairs() -> list[tuple[str, str]]:
    """Short tool-talk so the mouth can mention hands, not only school."""
    return [
        ("Который час?", "Сейчас скажу время."),
        ("Запомни это", "Запомнил."),
        ("Узнай в интернете", "Сейчас посмотрю."),
        ("Посчитай", "Сейчас посчитаю."),
    ]
