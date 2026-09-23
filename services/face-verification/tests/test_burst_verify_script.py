from unittest.mock import patch

import pytest

from scripts.burst_verify import (
    attempt_numbers_are_contiguous,
    percentile,
    require_local_database,
)


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "::1", "host.docker.internal"],
)
def test_accepts_only_explicit_local_database_hosts(host: str) -> None:
    with patch("scripts.burst_verify._build_database_url") as build_url:
        build_url.return_value.host = host
        assert require_local_database(object()) == host.casefold()  # type: ignore[arg-type]


def test_rejects_a_remote_database_before_connecting() -> None:
    with patch("scripts.burst_verify._build_database_url") as build_url:
        build_url.return_value.host = "db.example.test"
        with pytest.raises(ValueError, match="restricted to a local"):
            require_local_database(object())  # type: ignore[arg-type]


def test_reports_interpolated_latency_percentiles() -> None:
    assert percentile([10, 20, 30, 40], 0.50) == 25
    assert percentile([10, 20, 30, 40], 0.95) == pytest.approx(38.5)
    assert percentile([], 0.95) == 0


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [([1], True), ([1, 2, 3], True), ([], True), ([1, 3], False), ([2], False)],
)
def test_attempt_number_integrity(numbers: list[int], expected: bool) -> None:
    assert attempt_numbers_are_contiguous(numbers) is expected
