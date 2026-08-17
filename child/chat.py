from __future__ import annotations

import argparse
from pathlib import Path

import torch

from child.bytes_io import bytes_to_text, text_to_bytes
from child.learn import run_night
from child.lesson import DEFAULT_CHECKPOINT, load_child
from child.model import Child
from child.talk import NEWLINE, clean_reply, format_prompt
from child.wish import is_learn_command, parse_wish


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Talk with the child. Say «поучи python в интернете» to send him to study."
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--say", default=None, help="One line, then exit.")
    parser.add_argument("--temperature", type=float, default=0.35)
    parser.add_argument("--bytes", dest="n_bytes", type=int, default=80)
    parser.add_argument("--learn-steps", type=int, default=800)
    parser.add_argument("--no-learn", action="store_true")
    return parser.parse_args()


def resolve_checkpoint(path: Path) -> Path:
    if path.exists():
        return path
    yasli = Path("checkpoints/child_russian_yasli.pt")
    if yasli.exists():
        return yasli
    raise SystemExit(f"No checkpoint at {path}. Train first: python3 -m child.train")


def answer(
    model: Child,
    user: str,
    history: list[tuple[str, str]],
    temperature: float,
    n_bytes: int,
) -> str:
    prompt = format_prompt(user, history, model.config.block_size)
    idx = text_to_bytes(prompt).unsqueeze(0)
    prompt_len = idx.shape[1]
    out = model.generate(
        idx,
        max_new_bytes=n_bytes,
        temperature=temperature,
        top_k=40,
        stop_bytes=(NEWLINE,),
    )
    raw = bytes_to_text(out[0][prompt_len:])
    text = clean_reply(raw)
    if not text:
        text = "Я слушаю."
    return text


def study_if_asked(user: str, learn_steps: int, checkpoint: str) -> str | None:
    if not is_learn_command(user):
        return None
    parsed = parse_wish(user)
    print(f"Хорошо. Сам учусь: topic={parsed.topic} web={parsed.use_web}")
    run_night(
        wish=user,
        sources=[],
        urls=[],
        use_web=parsed.use_web,
        steps=learn_steps,
        batch_size=32,
        lr=8e-5,
        seed=42,
        resume=checkpoint,
        out=checkpoint,
        sample_every=0,
        keep_inbox=True,
        skip_exam=True,
    )
    return "Я поучился. Спроси меня."


def main() -> None:
    args = parse_args()
    path = resolve_checkpoint(Path(args.checkpoint))
    device = torch.device("cpu")
    if args.say is not None and not args.no_learn:
        learned = study_if_asked(args.say, args.learn_steps, str(path))
        if learned is not None:
            print(learned)
            return
    model, _payload, total_steps = load_child(path, device)
    model.eval()
    history: list[tuple[str, str]] = []
    if args.say is not None:
        print(answer(model, args.say, history, args.temperature, args.n_bytes))
        return
    print(f"Ребёнок слушает (шагов {total_steps}). Пиши. «поучи …» — сам учится. Пустая строка — выход.")
    while True:
        try:
            user = input("ты > ").strip()
        except EOFError:
            print()
            break
        if not user:
            break
        if not args.no_learn:
            learned = study_if_asked(user, args.learn_steps, str(path))
            if learned is not None:
                print(f"я  > {learned}")
                model, _payload, total_steps = load_child(path, device)
                model.eval()
                history = []
                continue
        child = answer(model, user, history, args.temperature, args.n_bytes)
        print(f"я  > {child}")
        history.append((user, child))
        if len(history) > 8:
            history = history[-8:]


if __name__ == "__main__":
    main()
