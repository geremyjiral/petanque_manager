"""Terrain label generation utilities."""


def generate_terrain_labels(count: int) -> list[str]:
    """Generate terrain labels A, B, C, ..., Z, AA, AB, ..., ZZ.

    Args:
        count: Number of terrain labels to generate (max 702: 26 + 26*26)

    Returns:
        List of terrain labels

    Raises:
        ValueError: If count > 702 or count < 1
    """
    if count < 1:
        raise ValueError("Count must be at least 1")
    if count > 702:  # 26 + 26*26
        raise ValueError("Maximum 702 terrains supported (A-Z, AA-ZZ)")

    labels: list[str] = []

    # Single letters: A-Z (26)
    for i in range(min(count, 26)):
        labels.append(chr(ord("A") + i))

    # Double letters: AA-ZZ (676)
    if count > 26:
        remaining = count - 26
        for i in range(remaining):
            first = chr(ord("A") + (i // 26))
            second = chr(ord("A") + (i % 26))
            labels.append(f"{first}{second}")

    return labels


def get_terrain_label(index: int) -> str:
    """Get terrain label for a given index (0-based).

    Args:
        index: 0-based index

    Returns:
        Terrain label (A, B, ..., Z, AA, AB, ...)

    Raises:
        ValueError: If index >= 702
    """
    if index < 0:
        raise ValueError("Index must be non-negative")
    if index >= 702:
        raise ValueError("Maximum index is 701 (terrain ZZ)")

    if index < 26:
        return chr(ord("A") + index)
    else:
        adjusted = index - 26
        first = chr(ord("A") + (adjusted // 26))
        second = chr(ord("A") + (adjusted % 26))
        return f"{first}{second}"
