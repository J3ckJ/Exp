from __future__ import annotations

from pathlib import Path
from typing import Sequence

INBOX = Path("data/inbox")
LEARNED = Path("data/learned")
READERS = Path("data/readers")


def gather(wish: str, extra: Sequence[Path]) -> list[Path]:
    """Find tonight's books.

    Wish is remembered for later (GitHub, e-books). Tonight it only
    labels the notebook. Sources are local files the child can reach.
    """
    del wish
    paths = [Path(item) for item in extra]
    if INBOX.exists():
        paths.append(INBOX)
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
