from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch

from child.curriculum import load_stage
from child.gather import archive_inbox, gather_all
from child.ingest import iter_text_files, join_lines, mix_study, read_utf8, split_practice_lines
from child.lesson import (
    DEFAULT_CHECKPOINT,
    exam,
    load_child,
    save_checkpoint,
    teach_text,
)
from child.wish import parse_wish

BRAIN_PATH = Path("notes/BRAIN.md")
TETRAD_PATH = Path("notes/TETRAD.md")
MAX_NEW_BRAIN_LINES = 24

STAGE_FOR_TOPIC = {
    "russian": "russian_power",
    "english": "english_school",
    "python": "python_school",
    "world": "world_school",
    "general": "russian_power",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="The child studies alone: local files and, if asked, the web."
    )
    parser.add_argument("--wish", default="учиться самому")
    parser.add_argument("--from", dest="sources", nargs="*", default=[])
    parser.add_argument("--url", dest="urls", nargs="*", default=[])
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=8e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--out", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--sample-every", type=int, default=400)
    parser.add_argument("--keep-inbox", action="store_true")
    parser.add_argument("--skip-exam", action="store_true")
    return parser.parse_args()


def load_brain() -> str:
    if BRAIN_PATH.exists():
        return BRAIN_PATH.read_text(encoding="utf-8")
    return ""


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
    body = (old_text or "# Мозг ребёнка\n").rstrip() + "\n\n## Сам прочитал\n\n"
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
    names = ", ".join(path.name for path in sources) or "тетрадь и школа"
    lines = [
        "",
        f"## Самоучка: {wish}",
        "",
        f"{stamp}. Источники: {names}. Новых байт практики: {new_bytes}. Шагов: {steps}. Loss: {loss:.4f}.",
        "",
    ]
    if added:
        lines.append("В мозг-тетрадь дописал:")
        lines.extend(f"- {item}" for item in added[:12])
        lines.append("")
    if after:
        lines.append("После ночи:")
        for prompt, answer in after[:8]:
            short = " ".join(answer.split())
            if len(short) > 120:
                short = short[:117] + "..."
            lines.append(f"- «{prompt}» → {short}")
        lines.append("")
    TETRAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TETRAD_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def study_mix(parsed: Wish, new_text: str, brain_text: str) -> str:
    school = load_stage(STAGE_FOR_TOPIC.get(parsed.topic, "russian_power"))
    return mix_study((brain_text, 6), (school, 3), (new_text, 10 if new_text.strip() else 0))


def run_night(
    wish: str,
    sources: list[str],
    urls: list[str],
    use_web: bool,
    steps: int,
    batch_size: int,
    lr: float,
    seed: int,
    resume: str,
    out: str,
    sample_every: int,
    keep_inbox: bool,
    skip_exam: bool,
) -> float:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    torch.manual_seed(seed)
    device = torch.device("cpu")
    parsed = parse_wish(wish)
    resume_path = Path(resume) if resume else None
    if resume_path is not None and not resume_path.exists():
        yasli = Path("checkpoints/child_russian_yasli.pt")
        if yasli.exists():
            resume_path = yasli
    model, _payload, total_steps = load_child(resume_path, device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    print(
        f"The child sits down alone. wish={parsed.raw!r} topic={parsed.topic} "
        f"web={use_web or parsed.use_web} parameters={model.count_parameters():,} "
        f"prior_steps={total_steps}"
    )
    source_paths = gather_all(
        parsed,
        [Path(item) for item in sources],
        urls,
        use_web=use_web,
    )
    files = iter_text_files(source_paths)
    raw_parts = [read_utf8(path) for path in files]
    practice_lines = split_practice_lines("\n".join(raw_parts))
    new_text = join_lines(practice_lines, repeats=6)
    brain_raw = load_brain()
    brain_text = join_lines(brain_sentences(brain_raw), repeats=1)
    study = study_mix(parsed, new_text, brain_text)
    if not study.strip():
        raise SystemExit("Nothing to study.")
    if not skip_exam:
        exam(model, "before the night")
    loss = teach_text(
        model,
        optimizer,
        text=study,
        label=parsed.raw,
        steps=steps,
        batch_size=batch_size,
        sample_every=sample_every,
        start_step=total_steps,
    )
    total_steps += steps
    after: list[tuple[str, str]] = []
    if not skip_exam:
        after = exam(model, "after the night")
    added = write_brain(brain_raw, practice_lines)
    append_tetrad(
        wish=parsed.raw,
        sources=files,
        new_bytes=len(new_text.encode("utf-8")),
        steps=steps,
        loss=loss,
        added=added,
        after=after,
    )
    save_checkpoint(
        Path(out),
        model,
        optimizer,
        stage=parsed.topic,
        steps=steps,
        total_steps=total_steps,
    )
    if not keep_inbox:
        archive_inbox()
    print(f"Wrote {BRAIN_PATH} and {TETRAD_PATH}")
    print(f"Saved {out}")
    return loss


def main() -> None:
    args = parse_args()
    run_night(
        wish=args.wish,
        sources=args.sources,
        urls=args.urls,
        use_web=args.web,
        steps=args.steps,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        resume=args.resume,
        out=args.out,
        sample_every=args.sample_every,
        keep_inbox=args.keep_inbox,
        skip_exam=args.skip_exam,
    )


if __name__ == "__main__":
    main()
