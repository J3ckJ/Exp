from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import torch

from child.config import AGES, age_name, next_age
from child.curriculum import load_stage
from child.ingest import join_lines, mix_study
from child.identity import identity_body
from child.lesson import DEFAULT_CHECKPOINT, load_child, save_checkpoint, teach_text
from child.lora import attach_lora, count_trainable, lora_parameters, merge_lora
from child.memory import load_brain_lines, remember
from child.model import Child
from child.phrase import build_phrases, save_phrases, textbook_texts
from child.transplant import transplant

# Grow copies the old mouth into a bigger body, then sings so songs do not die.
HARD_LOSS = 0.5
MIN_NEW_BYTES = 1500
DEFAULT_RECITE_STEPS = 800
DEFAULT_BATCH = 16
CHEAP_STEPS = 120
CHEAP_BATCH = 8
CHEAP_LR = 8e-4
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


def cheap_meal() -> str:
    from child.stories import stories_body

    brain = join_lines(load_brain_lines(), repeats=3)
    songs = load_stage("recite_all")
    talk = load_stage("russian_talk")
    return mix_study((identity_body(), 6), (talk, 4), (songs, 3), (brain, 3), (stories_body(), 1))


def run_cheap_grow(
    checkpoint: str | Path,
    steps: int = CHEAP_STEPS,
    lr: float = CHEAP_LR,
    batch_size: int = CHEAP_BATCH,
    rank: int = 8,
    last_blocks: int = 4,
    seed: int = 42,
) -> bool:
    """Grow without a new dense body: rebuild the notebook memory, then LoRA+merge."""
    path = Path(checkpoint)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    print("Cheap growth: not 40M dense. Phrase memory + LoRA on a frozen mouth.")
    memory = build_phrases(textbook_texts())
    save_phrases(memory)
    print(memory.stats())
    model, _payload, total_steps = load_child(path if path.exists() else None, device)
    backup_body(path, age_name(model.config))
    attach_lora(model, rank=rank, last_blocks=last_blocks)
    trainable = count_trainable(model)
    print(
        f"Frozen {model.count_parameters():,} mouth. Training {trainable:,} LoRA numbers "
        f"on last {last_blocks} blocks, rank={rank}."
    )
    optimizer = torch.optim.AdamW(lora_parameters(model), lr=lr)
    loss = teach_text(
        model,
        optimizer,
        text=cheap_meal(),
        label="cheap:lora+name",
        steps=steps,
        batch_size=batch_size,
        sample_every=0,
        start_step=total_steps,
    )
    merge_lora(model)
    save_checkpoint(
        path,
        model,
        torch.optim.AdamW(model.parameters(), lr=lr),
        stage="cheap_lora",
        steps=steps,
        total_steps=total_steps + steps,
    )
    remember("Меня зовут Тима. Я вырос дёшево: тетрадь в память, тонкий слой в рот.")
    tetrad = Path("notes/TETRAD.md")
    if tetrad.parent.exists():
        with tetrad.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Дешёвый рост: память + LoRA\n\n"
                f"Не плотные десятки миллионов. Суффиксная память учебника ({memory.stats()}). "
                f"Потом LoRA {trainable:,} чисел, {steps} шагов, loss={loss:.4f}, влили в старый рот. "
                f"Зовут Тима.\n"
            )
    print(f"Cheap body saved. lora_loss={loss:.4f}  extra_train={trainable:,}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cheap growth: textbook memory + LoRA merge. Pass --dense for the old bigger body."
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--dense", action="store_true", help="Old path: copy into the next drawn body.")
    parser.add_argument("--recite-steps", type=int, default=DEFAULT_RECITE_STEPS)
    parser.add_argument("--steps", type=int, default=CHEAP_STEPS, help="LoRA steps for cheap growth.")
    parser.add_argument("--batch-size", type=int, default=CHEAP_BATCH)
    parser.add_argument("--lr", type=float, default=CHEAP_LR)
    parser.add_argument("--rank", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args()
    if args.dense:
        grew = run_self_grow(
            args.checkpoint,
            force=True,
            allow=True,
            recite_steps=args.recite_steps,
            lr=args.lr,
            batch_size=args.batch_size,
        )
    else:
        grew = run_cheap_grow(
            args.checkpoint,
            steps=args.steps,
            lr=args.lr,
            batch_size=args.batch_size,
            rank=args.rank,
        )
    raise SystemExit(0 if grew else 1)


if __name__ == "__main__":
    main()
