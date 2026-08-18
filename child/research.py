from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

from urllib.parse import unquote, urlparse

from child.ingest import is_code_junk, is_toc_junk, is_weak_note, is_web_junk, split_practice_lines
from child.memory import remember
from child.think import (
    already_knows,
    deeper_query,
    follow_query,
    has_mechanism,
    hit_score,
    needs_deeper,
    next_topics,
    page_score,
    parse_assignment,
    relevant_facts,
    search_queries,
    wiki_title_fits,
)
from child.tools import first_fact, wiki_url
from child.web import (
    fetch_url,
    host_allowed,
    hunt_urls,
    topic_from_query,
    urls_for_wish,
    urls_in_text,
    wiki_search,
)

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


def _note_plan(
    assignment: str,
    steps: list[str],
    follow: list[tuple[str, str]],
    understood: list[str] | None = None,
) -> None:
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
    if understood:
        lines.append("## Понял")
        lines.append("")
        lines.extend(f"- {fact}" for fact in understood)
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
    lines = relevant_facts(text, query, limit=MAX_NOTES)
    fact_low = " ".join(lines).casefold()
    if not lines:
        fact = first_fact(text, query)
        if fact and not is_web_junk(fact) and not is_weak_note(fact, web=True):
            lines.append(fact)
            fact_low = fact.casefold()
    for line in split_practice_lines(text):
        if is_web_junk(line) or is_weak_note(line, web=True):
            continue
        if line in lines or line.casefold() in fact_low:
            continue
        lines.append(line)
        if len(lines) >= MAX_NOTES:
            break
    return [line for line in lines if not is_weak_note(line, web=True)][:MAX_NOTES]


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


def _read_topic(
    query: str,
    extra_urls: list[str],
    assignment: str,
    prefer_ru: bool = False,
    skip_urls: set[str] | None = None,
) -> tuple[str, str, str]:
    """Hunt, rank, and pick the page that best answers the assignment."""
    tries: list[tuple[str, str]] = []
    for url in extra_urls:
        if host_allowed(url):
            tries.append((url, url))
    for hunt in search_queries(query)[:3]:
        tries.extend(
            hunt_urls(
                hunt,
                limit=5,
                summary=parse_assignment(assignment).intent != "structure",
            )
        )
    parsed = parse_assignment(query)
    title = ""
    if prefer_ru:
        langs = ("ru", "en", "simple")
    else:
        langs = ("en", "simple", "ru")
    topic = topic_from_query(query) or topic_from_query(parsed.topic)
    if topic:
        for url in urls_for_wish(topic, ()):
            tries.append((topic, url))
    wiki_title = wiki_search(parsed.topic) or wiki_search(query)
    if wiki_title and not wiki_title_fits(wiki_title, assignment):
        print(f"skip unrelated wiki {wiki_title}")
        wiki_title = ""
    full_wiki = parse_assignment(assignment).intent == "structure"
    if wiki_title:
        title = wiki_title
        for lang in langs:
            tries.append((wiki_title, wiki_url(wiki_title, lang, full=full_wiki)))

    tries.sort(key=lambda item: hit_score(item[0], item[1], assignment), reverse=True)
    seen_urls: set[str] = set(skip_urls or ())
    best: tuple[int, str, str, str] | None = None
    fetched = 0
    for label, url in tries:
        if url in seen_urls or not host_allowed(url):
            continue
        seen_urls.add(url)
        try:
            text = fetch_url(url)
        except Exception as exc:
            print(f"skip {url}: {exc}")
            continue
        fetched += 1
        if not text or len(text) < 40 or _looks_like_json(text) or is_web_junk(text[:240]):
            continue
        if is_code_junk(text) or is_toc_junk(text):
            print(f"skip code page {url}" if is_code_junk(text) else f"skip toc page {url}")
            continue
        score = page_score(text, assignment, url, query=query)
        if best is None or score > best[0]:
            best = (score, _page_label(label, url), text, url)
        parsed_assign = parse_assignment(assignment)
        if parsed_assign.intent == "structure":
            if has_mechanism(text) and score >= 10:
                break
            if fetched >= 5:
                break
        elif score >= 12 or fetched >= 5:
            break
    if best:
        return best[1], best[2], best[3]
    return title, "", ""


def run_mission(wish: str) -> str:
    assignment = mission_query(wish)
    extra = urls_in_text(wish)
    print(f"Mission: {assignment!r}")
    log: list[str] = []
    all_follow: list[tuple[str, str]] = []
    understood: list[str] = []
    queue: list[str] = [assignment]
    seen: set[str] = set()
    seen_urls: set[str] = set()
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
            assignment,
            prefer_ru=bool(re.search(r"[А-Яа-яЁё]", parse_assignment(query).topic)),
            skip_urls=seen_urls,
        )
        extra = []
        pages += 1
        if source:
            seen_urls.add(source)
        if not extract:
            log.append(f"не нашёл: {query}")
            report.append(f"Не нашёл страницу про «{query}».")
            continue
        notes = _distill(extract, assignment if pages == 1 else query)
        for note in notes:
            remember(note)
            if note not in understood:
                understood.append(note)
        why_next = next_topics(assignment, extract)
        all_follow.extend(why_next)
        log.append(f"прочитал «{title}»")
        print(f"read {title} from {source}")
        if notes:
            report.append(f"Прочитал: {title}. {notes[0]}")
        else:
            report.append(f"Прочитал: {title}.")
        going: list[str] = []
        for topic, why in why_next:
            hunt = follow_query(assignment, topic)
            if already_knows(topic):
                report.append(f"«{topic}» уже в тетради — второй раз не иду.")
                log.append(f"уже в тетради: {topic}")
                continue
            report.append(f"Сам решил: дальше «{topic}». {why}")
            if hunt.casefold() not in seen:
                queue.append(hunt)
                going.append(topic)
        if going:
            log.append("сам пошёл: " + ", ".join(going))
        elif needs_deeper(assignment, extract):
            hunt = deeper_query(assignment)
            if hunt.casefold() not in seen:
                queue.append(hunt)
                report.append(f"Это пока определение. Сам иду глубже: «{hunt}».")
                log.append(f"мало устройства, иду: {hunt}")

    _note_plan(assignment, log, all_follow, understood[:6])
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
