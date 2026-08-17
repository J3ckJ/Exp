from dataclasses import dataclass


@dataclass
class ChildConfig:
    """Shape of the newborn: eyes, layers, width. No knowledge lives here."""

    vocab_size: int = 256
    block_size: int = 96
    n_layer: int = 4
    n_head: int = 4
    n_embd: int = 128
    dropout: float = 0.0
    bias: bool = True
