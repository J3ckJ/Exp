from __future__ import annotations

from pathlib import Path
from typing import Sequence

from child.web import fetch_wish_texts
from child.wish import Wish

INBOX = Path("data/inbox")
LEARNED = Path("data/learned")
READERS = Path("data/readers")
WEB_DIR = Path("data/web")


def gather_all(
    parsed: Wish,
    extra: Sequence[Path],
    extra_urls: Sequence[str],
    use_web: bool,
) -> list[Path]:
    paths = [Path(item) for item in extra]
    if INBOX.exists():
        paths.append(INBOX)
    if use_web or parsed.use_web:
        fetch_wish_texts(parsed.topic, extra_urls)
        if WEB_DIR.exists():
            paths.append(WEB_DIR)
    return paths


def archive_inbox() -> None:
    if not INBOX.exists():
        return
    LEARNED.mkdir(parents=True, exist_ok=True)
    for child in sorted(INBOX.iterdir()):
        if child.name == ".gitkeep":
            continue
        target = LEARNED / child.name
        if target.exists():
            target = LEARNED / f"{child.stem}-again{child.suffix}"
        child.replace(target)
