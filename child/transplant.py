from __future__ import annotations

import torch
import torch.nn as nn

from child.config import ChildConfig
from child.model import Block, Child


def _copy_linear(dst: nn.Linear, src: nn.Linear) -> None:
    out, inn = src.weight.shape
    dst.weight.data[:out, :inn] = src.weight.data
    if src.bias is not None and dst.bias is not None:
        dst.bias.data[:out] = src.bias.data


def _copy_ln(dst: nn.LayerNorm, src: nn.LayerNorm) -> None:
    width = src.weight.shape[0]
    dst.weight.data[:width] = src.weight.data
    dst.bias.data[:width] = src.bias.data


def _copy_block(dst: Block, src: Block) -> None:
    _copy_ln(dst.ln1, src.ln1)
    _copy_ln(dst.ln2, src.ln2)
    _copy_linear(dst.attn.c_attn, src.attn.c_attn)
    _copy_linear(dst.attn.c_proj, src.attn.c_proj)
    _copy_linear(dst.mlp.net[0], src.mlp.net[0])
    _copy_linear(dst.mlp.net[2], src.mlp.net[2])


def _identity_block(block: Block) -> None:
    """Residual block that leaves the stream unchanged: attn and MLP write zeros."""
    for module in (
        block.attn.c_attn,
        block.attn.c_proj,
        block.mlp.net[0],
        block.mlp.net[2],
    ):
        nn.init.zeros_(module.weight)
        if module.bias is not None:
            nn.init.zeros_(module.bias)


def transplant(old: Child, config: ChildConfig) -> Child:
    """Grow a bigger body while keeping the function the old mouth already learned."""
    if config.vocab_size != old.config.vocab_size:
        raise ValueError("transplant keeps the same byte alphabet")
    if config.n_embd != old.config.n_embd:
        raise ValueError("width change is not function-preserving with this attention layout")
    if config.n_head != old.config.n_head:
        raise ValueError("head count must stay with the old width")
    if config.n_layer < old.config.n_layer:
        raise ValueError("cannot shrink depth")
    if config.block_size < old.config.block_size:
        raise ValueError("cannot shrink the mouth")

    young = Child(config)
    with torch.no_grad():
        young.token_emb.weight.copy_(old.token_emb.weight)
        span = old.config.block_size
        young.pos_emb.weight[:span].copy_(old.pos_emb.weight[:span])
        _copy_ln(young.ln_f, old.ln_f)
        for index, src in enumerate(old.blocks):
            _copy_block(young.blocks[index], src)
        for index in range(old.config.n_layer, config.n_layer):
            _identity_block(young.blocks[index])
    young.tie_weights()
    young.eval()
    return young
