from __future__ import annotations

import re
from pathlib import Path

BRAIN_PATH = Path("notes/BRAIN.md")


def load_brain_lines() -> list[str]:
    return [line for _section, line in load_brain_entries()]


def load_brain_entries() -> list[tuple[str, str]]:
    if not BRAIN_PATH.exists():
        return []
    entries: list[tuple[str, str]] = []
    section = "прочее"
    for raw in BRAIN_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip().casefold()
            continue
        entries.append((section, line))
    return entries


def remember(fact: str) -> str:
    fact = " ".join(fact.split()).strip()
    if len(fact) < 4:
        return "Скажи, что запомнить."
    known = set(load_brain_lines())
    if fact in known:
        return "Это уже в тетради."
    BRAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BRAIN_PATH.exists():
        body = BRAIN_PATH.read_text(encoding="utf-8").rstrip() + "\n"
    else:
        body = "# Мозг ребёнка\n\n"
    body += f"\n## Запомнил\n\n{fact}\n"
    BRAIN_PATH.write_text(body, encoding="utf-8")
    return f"Запомнил: {fact}"


def _tokens(text: str) -> set[str]:
    raw = {
        part
        for part in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text.casefold())
        if len(part) > 2
    }
    extra = {part[:3] for part in raw if len(part) >= 4}
    return raw | extra


def retrieve(query: str, limit: int = 3) -> list[str]:
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[int, int, str]] = []
    fact_sections = {"запомнил", "мир", "python"}
    for section, line in load_brain_entries():
        overlap = len(q & _tokens(line))
        if not overlap:
            continue
        bonus = 1 if section in fact_sections else 0
        scored.append((overlap + bonus, len(line), line))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [line for _score, _length, line in scored[:limit]]


def know(query: str, limit: int = 3) -> str:
    hits = retrieve(query, limit=limit)
    if not hits:
        return "В тетради этого нет. Скажи «узнай …», я посмотрю."
    return " ".join(hits)
