from __future__ import annotations

import argparse
from pathlib import Path

import torch

from child.lesson import DEFAULT_CHECKPOINT, babble, exam, load_child


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Listen to the child after school.")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--bytes", dest="n_bytes", type=int, default=120)
    parser.add_argument("--temperature", type=float, default=0.35)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.checkpoint)
    if not path.exists():
        yasli = Path("checkpoints/child_russian_yasli.pt")
        if yasli.exists():
            path = yasli
        else:
            raise SystemExit(f"No checkpoint at {path}. Train first: python3 -m child.train")
    device = torch.device("cpu")
    model, _payload, total_steps = load_child(path, device)
    model.eval()
    print(f"Listening to {path}  total_steps={total_steps}")
    if args.prompt is None:
        exam(model, "exam")
        return
    print(babble(model, args.prompt, max_new_bytes=args.n_bytes, temperature=args.temperature))


if __name__ == "__main__":
    main()
