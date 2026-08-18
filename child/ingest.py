from __future__ import annotations

import re
from html import unescape
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
    if letters < 3:
        return False
    if is_web_junk(line):
        return False
    return True


_WEB_JUNK = (
    "cookie",
    "cookies",
    "enable javascript",
    "включите javascript",
    "just a moment",
    "attention required",
    "access denied",
    "cloudflare",
    "captcha",
    "подписывайтесь",
    "приняв cookie",
    "we use cookies",
    "sign in",
    "log in",
    "console.error",
    "console.log",
)


def is_web_junk(text: str) -> bool:
    low = text.casefold()
    return any(marker in low for marker in _WEB_JUNK)


def clean_web_text(text: str) -> str:
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), text)
    text = unescape(text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(text.split())


def is_weak_note(line: str, *, web: bool = False) -> bool:
    line = " ".join(line.split()).strip()
    if web and len(line) < 24:
        return True
    if len(line) < 4:
        return True
    if is_web_junk(line):
        return True
    if re.search(r"<[^>]+>|\\u00", line):
        return True
    low = line.casefold()
    if low in {"courses", "navigation", "home", "index"}:
        return True
    if re.search(r"/ хабр|geeksforgeeks| - youtube", low):
        return True
    if "console." in low or low.startswith("//") or ("{" in line and "function" in low):
        return True
    if web and sum(ch.isalpha() for ch in line) < 12:
        return True
    if web and re.search(
        r"ai-powered|our article|this article|this post|subscribe|business software|"
        r"foundational principles|scaffolds modern",
        low,
    ):
        return True
    if web and line.endswith("?") and re.match(
        r"(?i)(what|how|where|who|why|когда|что |как )", line
    ):
        return True
    if web:
        words = re.findall(r"[A-Za-zА-Яа-яЁё0-9\-]+", line)
        titled = sum(1 for word in words if word[:1].isupper())
        if (
            len(words) >= 8
            and titled >= 6
            and " is " not in low
            and " uses " not in low
            and " это " not in low
        ):
            return True
    return False


def is_code_junk(text: str) -> bool:
    low = text.casefold()
    markers = (
        "console.",
        "function(",
        "=> {",
        "this.messages",
        "document.",
        "$watch",
        "this.$",
        ".splice(",
    )
    return sum(1 for marker in markers if marker in low) >= 2 or "console.error" in low


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
