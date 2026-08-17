from __future__ import annotations

NEWLINE = 10
USER = "Ты"
SELF = "Я"


def format_pair(user: str, child: str) -> str:
    return f"{USER}: {user}\n{SELF}: {child}\n"


def format_prompt(user: str, history: list[tuple[str, str]], block_size: int) -> str:
    """Build a prompt that fits the child's short mouth."""
    tail = f"{USER}: {user}\n{SELF}: "
    prompt = tail
    for previous_user, previous_child in reversed(history):
        piece = format_pair(previous_user, previous_child)
        candidate = piece + prompt
        if len(candidate.encode("utf-8")) > block_size:
            break
        prompt = candidate
    return prompt


def clean_reply(raw: str) -> str:
    line = raw.split("\n", 1)[0]
    line = line.split(f"{USER}:", 1)[0]
    return " ".join(line.split()).strip()
