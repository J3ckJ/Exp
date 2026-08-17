from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

from child.config import AGES, configs_match
from child.lesson import (
    DEFAULT_CHECKPOINT,
    exam,
    load_child,
    save_checkpoint,
    teach,
)
from child.model import Child

# A school day: drill, then a full Russian day, then quiet recitation.
# English and Python stay in the corridor. Not today.
SCHOOL_DAY: tuple[tuple[str, int, float], ...] = (
    ("russian_core", 1200, 1.5e-4),
    ("russian_school", 2200, 1.2e-4),
    ("russian_recitation", 800, 8e-5),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Teach the child. Resume a living pupil; do not rebirth him."
    )
    parser.add_argument("--stage", default=None, help="One lesson. Omit to run the school day.")
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1.5e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--age",
        default=None,
        choices=sorted(AGES),
        help="Grow a new body if the checkpoint is smaller. toddler or preschooler.",
    )
    parser.add_argument(
        "--resume",
        default=str(DEFAULT_CHECKPOINT),
        help="Previous body. Empty string starts a newborn.",
    )
    parser.add_argument("--out", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument(
        "--sample-every",
        type=int,
        default=400,
        help="Print a recitation every N steps. 0 disables.",
    )
    parser.add_argument("--skip-exam", action="store_true")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args()
    torch.manual_seed(args.seed)
    device = torch.device("cpu")
    resume = Path(args.resume) if args.resume else None
    if resume is not None and not resume.exists():
        yasli = Path("checkpoints/child_russian_yasli.pt")
        if yasli.exists():
            resume = yasli
    model, _payload, total_steps = load_child(resume, device)
    if args.age is not None:
        target = AGES[args.age]
        if not configs_match(model.config, target):
            print(
                f"The child grew. {model.count_parameters():,} -> "
                f"age={args.age}  block={target.block_size}  "
                f"layers={target.n_layer}  width={target.n_embd}"
            )
            print("Weights start fresh. Memory lives in lessons and notes/BRAIN.md.")
            model = Child(target).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    n_params = model.count_parameters()
    if resume is not None and resume.exists():
        print(
            f"The child returns to school. parameters={n_params:,}  "
            f"prior_steps={total_steps}  from={resume}"
        )
    else:
        print(f"Child is born. parameters={n_params:,}  device={device}")

    if not args.skip_exam:
        exam(model, "before today's lessons")
    lessons = SCHOOL_DAY if args.stage is None else ((args.stage, args.steps, args.lr),)
    out_path = Path(args.out)
    last_stage = lessons[-1][0]
    for stage, steps, lr in lessons:
        for group in optimizer.param_groups:
            group["lr"] = lr
        print(f"--- period: {stage}  lr={lr:g} ---")
        teach(
            model,
            optimizer,
            stage=stage,
            steps=steps,
            batch_size=args.batch_size,
            sample_every=args.sample_every,
            start_step=total_steps,
        )
        total_steps += steps
        last_stage = stage
        save_checkpoint(
            out_path,
            model,
            optimizer,
            stage=last_stage,
            steps=steps,
            total_steps=total_steps,
        )
        named = Path("checkpoints") / f"child_{stage}.pt"
        if named != out_path:
            save_checkpoint(
                named,
                model,
                optimizer,
                stage=last_stage,
                steps=steps,
                total_steps=total_steps,
            )
        print(f"Saved {out_path}")

    if not args.skip_exam:
        exam(model, "after school")


if __name__ == "__main__":
    main()
