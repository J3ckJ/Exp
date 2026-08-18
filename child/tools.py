from __future__ import annotations

import ast
import operator
import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from child.ingest import is_web_junk
from child.memory import remember
from child.web import fetch_url, host_allowed, hunt_urls

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


_WEEKDAYS_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


def moscow_now() -> str:
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    return now.strftime("%H:%M, %d.%m.%Y")


def moscow_date() -> str:
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    weekday = _WEEKDAYS_RU[now.weekday()]
    return f"{weekday}, {now.strftime('%d.%m.%Y')}"


def _looks_like_menu(part: str) -> bool:
    words = part.split()
    if len(words) < 8:
        return False
    caps = sum(1 for word in words if word[:1].isupper())
    return caps / len(words) > 0.55 and len(part) > 80


def first_fact(text: str, query: str = "") -> str:
    """Keep the useful first sentence, even if it is longer than a school line."""
    blob = " ".join(text.split())
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", blob) if part.strip()]
    if not parts:
        return blob[:220]
    q_tokens = {
        token
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", query.casefold())
        if len(token) > 2
    }
    best = ""
    best_score = -1
    for part in parts[:12]:
        if len(part) < 12 or _looks_like_menu(part):
            continue
        tokens = {
            token
            for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", part.casefold())
            if len(token) > 2
        }
        score = len(q_tokens & tokens)
        if score > best_score:
            best = part
            best_score = score
    if not best:
        best = next((part for part in parts if not _looks_like_menu(part)), parts[0])
    if len(best) > 220:
        clipped = best[:217].rsplit(" ", 1)[0]
        return clipped + "…"
    return best


def safe_calc(expr: str) -> str:
    cleaned = expr.replace(" ", "")
    if not re.fullmatch(r"[0-9+\-*/().]+", cleaned):
        return ""
    try:
        tree = ast.parse(cleaned, mode="eval")
        value = _eval_node(tree.body)
    except (SyntaxError, TypeError, ZeroDivisionError, ValueError):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsafe")


def wiki_url(title: str, lang: str) -> str:
    host = {
        "en": "en.wikipedia.org",
        "ru": "ru.wikipedia.org",
        "simple": "simple.wikipedia.org",
    }[lang]
    return f"https://{host}/api/rest_v1/page/summary/{quote(title)}"


def lookup(query: str) -> str:
    title = " ".join(query.split())
    if not title:
        return "Что искать?"
    tries: list[str] = []
    langs = ("ru", "en", "simple") if re.search(r"[А-Яа-яЁё]", title) else ("en", "simple", "ru")
    for lang in langs:
        url = wiki_url(title, lang)
        if host_allowed(url):
            tries.append(url)
    for _label, url in hunt_urls(title, limit=4):
        if url not in tries:
            tries.append(url)
    for url in tries:
        try:
            text = fetch_url(url)
        except Exception:
            continue
        if not text or len(text) < 40 or is_web_junk(text[:240]):
            continue
        fact = first_fact(text, title)
        if fact and not is_web_junk(fact):
            remember(fact)
            return fact
    return "Не нашёл. Скажи иначе."
