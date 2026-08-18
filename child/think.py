from __future__ import annotations

import re
from dataclasses import dataclass

from child.ingest import clean_web_text, is_code_junk, is_weak_note, is_web_junk
from child.memory import load_brain_lines

# Weak prior for a few trades. Real next steps come from how the page links ideas.
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

PAGE_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("php", "пхп"), "PHP"),
    (("javascript", "java script", "js "), "JavaScript"),
    (("python", "питон"), "Python"),
    (("rest api", "rest-api", "вебхук", "webhook"), "REST API"),
    (("mysql", "база данных", "sql"), "SQL"),
)

# Mentioned everywhere. Follow only if the page says the topic is built with them.
GENERIC_CRAFTS = {
    "javascript",
    "python",
    "html",
    "css",
    "java",
    "rest api",
    "sql",
}

STRUCTURE_MARKERS = (
    "как устроен",
    "как устроена",
    "как устроено",
    "как устроены",
    "как работает",
    "как работают",
    "как делается",
    "как делают",
    "how it works",
    "how they",
    "architecture",
    "internals",
    "изнутри",
    "устройств",
)
HOWTO_MARKERS = (
    "как пользоваться",
    "как настроить",
    "как создать",
    "how to",
    "tutorial",
)
WHAT_MARKERS = ("что такое", "what is", "who is")

STOPWORDS = {
    "как",
    "что",
    "это",
    "для",
    "или",
    "the",
    "and",
    "for",
    "how",
    "they",
    "with",
    "from",
    "that",
    "this",
    "его",
    "её",
    "them",
}

GENERIC_CONCEPTS = {
    "software",
    "packages",
    "products",
    "platform",
    "service",
    "tool",
    "инструмент",
    "система",
    "приложение",
    "data",
    "code",
    "код",
    "web",
    "the web",
    "it",
    "them",
    "this",
    "that",
}

LINK_VERBS = (
    "использу",
    "основан",
    "на базе",
    "под капотом",
    "built on",
    "based on",
    "uses ",
    "using ",
    "requires ",
    "runs on",
    "written in",
    "написан",
    "держи",
    "блок",
    "состоит",
    "внутри",
    "через ",
    "via ",
    "с помощью",
    "called ",
    "называ",
)

EXPLAIN_MARKERS = (
    " это ",
    " is ",
    " are ",
    "использу",
    "состоит",
    "позволя",
    "built",
    "uses ",
    "архитектур",
    "внутри",
    "механизм",
    "изолир",
    "контейнер",
    "образ",
)

MECHANISM_MARKS = (
    "uses ",
    "использует",
    "состоит",
    "composed",
    "под капотом",
    "internal",
    "архитектур",
    "snapshot",
    "content-address",
    "kernel",
    "protocol",
    "протокол",
    "isolat",
    "hash",
    "blob",
    "commit",
    "namespace",
    "cgroup",
    "object database",
)

HISTORY_MARKS = (
    "created by",
    "originally",
    "often used",
    "collaboratively",
    "was invented",
    "в 19",
    "в 20",
)

_LINK_AFTER = (
    r"(?:uses|using|via|requires|based on|built on|runs on|written in)\s+",
    r"(?:использует|используют|на базе|основан[аоы]?\s+на|под капотом|с помощью|через|"
    r"написан[ао]?\s+на|держи[тть]\s+блоки|блоки)\s+",
)


@dataclass(frozen=True)
class Assignment:
    raw: str
    topic: str
    intent: str


def _norm(text: str) -> str:
    return " " + text.casefold().replace("ё", "е") + " "


def _tokens(text: str) -> set[str]:
    raw = {
        part
        for part in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text.casefold().replace("ё", "е"))
        if len(part) > 2 and part not in STOPWORDS
    }
    extra = {part[:5] for part in raw if len(part) >= 5}
    return raw | extra


def _sentences(text: str) -> list[str]:
    blob = clean_web_text(text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", blob)
    return [" ".join(part.split()).strip() for part in parts if part.strip()]


def parse_assignment(text: str) -> Assignment:
    raw = " ".join(text.split()).strip()
    low = raw.casefold()
    intent = "what"
    if any(marker in low for marker in STRUCTURE_MARKERS):
        intent = "structure"
    elif any(marker in low for marker in HOWTO_MARKERS):
        intent = "howto"
    topic = raw
    for marker in STRUCTURE_MARKERS + HOWTO_MARKERS + WHAT_MARKERS:
        idx = topic.casefold().find(marker)
        if idx >= 0:
            topic = (topic[:idx] + " " + topic[idx + len(marker) :]).strip()
    topic = " ".join(topic.split()).strip(" :,.-") or raw
    return Assignment(raw=raw, topic=topic, intent=intent)


def search_queries(text: str) -> list[str]:
    parsed = parse_assignment(text)
    topic = parsed.topic
    queries: list[str] = []
    if parsed.intent == "structure":
        queries.extend(
            (
                f"{topic} architecture",
                f"{topic} internals",
                f"{topic} как устроен",
            )
        )
    queries.extend((parsed.raw, topic, f"{topic} site:wikipedia.org"))
    out: list[str] = []
    seen: set[str] = set()
    for item in queries:
        key = " ".join(item.split()).casefold()
        if not item.strip() or key in seen:
            continue
        seen.add(key)
        out.append(" ".join(item.split()))
    return out[:4]


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


def hit_score(title: str, url: str, assignment: str) -> int:
    """Prefer encyclopedia and docs; downrank beginner listicles."""
    parsed = parse_assignment(assignment)
    blob = f"{title} {url}".casefold()
    host = ""
    path = blob
    match = re.search(r"https?://([^/]+)(/[^\s]*)?", url.casefold())
    if match:
        host = match.group(1)
        path = match.group(2) or ""
    score = 0
    if host.endswith("wikipedia.org"):
        score += 10
        if parsed.intent == "structure":
            score += 4
    if host.startswith("docs.") or "/docs/" in path or "readthedocs" in host:
        score += 4
    for token in _tokens(parsed.topic):
        if len(token) > 3 and token in host:
            score += 3
    if parsed.intent == "structure":
        if any(mark in blob for mark in ("architecture", "internal", "устрой", "how-it-works")):
            score += 5
        if any(
            mark in blob
            for mark in (
                "начинающ",
                "как пользоваться",
                "for beginners",
                "how-to-use",
                "tutorial",
                "get-started",
                "get_started",
                "/overview",
            )
        ):
            score -= 8
    if any(mark in host for mark in ("geeksforgeeks.org", "w3schools.com")):
        score -= 5
    if "habr.com" in host and parsed.intent == "structure":
        score -= 3
    if "course" in blob:
        score -= 4
    return score


def page_score(text: str, assignment: str, url: str = "") -> int:
    parsed = parse_assignment(assignment)
    if is_code_junk(text):
        return -20
    score = hit_score("", url, assignment) if url else 0
    facts = relevant_facts(text, assignment, limit=3)
    score += min(9, 3 * len(facts))
    low = _norm(text)
    if parsed.intent == "structure":
        if has_mechanism(text):
            score += 8
        else:
            score -= 6
        for mark in ("архитектур", "internal", "namespace", "cgroup", "состоит", "использует", "механизм"):
            if mark in low:
                score += 2
        for mark in ("для начинающих", "как пользоваться", "how to install"):
            if mark in low:
                score -= 3
    return score


def relevant_facts(text: str, assignment: str, limit: int = 3) -> list[str]:
    """Sentences that actually speak about the assignment."""
    parsed = parse_assignment(assignment)
    stems = _tokens(parsed.topic) | _tokens(parsed.raw)
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for part in _sentences(text)[:30]:
        if len(part) < 24 or is_web_junk(part) or is_weak_note(part, web=True):
            continue
        key = part.casefold()
        if key in seen:
            continue
        words = _tokens(part)
        overlap = len(stems & words)
        explain = 1 if any(mark in _norm(part) for mark in EXPLAIN_MARKERS) else 0
        if overlap == 0 and not any(stem in part.casefold() for stem in stems):
            continue
        score = overlap * 2 + explain
        if parsed.intent == "structure":
            if any(mark in _norm(part) for mark in MECHANISM_MARKS):
                score += 3
            if any(mark in part.casefold() for mark in HISTORY_MARKS):
                score -= 3
        if score <= 0:
            continue
        seen.add(key)
        scored.append((score, part if len(part) <= 220 else part[:217].rsplit(" ", 1)[0] + "…"))
    scored.sort(key=lambda item: -item[0])
    return [part for _score, part in scored[:limit]]


def _has_link_verb(sentence: str) -> bool:
    low = sentence.casefold()
    return any(verb in low for verb in LINK_VERBS)


def _clean_concept(chunk: str) -> str:
    chunk = re.split(
        r"\s+(?:to|for|чтобы|для|that|which|который|которая|чтобы)\s+",
        chunk,
        maxsplit=1,
    )[0]
    chunk = " ".join(chunk.split()).strip(" .,;:()[]")
    return chunk


def _is_concept(phrase: str) -> bool:
    words = [word for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9+\-]+", phrase) if word]
    if not 1 <= len(words) <= 4:
        return False
    low = phrase.casefold()
    if low in GENERIC_CONCEPTS or low in STOPWORDS:
        return False
    if all(word.casefold() in STOPWORDS for word in words):
        return False
    letters = sum(ch.isalpha() for ch in phrase)
    return letters >= 3


def _concepts_from(sentence: str) -> list[str]:
    found: list[str] = []
    for prefix in _LINK_AFTER:
        match = re.search(prefix + r"(.+?)(?:[.!?]|$)", sentence, flags=re.I)
        if not match:
            continue
        chunk = _clean_concept(match.group(1))
        parts = re.split(r"\s*(?:,|/|;|\band\b|\bи\b|\bas well as\b)\s*", chunk)
        for part in parts:
            part = _clean_concept(part)
            if _is_concept(part):
                found.append(part)
    return found


def _canonicalize(topic: str) -> str:
    low = topic.casefold()
    for needles, name in PAGE_HINTS:
        if any(needle.strip() == low or needle.strip() in f" {low} " for needle in needles):
            return name
        if low == name.casefold():
            return name
    if low == "php":
        return "PHP"
    return topic.strip()


def _strong_craft_link(sentence: str) -> bool:
    low = sentence.casefold()
    return any(
        mark in low
        for mark in (
            "написан",
            "written in",
            "блоки",
            "под капотом",
            "uses ",
            "использует",
            "основан",
            "based on",
        )
    )


def next_topics(assignment: str, page: str, limit: int = 2) -> list[tuple[str, str]]:
    """What is still missing to understand the assignment — not every word on the page."""
    parsed = parse_assignment(assignment)
    assign = _norm(assignment)
    stems = _tokens(parsed.topic) | _tokens(parsed.raw)
    chosen: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(topic: str, why: str) -> None:
        topic = _canonicalize(topic)
        key = topic.casefold()
        if key in seen or key == parsed.raw.casefold() or key == parsed.topic.casefold():
            return
        if key in _norm(parsed.topic) and " " not in topic:
            return
        seen.add(key)
        chosen.append((topic, why))

    for needles, follow in ASSIGNMENT_SEEDS:
        if any(needle in assign for needle in needles):
            for topic, why in follow:
                add(topic, why)

    for sentence in _sentences(page):
        about = any(stem in sentence.casefold() for stem in stems)
        if not about or not _has_link_verb(sentence):
            continue
        why = f"В устройстве «{parsed.topic}» это связано так: {sentence[:160]}"
        for concept in _concepts_from(sentence):
            craft = _canonicalize(concept)
            if craft.casefold() in GENERIC_CRAFTS and not _strong_craft_link(sentence):
                continue
            add(concept, why)
        for needles, name in PAGE_HINTS:
            if any(needle in _norm(sentence) for needle in needles):
                if name.casefold() in GENERIC_CRAFTS and not _strong_craft_link(sentence):
                    continue
                add(name, why)

    return chosen[:limit]


def follow_query(assignment: str, concept: str) -> str:
    """Hunt the gap in the context of the original task, not as a random new subject."""
    parsed = parse_assignment(assignment)
    if concept.casefold() in parsed.topic.casefold():
        return concept
    if parsed.intent == "structure":
        return f"{parsed.topic} {concept}"
    return concept


def has_mechanism(text: str) -> bool:
    for sentence in _sentences(text)[:12]:
        if any(mark in sentence.casefold() for mark in HISTORY_MARKS):
            continue
        if _has_link_verb(sentence):
            return True
        if any(mark in _norm(sentence) for mark in MECHANISM_MARKS):
            return True
    return False


def needs_deeper(assignment: str, page: str) -> bool:
    """A definition is not an answer to «как устроен»."""
    if parse_assignment(assignment).intent != "structure":
        return False
    if next_topics(assignment, page, limit=1):
        return False
    return not has_mechanism(page)


def deeper_query(assignment: str) -> str:
    topic = parse_assignment(assignment).topic
    return f"{topic} internals"
