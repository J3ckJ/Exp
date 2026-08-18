from __future__ import annotations

from child.memory import load_brain_lines

# What a task usually needs next. Not ChatGPT: a small map of trades.
ASSIGNMENT_SEEDS: tuple[tuple[tuple[str, ...], tuple[tuple[str, str], ...]], ...] = (
    (
        (
            "битрикс",
            "bitrix",
            "црм",
            "crm",
            "смарт-процесс",
            "смарт процесс",
            "цифровое рабочее",
        ),
        (
            (
                "PHP",
                "В ЦРМ Битрикса смарт-процессы часто держат блоки PHP — без PHP работу не собрать.",
            ),
        ),
    ),
    (
        ("смарт-процесс", "смартпроцесс", "smart process"),
        (
            (
                "PHP",
                "Смарт-процесс без PHP — только картинка. Надо уметь читать код в блоках.",
            ),
        ),
    ),
    (
        ("робот", "бизнес-процесс"),
        (
            (
                "PHP",
                "Робот в Битриксе часто выполняет PHP. Иначе не понять, что он меняет.",
            ),
        ),
    ),
)

# If the page itself talks about a craft, go learn that craft.
PAGE_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("php", "пхп"), "PHP"),
    (("javascript", "java script", "js "), "JavaScript"),
    (("python", "питон"), "Python"),
    (("rest api", "rest-api", "вебхук", "webhook"), "REST API"),
    (("mysql", "база данных", "sql"), "SQL"),
)


def _norm(text: str) -> str:
    return " " + text.casefold().replace("ё", "е") + " "


def already_knows(topic: str) -> bool:
    """True only if a notebook line is *about* the topic, not merely mentions it."""
    key = topic.casefold()
    if len(key) < 3:
        return False
    alt = key.replace("-", " ")
    for line in load_brain_lines():
        low = line.casefold()
        if low.startswith(key) or low.startswith(alt):
            return True
    return False


def next_topics(assignment: str, page: str, limit: int = 2) -> list[tuple[str, str]]:
    """Return (topic, why) the child should study next. Own initiative."""
    assign = _norm(assignment)
    body = _norm(assignment + "\n" + page)
    chosen: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(topic: str, why: str) -> None:
        key = topic.casefold()
        if key in seen or already_knows(topic):
            return
        if key == assignment.casefold():
            return
        seen.add(key)
        chosen.append((topic, why))

    for needles, follow in ASSIGNMENT_SEEDS:
        if any(needle in assign or needle in body for needle in needles):
            for topic, why in follow:
                add(topic, why)

    for needles, topic in PAGE_HINTS:
        if any(needle in body for needle in needles):
            add(topic, f"В тексте есть {needles[0]} — без этого задание не собрать.")

    return chosen[:limit]
