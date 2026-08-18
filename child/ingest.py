from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

TEXT_SUFFIXES = {".txt", ".md", ".py"}


def iter_text_files(paths: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
            continue
        if path.is_dir():
            files.extend(
                sorted(
                    child
                    for child in path.rglob("*")
                    if child.is_file() and child.suffix.lower() in TEXT_SUFFIXES
                )
            )
    return files


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_SKIP_LINES = {
    "theme",
    "auto",
    "light",
    "dark",
    "this page",
    "report a bug",
    "improve this page",
    "table of contents",
    "previous topic",
    "next topic",
    "contents",
    "show source",
    "navigation",
    "index",
    "modules |",
    "next |",
    "previous |",
    "numbers",
    "text",
    "lists",
}


def is_practice_line(line: str) -> bool:
    low = line.casefold()
    if low in _SKIP_LINES:
        return False
    if low.startswith(
        (
            "pep:",
            "title:",
            "author:",
            "status:",
            "type:",
            "created:",
            "post-history",
            "abstract",
            "code-block",
        )
    ):
        return False
    if line.endswith(("»", "|", "¶")):
        return False
    if ">>>" in line or ("…" in line and "prompt" in low):
        return False
    if re.fullmatch(r"\d+(\.\d+)*\.?", line):
        return False
    letters = sum(ch.isalpha() for ch in line)
    return letters >= 3


def split_practice_lines(text: str) -> list[str]:
    """Cut a book into sentences a tiny child can chew."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pieces = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    lines: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        line = " ".join(piece.split()).strip()
        if len(line) < 4 or len(line) > 120:
            continue
        if line.startswith("#"):
            continue
        if not is_practice_line(line):
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def join_lines(lines: Sequence[str], repeats: int) -> str:
    if not lines:
        return ""
    body = "\n".join(lines) + "\n"
    return body * repeats


def mix_study(*parts: tuple[str, int]) -> str:
    chunks: list[str] = []
    for text, repeats in parts:
        cleaned = text.strip()
        if not cleaned:
            continue
        if not cleaned.endswith("\n"):
            cleaned += "\n"
        chunks.append(cleaned * repeats)
    return "".join(chunks)
