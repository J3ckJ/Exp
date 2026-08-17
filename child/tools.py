from __future__ import annotations

import ast
import operator
import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from child.ingest import split_practice_lines
from child.memory import remember
from child.web import fetch_url, host_allowed

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def moscow_now() -> str:
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    return now.strftime("%H:%M, %d.%m.%Y")


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
    texts: list[str] = []
    langs = ("ru", "en", "simple") if re.search(r"[А-Яа-яЁё]", title) else ("en", "simple", "ru")
    for lang in langs:
        url = wiki_url(title, lang)
        if not host_allowed(url):
            continue
        try:
            text = fetch_url(url)
        except Exception:
            continue
        if text and len(text) > 40:
            texts.append(text)
            break
    if not texts:
        return "Не нашёл. Скажи иначе."
    extract = texts[0].strip()
    first = split_practice_lines(extract)
    fact = first[0] if first else extract[:180]
    remember(fact)
    return fact
