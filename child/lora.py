"""Cheap plastic growth: LoRA on a frozen mouth, then merge.

The 8M body already knows songs. Training all of it again to learn a name
or a new story is the expensive habit. Freeze the song, learn a thin
low-rank delta (Hu et al. 2022), then pour the delta back into W
(ReLoRA-style merge, Lialin et al. 2024). The checkpoint stays a normal Child.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from child.model import Child


class LoRALinear(nn.Module):
    def __init__(self, linear: nn.Linear, rank: int, alpha: float) -> None:
        super().__init__()
        if rank < 1:
            raise ValueError("LoRA rank must be >= 1")
        self.linear = linear
        self.rank = rank
        self.scale = alpha / rank
        for param in self.linear.parameters():
            param.requires_grad = False
        self.A = nn.Parameter(torch.zeros(rank, linear.in_features))
        self.B = nn.Parameter(torch.zeros(linear.out_features, rank))
        nn.init.normal_(self.A, mean=0.0, std=0.02)

    def extra_delta(self, x: torch.Tensor) -> torch.Tensor:
        # x @ A.T -> (..., rank); then @ B.T -> (..., out)
        return (x @ self.A.T @ self.B.T) * self.scale

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x) + self.extra_delta(x)

    def merged_weight(self) -> torch.Tensor:
        # W' = W + scale * B @ A
        return self.linear.weight + self.scale * (self.B @ self.A)


def _freeze_all(model: nn.Module) -> None:
    for param in model.parameters():
        param.requires_grad = False


def _swap_linear(module: nn.Module, name: str, rank: int, alpha: float) -> None:
    child = getattr(module, name)
    if not isinstance(child, nn.Linear):
        raise TypeError(f"{name} is not Linear")
    setattr(module, name, LoRALinear(child, rank=rank, alpha=alpha))


def attach_lora(
    model: Child,
    rank: int = 8,
    last_blocks: int = 4,
    alpha: float = 16.0,
) -> Child:
    """Freeze the mouth. Put LoRA on the last residual projections."""
    _freeze_all(model)
    start = max(0, len(model.blocks) - last_blocks)
    for block in model.blocks[start:]:
        _swap_linear(block.attn, "c_attn", rank, alpha)
        _swap_linear(block.attn, "c_proj", rank, alpha)
        block.mlp.net[0] = LoRALinear(block.mlp.net[0], rank=rank, alpha=alpha)
        block.mlp.net[2] = LoRALinear(block.mlp.net[2], rank=rank, alpha=alpha)
    return model


def lora_parameters(model: nn.Module) -> list[nn.Parameter]:
    return [param for param in model.parameters() if param.requires_grad]


def count_trainable(model: nn.Module) -> int:
    return sum(param.numel() for param in lora_parameters(model))


def merge_lora(model: Child) -> Child:
    """Pour A,B back into W and restore plain Linear modules."""
    for block in model.blocks:
        for owner, name in (
            (block.attn, "c_attn"),
            (block.attn, "c_proj"),
            (block.mlp.net, "0"),
            (block.mlp.net, "2"),
        ):
            module = getattr(owner, name) if owner is not block.mlp.net else owner[int(name)]
            if not isinstance(module, LoRALinear):
                continue
            linear = module.linear
            with torch.no_grad():
                linear.weight.copy_(module.merged_weight())
            linear.weight.requires_grad = True
            if linear.bias is not None:
                linear.bias.requires_grad = True
            if owner is block.mlp.net:
                owner[int(name)] = linear
            else:
                setattr(owner, name, linear)
    for param in model.parameters():
        param.requires_grad = True
    model.tie_weights()
    return model
