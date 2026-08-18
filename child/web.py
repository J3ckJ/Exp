from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ALLOWED_HOSTS = (
    "ru.wikipedia.org",
    "en.wikipedia.org",
    "simple.wikipedia.org",
    "docs.python.org",
    "raw.githubusercontent.com",
)

MAX_BYTES = 80_000
WEB_DIR = Path("data/web")
USER_AGENT = "ExpChild/0.1 (self-study; educational)"


TOPIC_PAGES: dict[str, tuple[str, ...]] = {
    "python": (
        "https://en.wikipedia.org/api/rest_v1/page/summary/Python_(programming_language)",
        "https://simple.wikipedia.org/api/rest_v1/page/summary/Python_(programming_language)",
    ),
    "english": (
        "https://simple.wikipedia.org/api/rest_v1/page/summary/English_language",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Hello",
    ),
    "russian": (
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Русский_язык",
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Мама",
    ),
    "world": (
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Земля",
        "https://simple.wikipedia.org/api/rest_v1/page/summary/Earth",
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Москва",
        "https://simple.wikipedia.org/api/rest_v1/page/summary/Sun",
        "https://simple.wikipedia.org/api/rest_v1/page/summary/Water",
    ),
    "github": (
        "https://raw.githubusercontent.com/python/peps/main/peps/pep-0020.rst",
    ),
    "bitrix": (
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Битрикс24",
        "https://ru.wikipedia.org/api/rest_v1/page/summary/CRM",
    ),
    "php": (
        "https://ru.wikipedia.org/api/rest_v1/page/summary/PHP",
        "https://simple.wikipedia.org/api/rest_v1/page/summary/PHP",
    ),
    "general": (
        "https://simple.wikipedia.org/api/rest_v1/page/summary/Learning",
    ),
}


def host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def encode_url(url: str) -> str:
    parts = urlsplit(url)
    path = quote(unquote(parts.path), safe="/")
    query = quote(unquote(parts.query), safe="=&")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return unescape(raw)


def fetch_url(url: str) -> str:
    if not host_allowed(url):
        raise ValueError(f"Host not allowed: {url}")
    request = Request(encode_url(url), headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
        ctype = response.headers.get("Content-Type", "")
    if len(data) > MAX_BYTES:
        data = data[:MAX_BYTES]
    text = data.decode("utf-8", errors="replace")
    if "json" in ctype or "/page/summary/" in url:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                extract = payload.get("extract")
                if isinstance(extract, str) and extract.strip():
                    return extract
            return text
        except json.JSONDecodeError:
            pass
    if "<html" in text[:1000].casefold() or "</p>" in text.casefold():
        return strip_html(text)
    return text


def urls_in_text(text: str) -> list[str]:
    found = re.findall(r"https://[^\s)>\"]+", text)
    cleaned: list[str] = []
    for url in found:
        url = url.rstrip(".,;]")
        if host_allowed(url) and url not in cleaned:
            cleaned.append(url)
    return cleaned


STOPWORDS = {
    "в",
    "во",
    "на",
    "и",
    "или",
    "для",
    "как",
    "про",
    "при",
    "the",
    "a",
    "an",
    "of",
    "in",
    "and",
    "for",
    "how",
    "they",
}

TOPIC_SEARCH = {
    "bitrix": "Битрикс24",
    "php": "PHP",
    "python": "Python",
    "english": "English language",
    "russian": "Русский язык",
    "world": "Земля",
    "github": "GitHub",
}


def query_variants(query: str) -> list[str]:
    """Whole phrase first, then product name, then stemmed words."""
    cleaned = " ".join(query.split())
    variants: list[str] = []
    topic = topic_from_query(query)
    if topic in TOPIC_SEARCH:
        variants.append(TOPIC_SEARCH[topic])
    if cleaned:
        variants.append(cleaned)
    tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", cleaned)
    words = [tok for tok in tokens if len(tok) > 2 and tok.casefold() not in STOPWORDS]
    if words:
        variants.append(" ".join(words))
    for word in sorted(set(words), key=len, reverse=True):
        variants.append(word)
        if len(word) > 5 and word[-1].casefold() in "аеёиоуыэюяйьъ":
            variants.append(word[:-1])
    out: list[str] = []
    seen: set[str] = set()
    for item in variants:
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _opensearch(query: str, limit: int) -> list[str]:
    langs = ("ru", "en") if re.search(r"[А-Яа-яЁё]", query) else ("en", "ru")
    for lang in langs:
        host = f"{lang}.wikipedia.org"
        url = (
            f"https://{host}/w/api.php?action=opensearch&search={quote(query)}"
            f"&limit={limit}&format=json"
        )
        try:
            raw = fetch_url(url)
            payload: Any = json.loads(raw)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, list) and len(payload) >= 2 and isinstance(payload[1], list):
            titles = [str(item) for item in payload[1] if str(item).strip()]
            if titles:
                return titles
    return []


def wiki_search_titles(query: str, limit: int = 5) -> list[str]:
    query = " ".join(query.split())
    if not query:
        return []
    for variant in query_variants(query):
        titles = _opensearch(variant, limit)
        if titles:
            return titles
    return []


def _title_score(query: str, title: str) -> int:
    q = query.casefold().replace("ё", "е")
    t = title.casefold().replace("ё", "е")
    score = 0
    for token in re.findall(r"[a-zа-я0-9]+", q):
        if len(token) < 3:
            continue
        stem = token[:5]
        if token in t or stem in t:
            score += 2
        if t in token:
            score += 1
    if any(mark in q for mark in ("црм", "crm")) and "24" in t:
        score += 3
    return score


def wiki_search(query: str) -> str:
    titles = wiki_search_titles(query)
    if not titles:
        return ""
    ranked = sorted(
        enumerate(titles),
        key=lambda item: (_title_score(query, item[1]), -item[0]),
        reverse=True,
    )
    return ranked[0][1]


def topic_from_query(query: str) -> str:
    low = query.casefold()
    if any(word in low for word in ("github", "гитхаб")):
        return "github"
    if any(word in low for word in ("php", "пхп")):
        return "php"
    if any(word in low for word in ("битрикс", "bitrix", "црм", "crm")):
        return "bitrix"
    if any(word in low for word in ("python", "питон")):
        return "python"
    if any(word in low for word in ("english", "английск")):
        return "english"
    if any(word in low for word in ("русск", "russian")):
        return "russian"
    if any(word in low for word in ("мир", "world", "земл", "москв")):
        return "world"
    return ""


def urls_for_wish(topic: str, extra_urls: Sequence[str]) -> list[str]:
    urls = list(TOPIC_PAGES.get(topic, TOPIC_PAGES["general"]))
    for url in extra_urls:
        if host_allowed(url) and url not in urls:
            urls.append(url)
    return urls[:6]


def fetch_wish_texts(topic: str, extra_urls: Sequence[str] = ()) -> list[Path]:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    found: list[Path] = []
    for url in urls_for_wish(topic, extra_urls):
        try:
            text = fetch_url(url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            print(f"skip {url}: {exc}")
            continue
        cleaned = " ".join(text.split())
        if len(cleaned) < 40:
            continue
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", urlparse(url).path).strip("-")[:40]
        path = WEB_DIR / f"{topic}-{slug or 'page'}.txt"
        path.write_text(text, encoding="utf-8")
        found.append(path)
        print(f"fetched {url} -> {path} ({len(text)} chars)")
    return found
