"""Textbook memory for a small mouth.

Not a bigger transformer. A suffix table over the songs and the notebook.
When the child is unsure, or when the last bytes already live in the book,
the next byte is mixed with that memory. kNN-LM / n-gram interpolation,
gated by entropy so a confident song is not shouted down.

This is how a student uses a notebook: look only when you need it,
and trust the page on phrases you have actually seen.
"""

from __future__ import annotations

import argparse
import math
import pickle
from pathlib import Path
from typing import Iterable

import torch
import torch.nn.functional as F

from child.bytes_io import text_to_bytes

DEFAULT_PHRASES = Path("checkpoints/child_phrases.pkl")
MIN_N = 6
MAX_N = 40
LENGTHS = (6, 8, 10, 12, 16, 20, 24, 32, 40)
# Mix hard when a long rare-or-frequent suffix hits; mix softly when the mouth wavers.
MAX_LAM = 0.82


class PhraseMemory:
    """Longest-suffix next-byte table. Keys are raw UTF-8 windows."""

    def __init__(self, lengths: tuple[int, ...] = LENGTHS) -> None:
        self.lengths = tuple(sorted(set(lengths)))
        self.min_n = self.lengths[0]
        self.max_n = self.lengths[-1]
        self.tables: dict[int, dict[bytes, dict[int, int]]] = {n: {} for n in self.lengths}
        self.events = 0

    def add_text(self, text: str) -> None:
        data = bytes(int(b) for b in text_to_bytes(text).tolist())
        self.add_bytes(data)

    def add_bytes(self, data: bytes) -> None:
        length = len(data)
        if length < self.min_n + 1:
            return
        for pos in range(length - 1):
            nxt = data[pos + 1]
            have = pos + 1
            for n in self.lengths:
                if have < n:
                    continue
                key = data[pos + 1 - n : pos + 1]
                bucket = self.tables[n]
                slot = bucket.get(key)
                if slot is None:
                    slot = {}
                    bucket[key] = slot
                slot[nxt] = slot.get(nxt, 0) + 1
            self.events += 1

    def lookup(self, ctx: bytes) -> tuple[dict[int, int], int, int] | None:
        have = len(ctx)
        for n in reversed(self.lengths):
            if have < n:
                continue
            slot = self.tables[n].get(ctx[-n:])
            if slot:
                return slot, n, sum(slot.values())
        return None

    def mix_probs(
        self,
        neural_logits: torch.Tensor,
        ctx: bytes,
        temperature: float,
    ) -> torch.Tensor:
        """Interpolate neural next-byte probs with the longest textbook suffix."""
        probs = F.softmax(neural_logits / max(temperature, 1e-6), dim=-1)
        found = self.lookup(ctx)
        if found is None:
            return probs
        counts, match_len, total = found
        mem = torch.zeros_like(probs)
        for byte, count in counts.items():
            mem[byte] = float(count)
        mem = mem / mem.sum().clamp_min(1.0)
        entropy = float(-(probs * (probs + 1e-9).log()).sum().item())
        unsure = min(1.0, entropy / math.log(256))
        strength = min(1.0, match_len / 24.0) * min(1.0, math.log(total + 1.0) / math.log(16.0))
        lam = max(0.62 * strength, 0.40 * unsure * strength)
        lam = min(MAX_LAM, lam)
        mixed = (1.0 - lam) * probs + lam * mem
        return mixed / mixed.sum().clamp_min(1e-9)

    def stats(self) -> str:
        keys = sum(len(table) for table in self.tables.values())
        return f"phrase keys={keys:,} windows={self.events:,} n={','.join(str(n) for n in self.lengths)}"


def build_phrases(texts: Iterable[str], lengths: tuple[int, ...] = LENGTHS) -> PhraseMemory:
    memory = PhraseMemory(lengths=lengths)
    for text in texts:
        if text:
            memory.add_text(text)
    return memory


def save_phrases(memory: PhraseMemory, path: Path = DEFAULT_PHRASES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(memory, protocol=pickle.HIGHEST_PROTOCOL))
    clear_phrase_cache()


_LOADED: dict[str, PhraseMemory | None] = {}


def load_phrases(path: Path = DEFAULT_PHRASES) -> PhraseMemory | None:
    key = str(path)
    if key in _LOADED:
        return _LOADED[key]
    if not path.exists():
        _LOADED[key] = None
        return None
    payload = pickle.loads(path.read_bytes())
    memory = payload if isinstance(payload, PhraseMemory) else None
    _LOADED[key] = memory
    return memory


def clear_phrase_cache() -> None:
    _LOADED.clear()


def textbook_texts() -> list[str]:
    from child.curriculum import load_stage
    from child.identity import identity_body
    from child.ingest import join_lines
    from child.memory import load_brain_lines
    from child.stories import extra_talk_pairs, stories_body
    from child.talk import format_pair

    turns = "".join(format_pair(user, child) for user, child in extra_talk_pairs())
    return [
        identity_body(),
        join_lines(load_brain_lines(), repeats=2),
        load_stage("russian_talk"),
        load_stage("recite_all"),
        stories_body(),
        turns * 8,
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the child's textbook suffix memory.")
    parser.add_argument("--out", default=str(DEFAULT_PHRASES))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    memory = build_phrases(textbook_texts())
    save_phrases(memory, Path(args.out))
    print(f"Wrote {args.out}  {memory.stats()}")


if __name__ == "__main__":
    main()
