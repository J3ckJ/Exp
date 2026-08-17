from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
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
        "https://docs.python.org/3/tutorial/introduction.html",
    ),
    "english": (
        "https://simple.wikipedia.org/api/rest_v1/page/summary/English_language",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Hello",
    ),
    "russian": (
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Русский_язык",
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Мама",
    ),
    "general": (
        "https://simple.wikipedia.org/api/rest_v1/page/summary/Learning",
    ),
}


def host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return unescape(raw)


def fetch_url(url: str) -> str:
    if not host_allowed(url):
        raise ValueError(f"Host not allowed: {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
        ctype = response.headers.get("Content-Type", "")
    if len(data) > MAX_BYTES:
        data = data[:MAX_BYTES]
    text = data.decode("utf-8", errors="replace")
    if "json" in ctype or "/page/summary/" in url:
        try:
            payload = json.loads(text)
            extract = payload.get("extract")
            if isinstance(extract, str) and extract.strip():
                return extract
        except json.JSONDecodeError:
            pass
    if "<html" in text[:1000].casefold() or "</p>" in text.casefold():
        return strip_html(text)
    return text


def urls_for_wish(topic: str, extra_urls: Sequence[str]) -> list[str]:
    urls = list(TOPIC_PAGES.get(topic, TOPIC_PAGES["general"]))
    for url in extra_urls:
        if host_allowed(url) and url not in urls:
            urls.append(url)
    return urls[:6]


def fetch_wish_texts(topic: str, extra_urls: Sequence[str] = ()) -> list[tuple[str, str]]:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    found: list[tuple[str, str]] = []
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
        found.append((url, text))
        print(f"fetched {url} -> {path} ({len(text)} chars)")
    return found
