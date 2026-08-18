from __future__ import annotations

import ipaddress
import json
import re
import socket
from html import unescape
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from child.ingest import split_practice_lines

MAX_BYTES = 120_000
WEB_DIR = Path("data/web")
USER_AGENT = "ExpChild/0.2 (self-study; +https://github.com/J3ckJ/Exp)"
SEARCH_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)

BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.google.com",
}
BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home", ".corp")
SKIP_RESULT_HOSTS = {
    "duckduckgo.com",
    "html.duckduckgo.com",
    "lite.duckduckgo.com",
    "google.com",
    "www.google.com",
    "bing.com",
    "www.bing.com",
    "yandex.ru",
    "yandex.com",
    "ya.ru",
}
DOCS_HINTS = {
    "bitrix": (
        "site:dev.1c-bitrix.ru",
        "site:helpdesk.bitrix24.ru",
        "site:academy.1c-bitrix.ru",
    ),
    "php": ("site:www.php.net",),
    "python": ("site:docs.python.org",),
    "docker": ("site:docs.docker.com",),
    "git": ("site:git-scm.com",),
    "http": ("site:developer.mozilla.org",),
    "dns": ("site:en.wikipedia.org",),
}

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
    "docker": (
        "https://en.wikipedia.org/api/rest_v1/page/summary/Docker_(software)",
        "https://ru.wikipedia.org/api/rest_v1/page/summary/Docker",
    ),
    "git": (
        "https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1&format=json&titles=Git",
        "https://raw.githubusercontent.com/progit/progit2/main/book/10-git-internals/sections/objects.asc",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Git",
    ),
    "http": (
        "https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1&format=json&titles=HTTP",
        "https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Messages",
        "https://en.wikipedia.org/api/rest_v1/page/summary/HTTP",
    ),
    "dns": (
        "https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1&format=json&titles=Domain_Name_System",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Domain_Name_System",
    ),
    "general": (
        "https://simple.wikipedia.org/api/rest_v1/page/summary/Learning",
    ),
}

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
    "docker": "Docker",
    "git": "Git",
    "http": "HTTP",
    "dns": "Domain Name System",
    "python": "Python",
    "english": "English language",
    "russian": "Русский язык",
    "world": "Земля",
    "github": "GitHub",
}


def _hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower().rstrip(".")


def _ip_is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(ip.is_global) and not ip.is_multicast


def host_allowed(url: str) -> bool:
    """Public http(s) only. Not a whitelist: localhost and private nets stay closed."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or host in BLOCKED_HOSTS:
        return False
    if any(host == suf[1:] or host.endswith(suf) for suf in BLOCKED_SUFFIXES):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return _ip_is_public(ip)


def _resolved_public(url: str) -> bool:
    if not host_allowed(url):
        return False
    host = _hostname(url)
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not _ip_is_public(ip):
            return False
    return True


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if not _resolved_public(newurl):
            raise URLError(f"blocked redirect: {newurl}")
        return HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl
        )


def encode_url(url: str) -> str:
    parts = urlsplit(url)
    path = quote(unquote(parts.path), safe="/")
    query = quote(unquote(parts.query), safe="=&")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
    raw = re.sub(
        r"(?is)<(script|style|noscript|svg|nav|footer|header|form|iframe|aside)[^>]*>.*?</\1>",
        " ",
        raw,
    )
    raw = re.sub(r"(?is)<script[^>]*>.*", " ", raw)
    raw = re.sub(
        r"(?is)<table\b[^>]*class=\"[^\"]*(?:infobox|navbox|sidebar)[^\"]*\"[^>]*>.*?</table>",
        " ",
        raw,
    )
    raw = re.sub(r"(?is)</?(p|div|li|h1|h2|h3|h4|tr|section|article|br)[^>]*>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = unescape(raw)
    text = re.sub(r"\{\{[^}]{0,400}\}\}", " ", text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _fetch_raw(url: str, user_agent: str = USER_AGENT) -> tuple[str, str, str]:
    """Return text, content-type, final url."""
    if not _resolved_public(url):
        raise ValueError(f"Host not allowed: {url}")
    request = Request(encode_url(url), headers={"User-Agent": user_agent})
    opener = build_opener(_SafeRedirect)
    with opener.open(request, timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
        ctype = response.headers.get("Content-Type", "")
        final = response.geturl() or url
    if not _resolved_public(final):
        raise ValueError(f"Host not allowed: {final}")
    if len(data) > MAX_BYTES:
        data = data[:MAX_BYTES]
    text = data.decode("utf-8", errors="replace")
    return text, ctype, final


def fetch_url(url: str) -> str:
    text, ctype, final = _fetch_raw(url)
    if "json" in ctype or "/page/summary/" in final or "action=query" in final or "action=query" in url:
        try:
            payload = json.loads(text)
            extracted = _json_extract(payload)
            if extracted:
                return extracted
            return text
        except json.JSONDecodeError:
            pass
    if "<html" in text[:2000].casefold() or "</p>" in text.casefold():
        return strip_html(text)
    return text


def _json_extract(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    extract = payload.get("extract")
    if isinstance(extract, str) and extract.strip():
        return extract
    pages = payload.get("query", {}).get("pages")
    if isinstance(pages, dict):
        for page in pages.values():
            if not isinstance(page, dict):
                continue
            extract = page.get("extract")
            if isinstance(extract, str) and extract.strip():
                return extract
    return ""


def urls_in_text(text: str) -> list[str]:
    found = re.findall(r"https?://[^\s)>\"]+", text)
    cleaned: list[str] = []
    for url in found:
        url = url.rstrip(".,;]")
        if host_allowed(url) and url not in cleaned:
            cleaned.append(url)
    return cleaned


def wiki_extract_url(title: str, lang: str) -> str:
    host = f"{lang}.wikipedia.org"
    return (
        f"https://{host}/w/api.php?action=query&prop=extracts&explaintext=1"
        f"&redirects=1&format=json&titles={quote(title)}"
    )


def wiki_summary_url(title: str, lang: str) -> str:
    return f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"


def as_readable_url(url: str, *, summary: bool = True) -> str:
    """Summary for «what is»; plain-text article extract for «how it is built»."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    rewritten = _progit_raw(url)
    if rewritten:
        return rewritten
    match = re.match(r"^(ru|en|simple)\.wikipedia\.org$", host)
    if match and ("/wiki/" in parsed.path or "/page/summary/" in parsed.path):
        if "/wiki/" in parsed.path:
            title = unquote(parsed.path.split("/wiki/", 1)[1])
        else:
            title = unquote(parsed.path.rsplit("/", 1)[-1])
        title = title.split("#", 1)[0]
        if title and not title.startswith(("Special:", "File:", "Служебная:")):
            lang = match.group(1)
            if summary:
                return wiki_summary_url(title, lang)
            return wiki_extract_url(title, lang)
    return url


_PROGIT_SECTIONS = {
    "git-internals-git-objects": (
        "https://raw.githubusercontent.com/progit/progit2/main/"
        "book/10-git-internals/sections/objects.asc"
    ),
    "git-internals-plumbing-and-porcelain": (
        "https://raw.githubusercontent.com/progit/progit2/main/"
        "book/10-git-internals/sections/plumbing-porcelain.asc"
    ),
}


def _progit_raw(url: str) -> str:
    path = urlparse(url).path.rstrip("/").casefold()
    slug = path.rsplit("/", 1)[-1]
    return _PROGIT_SECTIONS.get(slug, "")


def _result_host_ok(url: str) -> bool:
    host = _hostname(url)
    if not host or not host_allowed(url):
        return False
    if host in SKIP_RESULT_HOSTS or any(
        host.endswith("." + skipped) for skipped in SKIP_RESULT_HOSTS
    ):
        return False
    return True


def _unwrap_result_url(url: str) -> str:
    url = unescape(url.strip())
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "uddg" in qs and qs["uddg"]:
        url = unquote(qs["uddg"][0])
    return url


def parse_search_html(html: str) -> list[tuple[str, str]]:
    """Pull (title, url) out of a search-engine results page."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    ):
        url = _unwrap_result_url(match.group(1))
        title = " ".join(strip_html(match.group(2)).split())
        if not _result_host_ok(url) or url in seen:
            continue
        seen.add(url)
        found.append((title or url, url))
    for encoded in re.findall(r"[?&]uddg=([^&\"']+)", html):
        url = _unwrap_result_url("https://duckduckgo.com/l/?uddg=" + encoded)
        if not _result_host_ok(url) or url in seen:
            continue
        seen.add(url)
        found.append((url, url))
    return found


def web_search(query: str, limit: int = 5) -> list[tuple[str, str]]:
    query = " ".join(query.split())
    if not query:
        return []
    endpoints = (
        f"https://html.duckduckgo.com/html/?q={quote(query)}",
        f"https://lite.duckduckgo.com/lite/?q={quote(query)}",
    )
    for url in endpoints:
        try:
            html, _ctype, _final = _fetch_raw(url, user_agent=SEARCH_UA)
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            print(f"skip search {url}: {exc}")
            continue
        hits = parse_search_html(html)
        if hits:
            return hits[:limit]
    return []


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
        if word.casefold() in {"internals", "architecture", "structure", "overview"}:
            continue
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
    from child.think import wiki_title_fits

    ranked = sorted(
        enumerate(titles),
        key=lambda item: (_title_score(query, item[1]), -item[0]),
        reverse=True,
    )
    for _index, title in ranked:
        if wiki_title_fits(title, query):
            return title
    return ""


def topic_from_query(query: str) -> str:
    low = query.casefold()
    if any(word in low for word in ("github", "гитхаб")):
        return "github"
    if any(word in low for word in ("php", "пхп")):
        return "php"
    if re.search(r"(?<![a-zа-яё])https?(?![a-zа-яё])", low):
        return "http"
    if re.search(r"(?<![a-zа-яё])dns(?![a-zа-яё])|domain name", low):
        return "dns"
    if re.search(r"(?<![a-zа-яё])git(?![a-zа-яё])", low):
        return "git"
    if "docker" in low:
        return "docker"
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


def wiki_fulltext_hits(query: str, limit: int = 5) -> list[tuple[str, str]]:
    """Wikipedia's own search — works when DuckDuckGo returns an empty shell."""
    query = " ".join(query.split())
    if not query:
        return []
    langs = ("ru", "en") if re.search(r"[А-Яа-яЁё]", query) else ("en", "ru")
    from child.think import wiki_title_fits

    for lang in langs:
        url = (
            f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={quote(query)}&srlimit={limit}&format=json"
        )
        try:
            raw = fetch_url(url)
            payload: Any = json.loads(raw) if raw.lstrip().startswith("{") else {}
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            continue
        rows = payload.get("query", {}).get("search") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        hits: list[tuple[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title or not wiki_title_fits(title, query):
                continue
            hits.append((title, wiki_extract_url(title, lang)))
            if len(hits) >= limit:
                break
        if hits:
            return hits
    return []


def hunt_urls(query: str, limit: int = 5, *, summary: bool = True) -> list[tuple[str, str]]:
    """Search the public web, then Wikipedia. Official docs get an extra query."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(title: str, url: str) -> None:
        url = as_readable_url(url.rstrip(".,;]"), summary=summary)
        if not host_allowed(url) or url in seen:
            return
        seen.add(url)
        found.append((title.strip() or url, url))

    queries = [query]
    topic = topic_from_query(query)
    for hint in DOCS_HINTS.get(topic, ()):
        queries.append(f"{query} {hint}")
    for item in queries:
        for title, url in web_search(item, limit=limit):
            add(title, url)
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break
    for title, url in wiki_fulltext_hits(query, limit=limit):
        add(title, url)
    title = wiki_search(query)
    if title:
        langs = ("ru", "en") if re.search(r"[А-Яа-яЁё]", query) else ("en", "ru")
        for lang in langs:
            add(title, wiki_summary_url(title, lang) if summary else wiki_extract_url(title, lang))
    return found[: max(limit, len(found))][: limit + 4]


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
        lines = split_practice_lines(text)[:40]
        cleaned = "\n".join(lines) if lines else " ".join(text.split())[:4000]
        if len(cleaned) < 40:
            continue
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", urlparse(url).path).strip("-")[:40]
        path = WEB_DIR / f"{topic}-{slug or 'page'}.txt"
        path.write_text(cleaned, encoding="utf-8")
        found.append(path)
        print(f"fetched {url} -> {path} ({len(cleaned)} chars)")
    return found
