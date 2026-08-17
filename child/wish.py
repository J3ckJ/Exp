from __future__ import annotations

from dataclasses import dataclass


LEARN_MARKERS = (
    "поучи",
    "выучи",
    "научись",
    "почитай",
    "сам учи",
    "learn",
    "study",
    "go learn",
    "поучись",
)

WEB_MARKERS = (
    "интернет",
    "интернете",
    "github",
    "гитхаб",
    "гитхабе",
    "вики",
    "wikipedia",
    "web",
    "сайт",
    "в сети",
    "онлайн",
    "online",
)


@dataclass(frozen=True)
class Wish:
    raw: str
    topic: str
    use_web: bool
    query: str


def is_learn_command(text: str) -> bool:
    low = text.casefold()
    return any(marker in low for marker in LEARN_MARKERS)


def parse_wish(text: str) -> Wish:
    low = text.casefold()
    use_web = any(marker in low for marker in WEB_MARKERS)
    topic = "general"
    if any(word in low for word in ("python", "питон", "код", "программ", "print(")):
        topic = "python"
    elif any(word in low for word in ("english", "английск", "hello")):
        topic = "english"
    elif any(word in low for word in ("русск", "russian")):
        topic = "russian"
    query = _query_from(text, topic)
    return Wish(raw=text.strip(), topic=topic, use_web=use_web, query=query)


def _query_from(text: str, topic: str) -> str:
    cleaned = text.strip()
    for marker in LEARN_MARKERS + WEB_MARKERS:
        cleaned = _cut(cleaned, marker)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) >= 3:
        return cleaned
    if topic == "python":
        return "Python programming"
    if topic == "english":
        return "English language"
    if topic == "russian":
        return "Русский язык"
    return "learning"


def _cut(text: str, marker: str) -> str:
    low = text.casefold()
    idx = low.find(marker)
    if idx < 0:
        return text
    return (text[:idx] + " " + text[idx + len(marker) :]).strip()
