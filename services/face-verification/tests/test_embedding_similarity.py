import math

import pytest

from services.embedding_similarity import cosine_similarity


def test_identical_embeddings_have_maximum_similarity() -> None:
    score = cosine_similarity(
        (0.1, 0.2, 0.3),
        (0.1, 0.2, 0.3),
    )

    assert score == pytest.approx(1.0)


def test_opposite_embeddings_have_minimum_similarity() -> None:
    score = cosine_similarity(
        (1.0, 2.0, 3.0),
        (-1.0, -2.0, -3.0),
    )

    assert score == pytest.approx(-1.0)


def test_orthogonal_embeddings_have_zero_similarity() -> None:
    score = cosine_similarity(
        (1.0, 0.0),
        (0.0, 1.0),
    )

    assert score == pytest.approx(0.0)


def test_rejects_embeddings_with_different_dimensions() -> None:
    with pytest.raises(
        ValueError,
        match="Embeddings must have the same dimension",
    ):
        cosine_similarity((1.0, 2.0), (1.0, 2.0, 3.0))


@pytest.mark.parametrize(
    ("reference_embedding", "captured_embedding", "expected_message"),
    [
        ((), (1.0,), "Reference embedding cannot be empty"),
        ((1.0,), (), "Captured embedding cannot be empty"),
    ],
)
def test_rejects_empty_embedding(
    reference_embedding: tuple[float, ...],
    captured_embedding: tuple[float, ...],
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        cosine_similarity(reference_embedding, captured_embedding)


@pytest.mark.parametrize(
    ("reference_embedding", "captured_embedding", "expected_message"),
    [
        ((0.0, 0.0), (1.0, 2.0), "Reference embedding cannot be a zero vector"),
        ((1.0, 2.0), (0.0, 0.0), "Captured embedding cannot be a zero vector"),
    ],
)
def test_rejects_zero_vector(
    reference_embedding: tuple[float, ...],
    captured_embedding: tuple[float, ...],
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        cosine_similarity(reference_embedding, captured_embedding)


@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_rejects_non_finite_values(invalid_value: float) -> None:
    with pytest.raises(
        ValueError,
        match="Captured embedding must contain only finite values",
    ):
        cosine_similarity(
            (1.0, 2.0),
            (1.0, invalid_value),
        )
