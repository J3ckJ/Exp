from __future__ import annotations

import argparse
from pathlib import Path

import torch

from child.bytes_io import bytes_to_text, text_to_bytes
from child.lesson import DEFAULT_CHECKPOINT, load_child
from child.model import Child
from child.talk import NEWLINE, clean_reply, format_prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Talk with the child. Short turns. He is small."
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--say", default=None, help="One line, then exit.")
    parser.add_argument("--temperature", type=float, default=0.35)
    parser.add_argument("--bytes", dest="n_bytes", type=int, default=80)
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


def main() -> None:
    args = parse_args()
    path = resolve_checkpoint(Path(args.checkpoint))
    device = torch.device("cpu")
    model, _payload, total_steps = load_child(path, device)
    model.eval()
    history: list[tuple[str, str]] = []
    if args.say is not None:
        print(answer(model, args.say, history, args.temperature, args.n_bytes))
        return
    print(f"Ребёнок слушает (шагов {total_steps}). Пиши. Пустая строка — выход.")
    while True:
        try:
            user = input("ты > ").strip()
        except EOFError:
            print()
            break
        if not user:
            break
        child = answer(model, user, history, args.temperature, args.n_bytes)
        print(f"я  > {child}")
        history.append((user, child))
        if len(history) > 4:
            history = history[-4:]


if __name__ == "__main__":
    main()
