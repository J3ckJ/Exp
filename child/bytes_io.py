from __future__ import annotations

import torch


def text_to_bytes(text: str) -> torch.Tensor:
    data = text.encode("utf-8")
    return torch.tensor(list(data), dtype=torch.long)


def bytes_to_text(idx: torch.Tensor) -> str:
    raw = bytes(int(b) for b in idx.tolist())
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for cut in range(1, min(4, len(raw) + 1)):
        try:
            return raw[:-cut].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
