"""Random seed management."""

import random


def get_or_generate_seed(seed: int | None = None) -> int:
    """Get the provided seed or generate a new one.

    Args:
        seed: Optional seed value. If None, generates a random seed.

    Returns:
        Seed value to use
    """
    if seed is not None:
        return seed
    return random.randint(0, 2**31 - 1)


def set_random_seed(seed: int) -> None:
    """Set the random seed for reproducibility.

    Args:
        seed: Seed value
    """
    random.seed(seed)
