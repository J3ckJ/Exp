from __future__ import annotations

import torch


def text_to_bytes(text: str) -> torch.Tensor:
    data = text.encode("utf-8")
    return torch.tensor(list(data), dtype=torch.long)


def bytes_to_text(idx: torch.Tensor) -> str:
    raw = bytes(int(b) for b in idx.tolist())
    return raw.decode("utf-8", errors="replace")
