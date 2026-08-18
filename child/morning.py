from __future__ import annotations

import torch

from child.agent import route_tools
from child.lesson import DEFAULT_CHECKPOINT, babble, checkpoint_status, load_child
from child.tools import moscow_now

MORNING_PROMPTS = (
    ("Привет", "Ты: Привет\nЯ: "),
    ("Кто ты?", "Ты: Кто ты?\nЯ: "),
    ("Где мама?", "Ты: Где мама?\nЯ: "),
    ("Hello", "Ты: Hello\nЯ: "),
    ("What is print?", "Ты: What is print?\nЯ: "),
    ("Write hello", "Ты: Write hello\nЯ: "),
    ("Какая столица России?", "Ты: Какая столица России?\nЯ: "),
    ("Что такое Земля?", "Ты: Что такое Земля?\nЯ: "),
    ("Что ты умеешь?", "Ты: Что ты умеешь?\nЯ: "),
    ("Как зовут хозяина?", "Ты: Как зовут хозяина?\nЯ: "),
    ("Ты Джарвис?", "Ты: Ты Джарвис?\nЯ: "),
)


def main() -> None:
    path = DEFAULT_CHECKPOINT
    if not path.exists():
        raise SystemExit("No checkpoint. The child has not studied yet.")
    device = torch.device("cpu")
    model, _payload, total_steps = load_child(path, device)
    model.eval()
    print(f"Доброе утро. В Москве {moscow_now()}.")
    print(checkpoint_status(path))
    print(f"Шагов в этом теле: {total_steps}. Это ребёнок, не ChatGPT.")
    print()
    print("=== голос ===")
    for title, prompt in MORNING_PROMPTS:
        reply = babble(model, prompt, max_new_bytes=60, temperature=0.35)
        line = reply.split("Я: ", 1)[-1].split("\n", 1)[0].strip()
        print(f"«{title}» → {line}")
    print()
    print("=== руки ===")
    for question in (
        "который час",
        "какое сегодня число",
        "сколько будет 12*8",
        "что ты знаешь про Евгения",
        "что ты знаешь про Землю",
    ):
        print(f"«{question}» → {route_tools(question)}")
    print()
    print("Поговорить: python3 -m child.chat")


if __name__ == "__main__":
    main()
