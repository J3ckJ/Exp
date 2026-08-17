from __future__ import annotations

import argparse
from pathlib import Path

import torch

from child.bytes_io import bytes_to_text, text_to_bytes
from child.config import ChildConfig
from child.curriculum import load_stage
from child.model import Child


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Teach the newborn child one curriculum stage."
    )
    parser.add_argument("--stage", default="russian_yasli")
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        default="checkpoints/child_russian_yasli.pt",
        help="Where to save the taught weights.",
    )
    parser.add_argument(
        "--sample-every",
        type=int,
        default=200,
        help="Print a babble sample every N steps. 0 disables.",
    )
    return parser.parse_args()


def random_batch(
    data: torch.Tensor, batch_size: int, block_size: int
) -> tuple[torch.Tensor, torch.Tensor]:
    max_start = data.size(0) - block_size - 1
    starts = torch.randint(0, max_start, (batch_size,))
    x = torch.stack([data[s : s + block_size] for s in starts])
    y = torch.stack([data[s + 1 : s + 1 + block_size] for s in starts])
    return x, y


@torch.no_grad()
def babble(model: Child, prompt: str, max_new_bytes: int = 120) -> str:
    device = next(model.parameters()).device
    idx = text_to_bytes(prompt).unsqueeze(0).to(device)
    out = model.generate(idx, max_new_bytes=max_new_bytes, temperature=0.8, top_k=40)
    return bytes_to_text(out[0])


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    device = torch.device("cpu")

    text = load_stage(args.stage)
    data = text_to_bytes(text)
    config = ChildConfig()
    if data.size(0) < config.block_size + 2:
        raise SystemExit("Curriculum text is too short for this block_size.")

    model = Child(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    n_params = model.count_parameters()
    print(f"Child is born. parameters={n_params:,}  device={device}")
    print(f"Stage={args.stage}  bytes={data.size(0):,}  steps={args.steps}")
    print("--- before school ---")
    print(babble(model, "Мама "))

    model.train()
    for step in range(1, args.steps + 1):
        x, y = random_batch(data, args.batch_size, config.block_size)
        x, y = x.to(device), y.to(device)
        _logits, loss = model(x, y)
        if loss is None:
            raise RuntimeError("Training step did not return a loss.")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 1 or step % 50 == 0 or step == args.steps:
            print(f"step {step:4d}/{args.steps}  loss={loss.item():.4f}")
        if args.sample_every and step % args.sample_every == 0:
            print("--- babble ---")
            print(babble(model, "Мама "))
            model.train()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model": model.state_dict(),
            "config": config,
            "stage": args.stage,
            "steps": args.steps,
        },
        out_path,
    )
    print(f"Saved {out_path}")
    print("--- after school ---")
    print(babble(model, "Мама "))
    print(babble(model, "Привет"))


if __name__ == "__main__":
    main()
