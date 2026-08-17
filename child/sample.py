from __future__ import annotations

import argparse
from pathlib import Path

import torch

from child.bytes_io import bytes_to_text, text_to_bytes
from child.lesson import DEFAULT_CHECKPOINT, load_child


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask the child to continue a prompt.")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--prompt", default="Мама ")
    parser.add_argument("--bytes", dest="n_bytes", type=int, default=160)
    parser.add_argument("--temperature", type=float, default=0.8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.checkpoint)
    if not path.exists():
        yasli = Path("checkpoints/child_russian_yasli.pt")
        path = yasli if yasli.exists() else path
    if not path.exists():
        raise SystemExit(f"No checkpoint at {path}. Train first: python3 -m child.train")
    device = torch.device("cpu")
    model, _payload, _steps = load_child(path, device)
    model.eval()
    idx = text_to_bytes(args.prompt).unsqueeze(0)
    out = model.generate(
        idx, max_new_bytes=args.n_bytes, temperature=args.temperature, top_k=40
    )
    print(bytes_to_text(out[0]))


if __name__ == "__main__":
    main()
