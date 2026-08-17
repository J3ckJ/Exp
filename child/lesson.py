from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import torch

from child.bytes_io import bytes_to_text, text_to_bytes
from child.config import ChildConfig
from child.curriculum import load_stage
from child.model import Child

DEFAULT_CHECKPOINT = Path("checkpoints/child_latest.pt")
EXAM_PROMPTS = (
    "Мама ",
    "Папа ",
    "Привет",
    "Это ",
    "Кто это?",
    "Мама ест",
    "Мама читает",
    "Доброе ",
    "Где мама?",
    "Я ",
    "Я учусь",
    "Ты: Привет\nЯ: ",
    "Ты: Как дела?\nЯ: ",
    "Ты: Кто ты?\nЯ: ",
    "Ты: Почему небо голубое?\nЯ: ",
    "Ты: Как тебя зовут?\nЯ: ",
    "Ты: Ты умный?\nЯ: ",
)


def random_batch(
    data: torch.Tensor, batch_size: int, block_size: int
) -> tuple[torch.Tensor, torch.Tensor]:
    max_start = data.size(0) - block_size - 1
    starts = torch.randint(0, max_start, (batch_size,))
    x = torch.stack([data[s : s + block_size] for s in starts])
    y = torch.stack([data[s + 1 : s + 1 + block_size] for s in starts])
    return x, y


@torch.no_grad()
def babble(
    model: Child,
    prompt: str,
    max_new_bytes: int = 120,
    temperature: float = 0.8,
) -> str:
    device = next(model.parameters()).device
    idx = text_to_bytes(prompt).unsqueeze(0).to(device)
    stop = (10,) if "Я:" in prompt else None
    out = model.generate(
        idx,
        max_new_bytes=max_new_bytes,
        temperature=temperature,
        top_k=40,
        stop_bytes=stop,
    )
    text = bytes_to_text(out[0])
    if stop is not None:
        generated = bytes_to_text(out[0][idx.shape[1] :])
        return prompt + generated.split("\n", 1)[0]
    return text


def save_checkpoint(
    path: Path,
    model: Child,
    optimizer: torch.optim.Optimizer,
    stage: str,
    steps: int,
    total_steps: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "config": model.config,
            "stage": stage,
            "steps": steps,
            "total_steps": total_steps,
        },
        path,
    )


def load_child(
    resume: Optional[Path],
    device: torch.device,
) -> tuple[Child, Optional[dict], int]:
    config = ChildConfig()
    model = Child(config).to(device)
    payload: Optional[dict] = None
    total_steps = 0
    if resume is not None and resume.exists():
        payload = torch.load(resume, map_location=device, weights_only=False)
        saved_config = payload.get("config")
        if saved_config is not None:
            model = Child(saved_config).to(device)
        model.load_state_dict(payload["model"])
        model.tie_weights()
        total_steps = int(payload.get("total_steps") or payload.get("steps") or 0)
    return model, payload, total_steps


def teach_text(
    model: Child,
    optimizer: torch.optim.Optimizer,
    text: str,
    label: str,
    steps: int,
    batch_size: int,
    sample_every: int,
    start_step: int,
) -> float:
    data = text_to_bytes(text)
    block_size = model.config.block_size
    if data.size(0) < block_size + 2:
        raise SystemExit(f"Study text {label!r} is too short for this block_size.")
    last_loss = float("nan")
    device = next(model.parameters()).device
    print(f"Lesson={label}  bytes={data.size(0):,}  steps={steps}")
    base_lrs = [float(group["lr"]) for group in optimizer.param_groups]
    model.train()
    for step in range(1, steps + 1):
        progress = (step - 1) / max(steps - 1, 1)
        scale = 0.5 * (1.0 + math.cos(math.pi * progress))
        for group, base in zip(optimizer.param_groups, base_lrs):
            group["lr"] = max(base * scale, base * 0.08)
        x, y = random_batch(data, batch_size, block_size)
        x, y = x.to(device), y.to(device)
        _logits, loss = model(x, y)
        if loss is None:
            raise RuntimeError("Training step did not return a loss.")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        last_loss = float(loss.item())
        shown = start_step + step
        if step == 1 or step % 50 == 0 or step == steps:
            print(
                f"step {shown:5d}  loss={last_loss:.4f}  lr={optimizer.param_groups[0]['lr']:.2e}"
            )
        if sample_every and step % sample_every == 0:
            print("--- recitation ---")
            print(babble(model, "Мама ", temperature=0.4))
            print(babble(model, "Ты: Привет\nЯ: ", temperature=0.35, max_new_bytes=60))
            model.train()
    return last_loss


def teach(
    model: Child,
    optimizer: torch.optim.Optimizer,
    stage: str,
    steps: int,
    batch_size: int,
    sample_every: int,
    start_step: int,
) -> float:
    return teach_text(
        model,
        optimizer,
        text=load_stage(stage),
        label=stage,
        steps=steps,
        batch_size=batch_size,
        sample_every=sample_every,
        start_step=start_step,
    )


def exam(model: Child, title: str) -> list[tuple[str, str]]:
    print(f"=== {title} ===")
    results: list[tuple[str, str]] = []
    for prompt in EXAM_PROMPTS:
        quiet = babble(model, prompt, max_new_bytes=80, temperature=0.35)
        results.append((prompt, quiet))
        print(f"[{prompt!r}]")
        print(quiet)
        print()
    return results
