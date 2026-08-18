from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

from urllib.parse import unquote, urlparse

from child.ingest import split_practice_lines
from child.memory import remember
from child.think import next_topics
from child.tools import first_fact, wiki_url
from child.web import fetch_url, host_allowed, topic_from_query, urls_for_wish, urls_in_text, wiki_search

PLAN_PATH = Path("notes/PLAN.md")
MAX_PAGES = 4
MAX_NOTES = 3


def is_research_command(text: str) -> bool:
    low = text.casefold()
    markers = (
        "изучи",
        "разберись",
        "поищи как",
        "найди как",
        "как делают",
        "как делается",
        "прочти книгу",
        "прочитай книгу",
        "вот ссылка",
        "research",
        "investigate",
        "study how",
        "learn how they",
    )
    return any(marker in low for marker in markers)


def mission_query(text: str) -> str:
    cleaned = text.strip()
    for marker in (
        "изучи как делается",
        "изучи как делают",
        "разберись как",
        "поищи как делают",
        "поищи как",
        "найди как делают",
        "найди как",
        "study how",
        "learn how they",
        "изучи",
        "разберись",
        "прочти книгу",
        "прочитай книгу",
        "вот ссылка",
        "research",
        "investigate",
        "в инете",
        "в интернете",
        "в любых ресурсах",
        "пожалуйста",
    ):
        low = cleaned.casefold()
        idx = low.find(marker)
        if idx >= 0:
            cleaned = (cleaned[:idx] + " " + cleaned[idx + len(marker) :]).strip()
    return " ".join(cleaned.split()).strip(" :,.-") or text.strip()


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _note_plan(assignment: str, steps: list[str], follow: list[tuple[str, str]]) -> None:
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for topic, why in follow:
        key = topic.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append((topic, why))
    lines = [
        "# План ребёнка",
        "",
        f"Обновлён {stamp}.",
        "",
        "## Задание",
        "",
        assignment,
        "",
        "## Что сделал сам",
        "",
    ]
    lines.extend(f"- {step}" for step in steps)
    lines.append("")
    if unique:
        lines.append("## Сам решил учить дальше")
        lines.append("")
        lines.extend(f"- {topic}: {why}" for topic, why in unique)
        lines.append("")
    PLAN_PATH.write_text("\n".join(lines), encoding="utf-8")


def _distill(text: str, query: str) -> list[str]:
    if _looks_like_json(text):
        return []
    fact = first_fact(text, query)
    lines = [fact] if fact else []
    fact_low = fact.casefold()
    for line in split_practice_lines(text):
        if line in lines or line.casefold() in fact_low:
            continue
        lines.append(line)
        if len(lines) >= MAX_NOTES:
            break
    return lines


def _page_label(label: str, url: str) -> str:
    generic = {
        "bitrix",
        "php",
        "python",
        "github",
        "general",
        "english",
        "russian",
        "world",
    }
    if label.startswith("http") or label.casefold() in generic:
        slug = unquote(urlparse(url).path).rstrip("/").rsplit("/", 1)[-1]
        if slug:
            return slug.replace("_", " ")
    return label


def _read_topic(query: str, extra_urls: list[str], prefer_ru: bool = False) -> tuple[str, str, str]:
    """Return title, extract, source."""
    tries: list[tuple[str, str]] = []
    for url in extra_urls:
        if host_allowed(url):
            tries.append((url, url))
    title = wiki_search(query)
    if prefer_ru or re.search(r"[А-Яа-яЁё]", query + title):
        langs = ("ru", "en", "simple")
    else:
        langs = ("en", "simple", "ru")
    if title:
        for lang in langs:
            tries.append((title, wiki_url(title, lang)))
    topic = topic_from_query(query)
    if topic:
        for url in urls_for_wish(topic, ()):
            tries.append((topic, url))

    seen_urls: set[str] = set()
    for label, url in tries:
        if url in seen_urls or not host_allowed(url):
            continue
        seen_urls.add(url)
        try:
            text = fetch_url(url)
        except Exception as exc:
            print(f"skip {url}: {exc}")
            continue
        if not text or len(text) < 40 or _looks_like_json(text):
            continue
        return _page_label(label, url), text, url
    return title, "", ""


def run_mission(wish: str) -> str:
    assignment = mission_query(wish)
    extra = urls_in_text(wish)
    print(f"Mission: {assignment!r}")
    log: list[str] = []
    all_follow: list[tuple[str, str]] = []
    queue: list[str] = [assignment]
    seen: set[str] = set()
    pages = 0
    report: list[str] = [f"Задание: {assignment}"]

    while queue and pages < MAX_PAGES:
        query = queue.pop(0)
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        title, extract, source = _read_topic(
            query,
            extra if pages == 0 else [],
            prefer_ru=bool(re.search(r"[А-Яа-яЁё]", assignment)),
        )
        extra = []
        pages += 1
        if not extract:
            log.append(f"не нашёл: {query}")
            report.append(f"Не нашёл страницу про «{query}».")
            continue
        notes = _distill(extract, query)
        for note in notes:
            remember(note)
        why_next = next_topics(assignment if pages == 1 else query, extract)
        all_follow.extend(why_next)
        log.append(f"прочитал «{title}»")
        print(f"read {title} from {source}")
        if notes:
            report.append(f"Прочитал: {title}. {notes[0]}")
        else:
            report.append(f"Прочитал: {title}.")
        if why_next:
            for topic, why in why_next:
                report.append(f"Сам решил: дальше «{topic}». {why}")
                if topic.casefold() not in seen:
                    queue.append(topic)
            log.append("сам пошёл: " + ", ".join(topic for topic, _why in why_next))

    _note_plan(assignment, log, all_follow)
    report.append("Коротко записал в тетрадь и в notes/PLAN.md.")
    return "\n".join(report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hunt a topic, distill it, decide what to learn next."
    )
    parser.add_argument("--wish", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(run_mission(args.wish))


if __name__ == "__main__":
    main()
