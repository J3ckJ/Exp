from __future__ import annotations

import re

from child.grow import run_self_grow, wants_grow
from child.hands import (
    HANDS_HELP,
    extract_code,
    read_notebook,
    safe_python,
    wants_hands_help,
    wants_notebook,
)
from child.learn import run_night
from child.lesson import checkpoint_status
from child.memory import know, remember, retrieve
from child.talk import format_prompt
from child.tools import lookup, moscow_date, moscow_now, safe_calc
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
DATE_MARKERS = (
    "какое сегодня число",
    "какая сегодня дата",
    "какой сегодня день",
    "what date",
    "today's date",
    "what day is it",
    "какой день недели",
)
REMEMBER_MARKERS = ("запомни", "запомнить", "remember that", "remember:")
KNOW_MARKERS = (
    "что ты знаешь",
    "что ты помнишь",
    "что помнишь",
    "что знаешь про",
    "расскажи что знаешь",
    "what do you know",
    "what do you remember",
)
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
STATUS_MARKERS = (
    "сколько шагов",
    "какой урок",
    "что учил",
    "how many steps",
    "what did you study",
)


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
    if wants_hands_help(user):
        return HANDS_HELP
    if wants_notebook(user):
        return read_notebook()
    if any(marker in low for marker in STATUS_MARKERS):
        return checkpoint_status()
    if any(marker in low for marker in DATE_MARKERS) or low in {"дата", "date"}:
        return f"Сегодня {moscow_date()}."
    if any(marker in low for marker in REMEMBER_MARKERS):
        fact = _after_marker(user, REMEMBER_MARKERS)
        return remember(fact or user)
    if any(marker in low for marker in CALC_MARKERS) or re.fullmatch(r"[0-9+\-*/().\s]+", user):
        expr = _after_marker(user, CALC_MARKERS) or user
        value = safe_calc(expr)
        if value:
            return value
    code = extract_code(user)
    if code:
        return safe_python(code)
    if any(marker in low for marker in KNOW_MARKERS):
        query = _after_marker(user, KNOW_MARKERS) or user
        return know(query)
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
    if wants_grow(user) and not is_learn_command(user):
        print("Хорошо. Сам расту: новое тело, песни из тетради.")
        run_self_grow(checkpoint, force=True)
        return "Я вырос. Песни из тетради. Спроси меня."
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
        allow_grow=True,
        force_grow=wants_grow(user),
    )
    return "Я поучился. Спроси меня."


def jarvis_pairs() -> list[tuple[str, str]]:
    """Short tool-talk so the mouth can mention hands, not only school."""
    return [
        ("Который час?", "Сейчас скажу время."),
        ("Какое сегодня число?", "Сейчас скажу дату."),
        ("Запомни это", "Запомнил."),
        ("Узнай в интернете", "Сейчас посмотрю."),
        ("Что ты знаешь?", "Сейчас посмотрю в тетради."),
        ("Посчитай", "Сейчас посчитаю."),
        ("Выполни print", "Сейчас запущу."),
        ("Прочитай тетрадь", "Сейчас открою."),
        ("Вырасти", "Сейчас возьму больше ручек."),
        ("Что ты умеешь?", "Я говорю, помню, смотрю и считаю."),
    ]
