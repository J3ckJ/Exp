from dataclasses import dataclass


@dataclass
class ChildConfig:
    """Shape of the body: eyes, layers, width. No knowledge lives here."""

    vocab_size: int = 256
    block_size: int = 96
    n_layer: int = 4
    n_head: int = 4
    n_embd: int = 128
    dropout: float = 0.0
    bias: bool = True


def toddler_config() -> ChildConfig:
    return ChildConfig()


def preschooler_config() -> ChildConfig:
    """Growth spurt: longer mouth, wider head, still a child not an adult."""
    return ChildConfig(
        vocab_size=256,
        block_size=192,
        n_layer=6,
        n_head=6,
        n_embd=192,
        dropout=0.1,
        bias=True,
    )


def schoolkid_config() -> ChildConfig:
    """Next body on the self-grow ladder. A bigger random mouth, not downloaded knowledge."""
    return ChildConfig(
        vocab_size=256,
        block_size=256,
        n_layer=8,
        n_head=8,
        n_embd=256,
        dropout=0.1,
        bias=True,
    )


AGES: dict[str, ChildConfig] = {
    "toddler": toddler_config(),
    "preschooler": preschooler_config(),
    "schoolkid": schoolkid_config(),
}

LADDER: tuple[str, ...] = ("toddler", "preschooler", "schoolkid")


def configs_match(left: ChildConfig, right: ChildConfig) -> bool:
    return (
        left.vocab_size == right.vocab_size
        and left.block_size == right.block_size
        and left.n_layer == right.n_layer
        and left.n_head == right.n_head
        and left.n_embd == right.n_embd
    )


def age_name(config: ChildConfig) -> str:
    for name, template in AGES.items():
        if configs_match(config, template):
            return name
    return "unknown"


def next_age(name: str) -> str | None:
    if name not in LADDER:
        return None
    index = LADDER.index(name)
    if index + 1 >= len(LADDER):
        return None
    return LADDER[index + 1]
