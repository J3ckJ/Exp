from __future__ import annotations

import argparse
from pathlib import Path

import torch

from child.agent import route_tools, speak_prompt, study_command
from child.bytes_io import bytes_to_text, text_to_bytes
from child.lesson import DEFAULT_CHECKPOINT, load_child
from child.model import Child
from child.talk import NEWLINE, clean_reply


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Jarvis-child: talk, remember, look up, study, tell Moscow time."
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--say", default=None, help="One line, then exit.")
    parser.add_argument("--temperature", type=float, default=0.35)
    parser.add_argument("--bytes", dest="n_bytes", type=int, default=80)
    parser.add_argument("--learn-steps", type=int, default=600)
    parser.add_argument("--no-learn", action="store_true")
    parser.add_argument("--no-tools", action="store_true")
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
    prompt = speak_prompt(user, history, model.config.block_size)
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


def handle_line(
    user: str,
    model: Child | None,
    history: list[tuple[str, str]],
    args: argparse.Namespace,
    checkpoint: str,
) -> tuple[str, Child | None, str]:
    if not args.no_tools:
        tool = route_tools(user)
        if tool is not None:
            return tool, model, "tool"
    if not args.no_learn:
        learned = study_command(user, args.learn_steps, checkpoint)
        if learned is not None:
            device = torch.device("cpu")
            model, _payload, _steps = load_child(Path(checkpoint), device)
            model.eval()
            history.clear()
            return learned, model, "tool"
    if model is None:
        device = torch.device("cpu")
        model, _payload, _steps = load_child(Path(checkpoint), device)
        model.eval()
    return answer(model, user, history, args.temperature, args.n_bytes), model, "talk"


def main() -> None:
    args = parse_args()
    path = resolve_checkpoint(Path(args.checkpoint))
    model: Child | None = None
    history: list[tuple[str, str]] = []
    if args.say is not None:
        text, _model, _kind = handle_line(args.say, model, history, args, str(path))
        print(text)
        return
    device = torch.device("cpu")
    model, _payload, total_steps = load_child(path, device)
    model.eval()
    print(
        f"Джарвис-ребёнок слушает (шагов {total_steps}). "
        "Можно: говорить, «который час», «какое сегодня число», «запомни …», "
        "«что ты знаешь про …», «что такое …», «посчитай …», «выполни print(… )», "
        "«прочитай тетрадь», «сколько шагов», «поучи github», «вырасти»."
    )
    while True:
        try:
            user = input("ты > ").strip()
        except EOFError:
            print()
            break
        if not user:
            break
        text, model, kind = handle_line(user, model, history, args, str(path))
        print(f"я  > {text}")
        if kind == "talk":
            history.append((user, text))
            if len(history) > 8:
                history = history[-8:]


if __name__ == "__main__":
    main()
