from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import torch

from child.curriculum import gold_lines, load_stage
from child.gather import archive_inbox, gather
from child.ingest import iter_text_files, join_lines, mix_study, read_utf8, split_practice_lines
from child.lesson import (
    DEFAULT_CHECKPOINT,
    exam,
    load_child,
    save_checkpoint,
    teach_text,
)

BRAIN_PATH = Path("notes/BRAIN.md")
TETRAD_PATH = Path("notes/TETRAD.md")
MAX_NEW_BRAIN_LINES = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="The child studies alone: read, rehearse, write the notebook."
    )
    parser.add_argument(
        "--wish",
        default="учиться самому",
        help="What to want tonight. Later this will choose GitHub or books.",
    )
    parser.add_argument(
        "--from",
        dest="sources",
        nargs="*",
        default=[],
        help="Files or folders to read. Also reads data/inbox.",
    )
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=8e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--out", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--sample-every", type=int, default=250)
    parser.add_argument(
        "--keep-inbox",
        action="store_true",
        help="Do not move inbox files to data/learned after the night.",
    )
    return parser.parse_args()


def load_brain() -> str:
    if BRAIN_PATH.exists():
        return BRAIN_PATH.read_text(encoding="utf-8")
    return "\n".join(gold_lines()) + "\n"


def brain_sentences(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def write_brain(old_text: str, new_lines: list[str]) -> list[str]:
    known = set(brain_sentences(old_text))
    added: list[str] = []
    for line in new_lines:
        if line in known:
            continue
        added.append(line)
        known.add(line)
        if len(added) >= MAX_NEW_BRAIN_LINES:
            break
    if not added:
        return []
    BRAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = old_text.rstrip() + "\n\n## Сам прочитал\n\n"
    body += "\n".join(added) + "\n"
    BRAIN_PATH.write_text(body, encoding="utf-8")
    return added


def append_tetrad(
    wish: str,
    sources: list[Path],
    new_bytes: int,
    steps: int,
    loss: float,
    added: list[str],
    after: list[tuple[str, str]],
) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    names = ", ".join(path.name for path in sources) or "только тетрадь"
    lines = [
        "",
        f"## Самоучка: {wish}",
        "",
        f"{stamp}. Источники: {names}. Новых байт практики: {new_bytes}. Шагов: {steps}. Loss: {loss:.4f}.",
        "",
    ]
    if added:
        lines.append("В мозг-тетрадь дописал:")
        lines.extend(f"- {item}" for item in added)
        lines.append("")
    lines.append("После ночи:")
    for prompt, answer in after[:6]:
        short = " ".join(answer.split())
        if len(short) > 120:
            short = short[:117] + "..."
        lines.append(f"- «{prompt}» → {short}")
    lines.append("")
    TETRAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TETRAD_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    device = torch.device("cpu")
    resume = Path(args.resume) if args.resume else None
    if resume is not None and not resume.exists():
        yasli = Path("checkpoints/child_russian_yasli.pt")
        if yasli.exists():
            resume = yasli
    model, _payload, total_steps = load_child(resume, device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    print(
        f"The child sits down alone. wish={args.wish!r}  "
        f"parameters={model.count_parameters():,}  prior_steps={total_steps}"
    )

    source_paths = gather(args.wish, [Path(item) for item in args.sources])
    files = iter_text_files(source_paths)
    raw_parts = [read_utf8(path) for path in files]
    practice_lines = split_practice_lines("\n".join(raw_parts))
    new_text = join_lines(practice_lines, repeats=8)
    brain_raw = load_brain()
    brain_text = join_lines(brain_sentences(brain_raw), repeats=1)
    rehearsal = load_stage("russian_recitation")
    study = mix_study((brain_text, 8), (rehearsal, 2), (new_text, 10))
    if not study.strip():
        raise SystemExit("Nothing to study. Put text in data/inbox or pass --from.")

    exam(model, "before the night")
    loss = teach_text(
        model,
        optimizer,
        text=study,
        label=args.wish,
        steps=args.steps,
        batch_size=args.batch_size,
        sample_every=args.sample_every,
        start_step=total_steps,
    )
    total_steps += args.steps
    after = exam(model, "after the night")
    added = write_brain(brain_raw, practice_lines)
    append_tetrad(
        wish=args.wish,
        sources=files,
        new_bytes=len(new_text.encode("utf-8")),
        steps=args.steps,
        loss=loss,
        added=added,
        after=after,
    )
    save_checkpoint(
        Path(args.out),
        model,
        optimizer,
        stage=args.wish,
        steps=args.steps,
        total_steps=total_steps,
    )
    if not args.keep_inbox:
        archive_inbox()
    print(f"Wrote {BRAIN_PATH} and {TETRAD_PATH}")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
