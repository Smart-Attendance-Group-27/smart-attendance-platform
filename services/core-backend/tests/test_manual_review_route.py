from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LECTURER_USER_ID,
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.attendance_verification.manual_review.exception import (
    VerificationAttemptNotFailedError,
    VerificationAttemptNotFoundError,
)
from modules.attendance_verification.manual_review.repository import ManualReviewQueueItemRecord
from modules.attendance_verification.manual_review.route import get_manual_review_service
from modules.identity.auth.dependencies import get_authentication_service

QUEUE_URL = "/api/v1/lecturers/me/manual-reviews"
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_queue_item(review_status: str = "pending") -> ManualReviewQueueItemRecord:
    return ManualReviewQueueItemRecord(
        verification_attempt_id=ATTEMPT_ID,
        session_id=SESSION_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        classroom_code="LH-02",
        scheduled_start_at=CURRENT_TIME,
        student_id=STUDENT_ID,
        registration_number="230701A",
        full_name="Amal Perera",
        failure_reason="face_mismatch",
        started_at=CURRENT_TIME,
        completed_at=CURRENT_TIME,
        geofence_status="passed",
        geofence_failure_reason=None,
        face_status="failed",
        face_similarity_score=0.42,
        face_liveness_passed=False,
        qr_status=None,
        review_status=review_status,
        decision_reason=None,
        reviewed_at=None,
    )


class StubManualReviewService:
    def __init__(
        self,
        items: list[ManualReviewQueueItemRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.items = items if items is not None else [build_queue_item()]
        self.error = error
        self.requested_user_id: UUID | None = None
        self.decision_calls: list[tuple] = []

    async def list_queue_for_user(self, pool, user_id, session_id=None):
        self.requested_user_id = user_id
        if self.error is not None:
            raise self.error
        return self.items

    async def decide_for_user(self, pool, user_id, verification_attempt_id, decision, reason):
        self.decision_calls.append((user_id, verification_attempt_id, decision, reason))
        if self.error is not None:
            raise self.error
        return build_queue_item(decision.value)


def build_client(jwks_document, service: StubManualReviewService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_manual_review_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubManualReviewService:
    return StubManualReviewService()


@pytest.fixture
def client(jwks_document, service: StubManualReviewService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_lists_pending_queue_items(client: TestClient, make_access_token) -> None:
    response = client.get(QUEUE_URL, headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["verificationAttemptId"] == str(ATTEMPT_ID)
    assert body[0]["reviewStatus"] == "pending"


def test_queue_requires_lecturer_role(client: TestClient, make_access_token) -> None:
    response = client.get(QUEUE_URL, headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))))

    assert response.status_code == 403


def test_queue_missing_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubManualReviewService(error=LecturerProfileNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(
            QUEUE_URL,
            headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
        )

    assert response.status_code == 404


@pytest.mark.parametrize("decision", ["approve", "reject", "retry", "escalate"])
def test_decision_endpoint_forwards_decision(
    client: TestClient,
    service: StubManualReviewService,
    make_access_token,
    decision: str,
) -> None:
    response = client.post(
        f"{QUEUE_URL}/{ATTEMPT_ID}/decision",
        headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
        json={"decision": decision, "reason": "reviewed on camera"},
    )

    assert response.status_code == 200
    assert response.json()["reviewStatus"] == decision
    assert len(service.decision_calls) == 1
    called_user_id, called_attempt_id, called_decision, called_reason = service.decision_calls[0]
    assert called_user_id == LECTURER_USER_ID
    assert called_attempt_id == ATTEMPT_ID
    assert called_decision.value == decision
    assert called_reason == "reviewed on camera"


def test_decision_rejects_unknown_decision_value(client: TestClient, make_access_token) -> None:
    response = client.post(
        f"{QUEUE_URL}/{ATTEMPT_ID}/decision",
        headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
        json={"decision": "delete-everything"},
    )

    assert response.status_code == 422


def test_decision_missing_attempt_returns_404(jwks_document, make_access_token) -> None:
    service = StubManualReviewService(error=VerificationAttemptNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.post(
            f"{QUEUE_URL}/{ATTEMPT_ID}/decision",
            headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
            json={"decision": "approve"},
        )

    assert response.status_code == 404


def test_decision_on_non_failed_attempt_returns_409(jwks_document, make_access_token) -> None:
    service = StubManualReviewService(error=VerificationAttemptNotFailedError())
    with build_client(jwks_document, service) as client:
        response = client.post(
            f"{QUEUE_URL}/{ATTEMPT_ID}/decision",
            headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
            json={"decision": "approve"},
        )

    assert response.status_code == 409


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(QUEUE_URL)

    assert response.status_code == 401
