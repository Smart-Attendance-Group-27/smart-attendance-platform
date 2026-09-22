import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


MAX_EVIDENCE_BYTES = 2 * 1024
DEFAULT_MAX_EVIDENCE_AGE_SECONDS = 120
MAX_FUTURE_TOLERANCE_SECONDS = 5
LIVENESS_EVIDENCE_VERSION = 1
LIVENESS_METHOD = "mlkit_challenge"
SUPPORTED_CHALLENGES = frozenset(
    {"blink", "turn_left", "turn_right", "eyes_closed_hold"}
)
REQUIRED_FIELDS = frozenset(
    {
        "version",
        "method",
        "passed",
        "challenges",
        "startedAt",
        "completedAt",
        "engine",
    }
)


Clock = Callable[[], datetime]


class LivenessEvidenceValidationError(ValueError):
    """Raised when supplied liveness evidence violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class LivenessEvidence:
    version: int
    method: str
    passed: bool
    challenges: tuple[str, ...]
    started_at: datetime
    completed_at: datetime
    engine: str


def validate_optional_liveness_evidence(
    serialized_evidence: str | None,
    *,
    enforcement_enabled: bool,
    max_age_seconds: int = DEFAULT_MAX_EVIDENCE_AGE_SECONDS,
    clock: Clock | None = None,
) -> LivenessEvidence | None:
    """Validate supplied evidence and enforce its presence when configured."""
    if serialized_evidence is None:
        if enforcement_enabled:
            raise LivenessEvidenceValidationError(
                "Liveness evidence is required"
            )
        return None

    return validate_liveness_evidence(
        serialized_evidence,
        max_age_seconds=max_age_seconds,
        clock=clock,
    )


def validate_liveness_evidence(
    serialized_evidence: str,
    *,
    max_age_seconds: int = DEFAULT_MAX_EVIDENCE_AGE_SECONDS,
    clock: Clock | None = None,
) -> LivenessEvidence:
    """Parse and validate serialized liveness evidence from a client."""
    if not isinstance(serialized_evidence, str):
        raise LivenessEvidenceValidationError(
            "Liveness evidence must be a JSON string"
        )
    if len(serialized_evidence.encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise LivenessEvidenceValidationError(
            "Liveness evidence exceeds the 2 KB limit"
        )
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError("max_age_seconds must be a non-negative integer")

    try:
        payload = json.loads(serialized_evidence)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise LivenessEvidenceValidationError(
            "Liveness evidence must contain valid JSON"
        ) from error

    if not isinstance(payload, dict):
        raise LivenessEvidenceValidationError(
            "Liveness evidence must be a JSON object"
        )

    fields = set(payload)
    missing_fields = REQUIRED_FIELDS - fields
    if missing_fields:
        raise LivenessEvidenceValidationError(
            f"Liveness evidence is missing: {', '.join(sorted(missing_fields))}"
        )
    unknown_fields = fields - REQUIRED_FIELDS
    if unknown_fields:
        raise LivenessEvidenceValidationError(
            f"Liveness evidence contains unknown fields: "
            f"{', '.join(sorted(unknown_fields))}"
        )

    _validate_fixed_values(payload)
    challenges = _validate_challenges(payload["challenges"])
    started_at = _parse_timestamp(payload["startedAt"], "startedAt")
    completed_at = _parse_timestamp(payload["completedAt"], "completedAt")

    if started_at > completed_at:
        raise LivenessEvidenceValidationError(
            "startedAt must be before or equal to completedAt"
        )

    now = _ensure_aware((clock or _utc_now)(), "Current time")
    if completed_at < now - timedelta(seconds=max_age_seconds):
        raise LivenessEvidenceValidationError("Liveness evidence has expired")
    if completed_at > now + timedelta(seconds=MAX_FUTURE_TOLERANCE_SECONDS):
        raise LivenessEvidenceValidationError(
            "completedAt is too far in the future"
        )

    engine = payload["engine"]
    if not isinstance(engine, str) or not engine.strip():
        raise LivenessEvidenceValidationError(
            "engine must be a non-empty string"
        )

    return LivenessEvidence(
        version=LIVENESS_EVIDENCE_VERSION,
        method=LIVENESS_METHOD,
        passed=True,
        challenges=challenges,
        started_at=started_at.astimezone(UTC),
        completed_at=completed_at.astimezone(UTC),
        engine=engine,
    )


def _validate_fixed_values(payload: dict[str, Any]) -> None:
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise LivenessEvidenceValidationError("version must equal 1")
    if payload["method"] != LIVENESS_METHOD:
        raise LivenessEvidenceValidationError(
            f"method must equal {LIVENESS_METHOD}"
        )
    if payload["passed"] is not True:
        raise LivenessEvidenceValidationError("passed must equal true")


def _validate_challenges(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise LivenessEvidenceValidationError("challenges must be an array")
    if not 2 <= len(value) <= 4:
        raise LivenessEvidenceValidationError(
            "challenges must contain between 2 and 4 values"
        )
    if any(not isinstance(challenge, str) for challenge in value):
        raise LivenessEvidenceValidationError(
            "Every challenge must be a string"
        )

    challenges = tuple(value)
    if len(set(challenges)) != len(challenges):
        raise LivenessEvidenceValidationError(
            "challenges must contain distinct values"
        )

    unsupported = set(challenges) - SUPPORTED_CHALLENGES
    if unsupported:
        raise LivenessEvidenceValidationError(
            f"Unsupported challenges: {', '.join(sorted(unsupported))}"
        )

    return challenges


def _parse_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise LivenessEvidenceValidationError(
            f"{field_name} must be an ISO-8601 string"
        )

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise LivenessEvidenceValidationError(
            f"{field_name} must be a valid ISO-8601 timestamp"
        ) from error

    return _ensure_aware(parsed, field_name)


def _ensure_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LivenessEvidenceValidationError(
            f"{field_name} must include a timezone"
        )
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "DEFAULT_MAX_EVIDENCE_AGE_SECONDS",
    "LivenessEvidence",
    "LivenessEvidenceValidationError",
    "MAX_EVIDENCE_BYTES",
    "MAX_FUTURE_TOLERANCE_SECONDS",
    "SUPPORTED_CHALLENGES",
    "validate_liveness_evidence",
    "validate_optional_liveness_evidence",
]
