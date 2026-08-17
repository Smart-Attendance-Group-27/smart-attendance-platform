import math
from collections.abc import Sequence


def cosine_similarity(reference_embedding: Sequence[float],captured_embedding: Sequence[float],) -> float:

    reference_values = _convert_embedding(reference_embedding,name="Reference embedding",)
    captured_values = _convert_embedding(captured_embedding,name="Captured embedding",)

    if len(reference_values) != len(captured_values):
        raise ValueError("Embeddings must have the same dimension")

    normalized_reference = _normalize_embedding(reference_values,name="Reference embedding",)
    normalized_captured = _normalize_embedding(captured_values,name="Captured embedding",)

    score = math.fsum(reference_value * captured_value
        for reference_value, captured_value in zip(normalized_reference,normalized_captured,strict=True,)
    )

    # Clamp only to the mathematically valid cosine-similarity range.
    return max(-1.0, min(1.0, score))

# Convert an embedding to finite Python floats.
def _convert_embedding(embedding: Sequence[float],*,name: str,) -> tuple[float, ...]:

    try:
        values = tuple(float(value) for value in embedding)

    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain only numeric values") from error

    if not values:
        raise ValueError(f"{name} cannot be empty")

    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{name} must contain only finite values")

    return values

# Normalize one vector defensively before calculating its dot product."""
def _normalize_embedding(embedding: tuple[float, ...],*,name: str,) -> tuple[float, ...]:

    magnitude = math.hypot(*embedding)

    if not math.isfinite(magnitude) or magnitude == 0:
        raise ValueError(f"{name} cannot be a zero vector")

    return tuple(value / magnitude for value in embedding)


__all__ = ["cosine_similarity"]
