from __future__ import annotations

"""The locked study loop. Hands hunt. The mouth only recites."""

MECHANISM = """\
Конечный механизм — две петли, они не смешиваются.

1. Руки (работа). Команда «изучи …» или «изучи дальше».
   Задание → найти страницы → взять одну по смыслу задания →
   отжать факты в notes/BRAIN.md → решить, какой кусок устройства ещё дыра →
   идти в дыру, не перечитывая ту же статью → остановиться, когда в тетради
   есть механизм, или кончились страницы → записать notes/PLAN.md.
   Рот не трогаем: страницы Git, TLS, HTTP, Битрикса в веса не идут.

2. Рот (речь). Команда «поучи …» и ночная школа.
   Поёт notes/BRAIN.md и учебник, чтобы «Привет» не стал print.
   Интернет для рта — только язык и короткие песни, не внутренности продуктов.

3. Один взгляд. «что такое …» / «узнай …» — одна страница, не миссия.

Дальше сам: python3 -m child.research --expand
"""

MECHANISM_MARKERS = (
    "как ты учишься",
    "как ты учишься?",
    "какой механизм",
    "конечный механизм",
    "как устроена учёба",
    "как устроена учеба",
    "how do you learn",
    "what's the loop",
)


def is_mechanism_question(text: str) -> bool:
    low = text.casefold().strip()
    return any(marker in low for marker in MECHANISM_MARKERS) or low in {
        "механизм",
        "петля",
        "loop",
    }


def describe_mechanism() -> str:
    return MECHANISM.strip()
