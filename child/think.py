from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

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
    "blog",
    "conclusion",
    "workflow",
    "home",
    "menu",
    "docs",
    "directory",
    "once again",
    "programming languages",
    "key programming languages",
    "architecture",
    "wikipedia",
    "internals",
    "certain",
    "additional",
    "common",
    "standard",
    "decimal",
    "query",
    "octets",
    "storage",
    "cryptography",
    "cryptology",
    "расширение",
}

# Encyclopedia articles named after a generic word, not the product.
WIKI_TRAPS = {
    "architecture",
    "wikipedia",
    "working",
    "software",
    "computer",
    "internet",
    "blog",
    "language",
    "internals",
    "github",
    "gcc",
    "gnu compiler collection",
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
    "protocol",
    "протокол",
    "isolat",
    "hash",
    "blob",
    "commit",
    "namespace",
    "cgroup",
    "object database",
    "local copy",
    "entire repository",
)

DEEP_MARKS = (
    "request-response",
    "request–response",
    "content-address",
    "object database",
    "snapshot",
    "namespace",
    "cgroup",
    "stateless",
    "header",
    "sha-1",
    "sha1",
    "blob",
    "working tree",
    "virtualization",
    "resolver",
    "hierarchical",
    "handshake",
    "asymmetric",
    "symmetric",
    "шифр",
    "сертификат",
    "pki",
    "public key",
    "запрос",
    "заголов",
)

HISTORY_MARKS = (
    "created by",
    "originally",
    "often used",
    "collaboratively",
    "was invented",
    "benchmarked",
    "most commonly used",
    "performance goals",
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
    blob = re.sub(r"\s+/\s+", ". ", blob)
    blob = re.sub(
        r"\b(Conclusion|Home|Menu|Documentation|Workflow)\b",
        ".",
        blob,
    )
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
                f"{topic} site:wikipedia.org",
                f"{topic} internals",
                f"{topic} how it works",
                f"{topic} architecture",
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


TITLE_ALIASES = {
    "tls": ("transport layer security", "ssl"),
    "ssl": ("transport layer security", "tls"),
    "http": ("hypertext transfer protocol",),
    "dns": ("domain name system",),
}

GENERIC_HUNT = {
    "internal",
    "internals",
    "architecture",
    "structure",
    "overview",
    "working",
    "wikipedia",
    "устроен",
    "устроена",
    "устроено",
    "устроены",
    "устройство",
    "procedure",
    "protocol",
    "version",
}


def _product_tokens(text: str) -> set[str]:
    words = {
        part
        for part in re.findall(r"[a-zа-яё0-9]+", text.casefold().replace("ё", "е"))
        if len(part) > 2 and part not in STOPWORDS and part not in GENERIC_HUNT
    }
    extra = {part[:5] for part in words if len(part) >= 6}
    return words | extra


def _beyond_known_product(text: str) -> set[str]:
    """Extra tokens after a known acronym: 'TLS handshake' but not 'как устроен TLS'."""
    if not text:
        return set()
    low = text.casefold()
    for key, aliases in TITLE_ALIASES.items():
        if not re.search(r"(?<![a-zа-яё])" + re.escape(key) + r"(?![a-zа-яё])", low):
            continue
        extra = _product_tokens(text) - {key} - _product_tokens(" ".join(aliases)) - GENERIC_HUNT
        return {token for token in extra if len(token) > 3}
    return set()


def _stems_overlap(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    for item in left:
        for other in right:
            if item in other or other in item:
                return True
            if len(item) >= 5 and len(other) >= 5 and item[:5] == other[:5]:
                return True
    return False


def wiki_page_key(url: str) -> str:
    """Same Wikipedia article under titles=Git and titles=Git%20 is one page."""
    slug = _wiki_slug(url)
    if not slug:
        return url.rstrip("/")
    host = urlparse(url).netloc.casefold()
    return f"{host}::{slug.casefold().replace('_', ' ')}"


def wiki_title_fits(title: str, assignment: str, query: str = "") -> bool:
    """Skip encyclopedia articles named after a generic word, not the product."""
    if not title:
        return False
    low = title.casefold().strip()
    parsed = parse_assignment(assignment)
    topic = parsed.topic.casefold()
    if low in WIKI_TRAPS:
        return low == topic or any(part == low for part in topic.split())
    hunt = query or assignment
    extra = _beyond_known_product(hunt) | _beyond_known_product(query)
    title_tokens = _product_tokens(title)
    if extra and not _stems_overlap(extra, title_tokens):
        return False
    if " " not in title.strip():
        product = (
            _product_tokens(parsed.topic)
            | _product_tokens(parse_assignment(query or assignment).topic)
            | _product_tokens(query)
        )
        if not product:
            return True
        return bool(product & title_tokens) or any(
            token in low for token in product if len(token) > 3
        )
    product = (
        _product_tokens(parsed.topic)
        | _product_tokens(parse_assignment(query or assignment).topic)
        | _product_tokens(query)
    )
    if not product:
        return True
    if product & title_tokens:
        return True
    for key, aliases in TITLE_ALIASES.items():
        if key in product or key == topic:
            if any(alias in low for alias in aliases) or key in low:
                return True
    return False


def _tidy_fact(part: str, topic: str) -> str:
    """Drop a trailing echo of the topic glued on by page headings."""
    part = re.sub(r"\[\s*\d+\s*\]", " ", part)
    part = re.sub(r"\s*\((?:see|см\.)\s*§[^)]*\)", " ", part, flags=re.I)
    topic = " ".join(topic.split()).strip()
    if topic:
        part = re.sub(r"\s+" + re.escape(topic) + r"\s*[.]*$", "", part, flags=re.I)
    part = " ".join(part.split()).strip(" .")
    if part and part[-1] not in ".!?":
        part += "."
    return part


def _wiki_slug(url: str) -> str:
    parsed = urlparse(url) if "://" in url else None
    if parsed and parsed.query:
        titles = parse_qs(parsed.query).get("titles") or []
        if titles and titles[0]:
            return unquote(titles[0]).replace("_", " ").strip()
    match = re.search(r"(?:/wiki/|/page/summary/)([^/?#]+)", url)
    if not match:
        return ""
    return unquote(match.group(1)).replace("_", " ").strip()


def hit_score(title: str, url: str, assignment: str, query: str = "") -> int:
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
    slug = _wiki_slug(url) or title
    if host.endswith("wikipedia.org") and not wiki_title_fits(slug, assignment, query):
        return -40
    wiki_lang = ""
    wmatch = re.match(r"^([a-z]{2,3})\.wikipedia\.org$", host)
    if wmatch:
        wiki_lang = wmatch.group(1)
        if wiki_lang not in {"en", "ru", "simple"}:
            score -= 25
    if host.endswith("wikipedia.org"):
        score += 10
        if parsed.intent == "structure":
            score += 4
        topic_low = parsed.topic.casefold()
        title_low = title.casefold().strip()
        slug_low = slug.casefold().replace("_", " ")
        if title_low == topic_low or title_low == topic_low.replace(" ", "_"):
            score += 8
        product = _product_tokens(parsed.topic) | _product_tokens(query)
        for key, aliases in TITLE_ALIASES.items():
            if key not in product and key != topic_low:
                continue
            if any(alias in slug_low or alias in title_low for alias in aliases):
                score += 10
        if title_low.startswith("list of") or re.search(r"\b\d{3}\b", title_low):
            score -= 12
        if "internal" in parsed.raw.casefold() and "internal" not in blob:
            score -= 8
    if host.startswith("docs.") or "/docs/" in path or "readthedocs" in host:
        score += 4
    if "/blog/" in path or host.startswith("blog.") or "/blog." in host:
        if parsed.intent == "structure":
            score -= 8
    for token in _tokens(parsed.topic):
        if len(token) > 3 and token in host:
            score += 3
    if parsed.intent == "structure":
        if any(mark in blob for mark in ("architecture", "internal", "устрой", "how-it-works", "plumbing")):
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
    if any(host.endswith(item) for item in ("git-scm.com", "php.net", "docs.docker.com", "mozilla.org")):
        score += 6
    if "course" in blob:
        score -= 4
    return score


def page_score(text: str, assignment: str, url: str = "", query: str = "") -> int:
    parsed = parse_assignment(assignment)
    if is_code_junk(text):
        return -20
    score = hit_score("", url, assignment, query) if url else 0
    facts = relevant_facts(text, assignment, limit=3)
    if not facts and query and query.casefold() != assignment.casefold():
        facts = relevant_facts(text, query, limit=3)
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
    window = 100 if parsed.intent == "structure" else 30
    for part in _sentences(text)[:window]:
        if len(part) < 24 or is_web_junk(part) or is_weak_note(part, web=True):
            continue
        key = part.casefold()
        if key in seen:
            continue
        words = _tokens(part)
        overlap = len(stems & words)
        explain = 1 if any(mark in _norm(part) for mark in EXPLAIN_MARKERS) else 0
        if overlap == 0 and not any(_has_stem(part, stem) for stem in stems):
            continue
        part = _tidy_fact(part, parsed.topic)
        if is_weak_note(part, web=True):
            continue
        score = overlap * 2 + explain
        if parsed.intent == "structure":
            if any(mark in _norm(part) for mark in DEEP_MARKS):
                score += 8
            if any(mark in _norm(part) for mark in MECHANISM_MARKS):
                score += 4
            if any(mark in part.casefold() for mark in HISTORY_MARKS):
                score -= 8
            if re.search(r"\b(?:19|20)\d{2}\b|\b\d{1,2}\s+(?:January|April|June|July)\b", part):
                score -= 6
            if any(
                mark in part.casefold()
                for mark in ("our article", "this article", "this post", "overview of")
            ):
                score -= 6
        if score <= 0:
            continue
        seen.add(key)
        scored.append((score, part if len(part) <= 220 else part[:217].rsplit(" ", 1)[0] + "…"))
    scored.sort(key=lambda item: -item[0])
    return [part for _score, part in scored[:limit]]


def _has_stem(text: str, stem: str) -> bool:
    if not stem:
        return False
    return re.search(r"(?i)\b" + re.escape(stem) + r"\b", text) is not None


def _has_link_verb(sentence: str) -> bool:
    low = sentence.casefold()
    return any(verb in low for verb in LINK_VERBS)


def _clean_concept(chunk: str) -> str:
    chunk = re.split(
        r"\s+(?:to|for|чтобы|для|that|which|который|которая|чтобы)\s+",
        chunk,
        maxsplit=1,
    )[0]
    chunk = re.split(r"\s*\(|\s*§|\s+(?:see|см\.)\s+", chunk, maxsplit=1)[0]
    chunk = " ".join(chunk.split()).strip(" .,;:()[]")
    return chunk


def _is_concept(phrase: str) -> bool:
    words = [word for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9+\-]+", phrase) if word]
    if not 1 <= len(words) <= 4:
        return False
    low = phrase.casefold()
    if "§" in phrase or low.startswith(("some ", "see ", "for example")):
        return False
    if low in GENERIC_CONCEPTS or low in STOPWORDS or low in WIKI_TRAPS:
        return False
    if any(low == item or item in low for item in ("blog", "conclusion", "programming languages")):
        return False
    if all(word.casefold() in STOPWORDS for word in words):
        return False
    filler = {
        "some",
        "several",
        "various",
        "certain",
        "additional",
        "such",
        "many",
        "any",
        "example",
    }
    if words[0].casefold() in filler:
        return False
    if words[0][:1].isdigit():
        return False
    lowered = {word.casefold() for word in words}
    if "mail" in lowered and "news" in lowered:
        return False
    if any(
        token in lowered
        for token in (
            "command",
            "commands",
            "perfect",
            "tutorial",
            "article",
            "click",
            "must",
            "imap",
            "pop3",
        )
    ):
        return False
    if re.match(
        r"(?i)git\s+(clone|init|push|pull|commit|add|status|gc|fsck|fetch|merge|rebase)\b",
        low,
    ):
        return False
    if any(token in lowered for token in ("several", "scripts")):
        return False
    if len(words) >= 3 and sum(word[:1].isupper() for word in words) >= 3:
        return False
    letters = sum(ch.isalpha() for ch in phrase)
    return letters >= 3


def _concepts_from(sentence: str, topic_stems: set[str] | None = None) -> list[str]:
    found: list[str] = []
    stems = topic_stems or set()
    for prefix in _LINK_AFTER:
        match = re.search(prefix + r"(.+?)(?:[.!?]|$)", sentence, flags=re.I)
        if not match:
            continue
        collected: list[str] = []
        chunk = _clean_concept(match.group(1).split(",")[0])
        for word in chunk.split():
            plain = word.strip(".,;:").casefold()
            if plain in {"/", "|", "blog", "conclusion", "workflow", "home", "menu"}:
                break
            if any(_has_stem(word, stem) for stem in stems) and collected:
                break
            if plain in {"a", "an", "the"}:
                continue
            collected.append(word)
            if len(collected) >= 4:
                break
        part = " ".join(collected)
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
        if parsed.topic and key.startswith(parsed.topic.casefold() + " "):
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
        if sentence.count(",") >= 4:
            continue
        if "{{" in sentence or any(
            mark in sentence.casefold()
            for mark in ("jump to content", "from wikipedia", "cite web", "not to be confused")
        ):
            continue
        about = any(_has_stem(sentence, stem) for stem in stems)
        if not about or not _has_link_verb(sentence):
            continue
        why = f"В устройстве «{parsed.topic}» это связано так: {_tidy_fact(sentence, parsed.topic)[:160]}"
        for concept in _concepts_from(sentence, stems):
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


def has_depth(text: str) -> bool:
    blob = _norm(text)
    return any(mark in blob for mark in DEEP_MARKS)


def knows_deeply(topic: str) -> bool:
    key = topic.casefold()
    if len(key) < 3:
        return False
    lines = [line for line in load_brain_lines() if key in line.casefold()]
    return has_depth(" ".join(lines))


def has_mechanism(text: str) -> bool:
    seen = 0
    for sentence in _sentences(text)[:40]:
        if any(mark in sentence.casefold() for mark in HISTORY_MARKS):
            continue
        if any(
            mark in sentence.casefold()
            for mark in ("jump to content", "from wikipedia", "cite web")
        ):
            continue
        seen += 1
        if _has_link_verb(sentence):
            return True
        if any(mark in _norm(sentence) for mark in MECHANISM_MARKS):
            return True
        if seen >= 16:
            break
    return False


def needs_deeper(assignment: str, page: str) -> bool:
    """A definition is not an answer to «как устроен» — need the moving parts."""
    if parse_assignment(assignment).intent != "structure":
        return False
    facts = relevant_facts(page, assignment, limit=4)
    if has_depth(" ".join(facts)) or has_depth(page[:4000]):
        return False
    return True


def deeper_query(assignment: str) -> str:
    topic = parse_assignment(assignment).topic
    return f"{topic} internals"
