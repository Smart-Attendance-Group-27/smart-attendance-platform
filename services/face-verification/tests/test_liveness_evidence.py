import json
from datetime import UTC, datetime

import pytest

from services.liveness_evidence import (
    LivenessEvidenceValidationError,
    MAX_EVIDENCE_BYTES,
    validate_liveness_evidence,
    validate_optional_liveness_evidence,
)


NOW = datetime(2026, 9, 22, 8, 0, 30, tzinfo=UTC)


def evidence(**overrides: object) -> str:
    payload: dict[str, object] = {
        "version": 1,
        "method": "mlkit_challenge",
        "passed": True,
        "challenges": ["turn_left", "eyes_closed_hold"],
        "startedAt": "2026-09-22T08:00:00Z",
        "completedAt": "2026-09-22T08:00:10Z",
        "engine": "uniattend-mobile-liveness",
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":"))


def validate(serialized_evidence: str, *, max_age_seconds: int = 120):
    return validate_liveness_evidence(
        serialized_evidence,
        max_age_seconds=max_age_seconds,
        clock=lambda: NOW,
    )


def test_accepts_valid_evidence_and_normalizes_timestamps_to_utc() -> None:
    result = validate(
        evidence(
            challenges=["blink", "turn_right"],
            startedAt="2026-09-22T13:30:00+05:30",
            completedAt="2026-09-22T13:30:10+05:30",
        )
    )

    assert result.version == 1
    assert result.method == "mlkit_challenge"
    assert result.passed is True
    assert result.challenges == ("blink", "turn_right")
    assert result.started_at == datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
    assert result.completed_at == datetime(2026, 9, 22, 8, 0, 10, tzinfo=UTC)
    assert result.engine == "uniattend-mobile-liveness"


@pytest.mark.parametrize(
    "challenges",
    [
        ["blink", "turn_left"],
        ["blink", "turn_left", "turn_right"],
        ["blink", "turn_left", "turn_right", "eyes_closed_hold"],
    ],
)
def test_accepts_two_to_four_distinct_supported_challenges(
    challenges: list[str],
) -> None:
    result = validate(evidence(challenges=challenges))

    assert result.challenges == tuple(challenges)


@pytest.mark.parametrize("serialized", ["{", "[]", "null"])
def test_rejects_invalid_json_or_non_object_payloads(serialized: str) -> None:
    with pytest.raises(LivenessEvidenceValidationError):
        validate(serialized)


def test_rejects_payload_larger_than_two_kibibytes() -> None:
    serialized = evidence(engine="x" * MAX_EVIDENCE_BYTES)

    with pytest.raises(LivenessEvidenceValidationError, match="2 KB"):
        validate(serialized)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("version", 2, "version"),
        ("version", True, "version"),
        ("method", "other", "method"),
        ("passed", False, "passed"),
        ("passed", 1, "passed"),
    ],
)
def test_rejects_incorrect_fixed_values(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(LivenessEvidenceValidationError, match=message):
        validate(evidence(**{field: value}))


@pytest.mark.parametrize(
    "challenges",
    [
        ["turn_left"],
        ["blink", "turn_left", "turn_right", "eyes_closed_hold", "blink"],
    ],
)
def test_rejects_challenge_counts_outside_two_to_four(
    challenges: list[str],
) -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="between 2 and 4"):
        validate(evidence(challenges=challenges))


def test_rejects_duplicate_challenges() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="distinct"):
        validate(evidence(challenges=["turn_left", "turn_left"]))


def test_rejects_unsupported_challenges() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="Unsupported"):
        validate(evidence(challenges=["turn_left", "smile"]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("startedAt", "not-a-date"),
        ("completedAt", "2026-09-22T08:00:10"),
    ],
)
def test_rejects_malformed_or_timezone_naive_timestamps(
    field: str,
    value: str,
) -> None:
    with pytest.raises(LivenessEvidenceValidationError, match=field):
        validate(evidence(**{field: value}))


def test_rejects_started_at_after_completed_at() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="startedAt"):
        validate(
            evidence(
                startedAt="2026-09-22T08:00:20Z",
                completedAt="2026-09-22T08:00:10Z",
            )
        )


def test_accepts_evidence_exactly_at_maximum_age() -> None:
    result = validate(
        evidence(
            startedAt="2026-09-22T07:58:20Z",
            completedAt="2026-09-22T07:58:30Z",
        )
    )

    assert result.completed_at == datetime(2026, 9, 22, 7, 58, 30, tzinfo=UTC)


def test_rejects_expired_evidence() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="expired"):
        validate(
            evidence(
                startedAt="2026-09-22T07:58:19Z",
                completedAt="2026-09-22T07:58:29Z",
            )
        )


def test_accepts_completed_at_exactly_at_future_tolerance() -> None:
    result = validate(
        evidence(
            startedAt="2026-09-22T08:00:30Z",
            completedAt="2026-09-22T08:00:35Z",
        )
    )

    assert result.completed_at == datetime(2026, 9, 22, 8, 0, 35, tzinfo=UTC)


def test_rejects_completed_at_beyond_future_tolerance() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="future"):
        validate(
            evidence(
                startedAt="2026-09-22T08:00:31Z",
                completedAt="2026-09-22T08:00:36Z",
            )
        )


def test_rejects_missing_and_unknown_fields() -> None:
    missing_engine = json.loads(evidence())
    missing_engine.pop("engine")

    with pytest.raises(LivenessEvidenceValidationError, match="missing"):
        validate(json.dumps(missing_engine))
    with pytest.raises(LivenessEvidenceValidationError, match="unknown fields"):
        validate(evidence(extra="value"))


def test_rejects_blank_engine() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="engine"):
        validate(evidence(engine=" "))


def test_allows_missing_evidence_when_enforcement_is_disabled() -> None:
    result = validate_optional_liveness_evidence(
        None,
        enforcement_enabled=False,
        clock=lambda: NOW,
    )

    assert result is None


def test_rejects_missing_evidence_when_enforcement_is_enabled() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="required"):
        validate_optional_liveness_evidence(
            None,
            enforcement_enabled=True,
            clock=lambda: NOW,
        )


@pytest.mark.parametrize("enforcement_enabled", [False, True])
@pytest.mark.parametrize(
    "serialized_evidence",
    [
        "{",
        evidence(passed=False),
        evidence(
            startedAt="2026-09-22T07:57:59Z",
            completedAt="2026-09-22T07:58:09Z",
        ),
    ],
)
def test_rejects_invalid_supplied_evidence_in_every_enforcement_mode(
    enforcement_enabled: bool,
    serialized_evidence: str,
) -> None:
    with pytest.raises(LivenessEvidenceValidationError):
        validate_optional_liveness_evidence(
            serialized_evidence,
            enforcement_enabled=enforcement_enabled,
            clock=lambda: NOW,
        )


def test_uses_configured_maximum_age_for_supplied_evidence() -> None:
    with pytest.raises(LivenessEvidenceValidationError, match="expired"):
        validate_optional_liveness_evidence(
            evidence(),
            enforcement_enabled=False,
            max_age_seconds=10,
            clock=lambda: NOW,
        )
