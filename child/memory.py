from __future__ import annotations

import re
from pathlib import Path

BRAIN_PATH = Path("notes/BRAIN.md")


def load_brain_lines() -> list[str]:
    if not BRAIN_PATH.exists():
        return []
    lines: list[str] = []
    for raw in BRAIN_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


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
    return {part for part in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text.casefold()) if len(part) > 2}


def retrieve(query: str, limit: int = 3) -> list[str]:
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[int, str]] = []
    for line in load_brain_lines():
        overlap = len(q & _tokens(line))
        if overlap:
            scored.append((overlap, line))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    return [line for _score, line in scored[:limit]]
