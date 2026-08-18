from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import torch

from child.config import AGES, age_name, next_age
from child.curriculum import load_stage
from child.ingest import join_lines, mix_study
from child.lesson import DEFAULT_CHECKPOINT, load_child, save_checkpoint, teach_text
from child.memory import load_brain_lines, remember
from child.model import Child
from child.transplant import transplant

# Grow copies the old mouth into a bigger body, then sings so songs do not die.
HARD_LOSS = 0.5
MIN_NEW_BYTES = 1500
DEFAULT_RECITE_STEPS = 800
DEFAULT_BATCH = 16
GROW_MARKERS = (
    "вырасти",
    "стань больше",
    "набери параметры",
    "больше параметров",
    "grow yourself",
    "grow bigger",
)


def wants_grow(text: str) -> bool:
    low = text.casefold()
    return any(marker in low for marker in GROW_MARKERS)


def should_grow(
    current_age: str,
    loss: float,
    new_bytes: int,
    allow: bool,
    force: bool,
) -> tuple[bool, str]:
    nxt = next_age(current_age)
    if nxt is None:
        return False, "already the largest drawn body"
    if not allow and not force:
        return False, "growth is not allowed this lesson"
    if force:
        return True, f"asked to grow {current_age} -> {nxt}"
    if not allow:
        return False, "growth is not allowed this lesson"
    if new_bytes < MIN_NEW_BYTES:
        return False, "the new page is too small to need a bigger mouth"
    if loss < HARD_LOSS:
        return False, "the current mouth chewed the lesson"
    return True, f"loss {loss:.3f} is too hard for {current_age}; try {nxt}"


def backup_body(checkpoint: Path, age: str) -> Path:
    target = checkpoint.parent / f"child_{age}.pt"
    if checkpoint.exists() and checkpoint.resolve() != target.resolve():
        shutil.copy2(checkpoint, target)
        print(f"Kept the old body at {target}")
    return target


def growth_meal() -> str:
    from child.stories import stories_body

    brain = join_lines(load_brain_lines(), repeats=4)
    songs = load_stage("recite_all")
    stories = stories_body()
    return mix_study((brain, 4), (songs, 3), (stories, 2))


def grow_model(old: Child) -> tuple[Child, str, str]:
    current = age_name(old.config)
    nxt = next_age(current)
    if nxt is None:
        raise ValueError("no larger body is drawn yet")
    young = transplant(old, AGES[nxt])
    print(
        f"The child grew himself. {current} {old.count_parameters():,} -> "
        f"{nxt} {young.count_parameters():,}  "
        f"block={young.config.block_size} layers={young.config.n_layer}"
    )
    print("Old weights were copied. New layers start as identity. Then we sing.")
    return young, current, nxt


def run_self_grow(
    checkpoint: str | Path,
    force: bool = False,
    last_loss: float = 0.0,
    new_bytes: int = 0,
    allow: bool = True,
    recite_steps: int = DEFAULT_RECITE_STEPS,
    lr: float = 1.2e-4,
    batch_size: int = DEFAULT_BATCH,
    seed: int = 42,
) -> bool:
    path = Path(checkpoint)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    model, _payload, _steps = load_child(path if path.exists() else None, device)
    current = age_name(model.config)
    ok, reason = should_grow(current, last_loss, new_bytes, allow, force)
    print(f"grow? {ok}  because {reason}")
    if not ok:
        return False
    backup_body(path, current)
    model, old_age, new_age = grow_model(model)
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    meal = growth_meal()
    loss = teach_text(
        model,
        optimizer,
        text=meal,
        label=f"grow:{old_age}->{new_age}",
        steps=recite_steps,
        batch_size=batch_size,
        sample_every=0,
        start_step=0,
    )
    save_checkpoint(
        path,
        model,
        optimizer,
        stage=f"grow_{new_age}",
        steps=recite_steps,
        total_steps=recite_steps,
    )
    named = path.parent / f"child_{new_age}.pt"
    if named != path:
        save_checkpoint(
            named,
            model,
            optimizer,
            stage=f"grow_{new_age}",
            steps=recite_steps,
            total_steps=recite_steps,
        )
    remember(f"Я вырос сам. Было {old_age}, стало {new_age}.")
    tetrad = Path("notes/TETRAD.md")
    if tetrad.parent.exists():
        with tetrad.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n## Сам вырос: {old_age} → {new_age}\n\n"
                f"Ручек стало больше. Старый рот скопировали, новые слои — тождество. "
                f"Спели тетрадь и истории за {recite_steps} шагов, loss={loss:.4f}.\n"
            )
    print(f"New body saved. grow_loss={loss:.4f}  age={new_age}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="The child grows a bigger mouth, copying the old one, then sings."
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--recite-steps", type=int, default=DEFAULT_RECITE_STEPS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--lr", type=float, default=1.2e-4)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args()
    grew = run_self_grow(
        args.checkpoint,
        force=True,
        allow=True,
        recite_steps=args.recite_steps,
        lr=args.lr,
        batch_size=args.batch_size,
    )
    raise SystemExit(0 if grew else 1)


if __name__ == "__main__":
    main()
