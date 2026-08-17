from __future__ import annotations

import argparse
from pathlib import Path

import torch

from child.bytes_io import bytes_to_text, text_to_bytes
from child.config import ChildConfig
from child.model import Child


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask the child to continue a prompt.")
    parser.add_argument("--checkpoint", default="checkpoints/child_russian_yasli.pt")
    parser.add_argument("--prompt", default="Мама ")
    parser.add_argument("--bytes", dest="n_bytes", type=int, default=160)
    parser.add_argument("--temperature", type=float, default=0.8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.checkpoint)
    if not path.exists():
        raise SystemExit(f"No checkpoint at {path}. Train first: python3 -m child.train")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    config = payload.get("config") or ChildConfig()
    model = Child(config)
    model.load_state_dict(payload["model"])
    model.eval()
    idx = text_to_bytes(args.prompt).unsqueeze(0)
    out = model.generate(
        idx, max_new_bytes=args.n_bytes, temperature=args.temperature, top_k=40
    )
    print(bytes_to_text(out[0]))


if __name__ == "__main__":
    main()
