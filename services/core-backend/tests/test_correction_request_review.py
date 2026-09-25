from contextlib import asynccontextmanager
from datetime import UTC, datetime, time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_ADMINISTRATOR_SUBJECT,
    LINKED_LECTURER_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.admin_correction_requests import service as service_module
from modules.academic.admin_correction_requests.exception import (
    CorrectionRequestNotFoundError,
    InvalidDecisionError,
    InvalidReviewNoteError,
)
from modules.academic.admin_correction_requests.repository import AdminCorrectionRequestRecord
from modules.academic.admin_correction_requests.route import get_admin_correction_request_service
from modules.academic.admin_correction_requests.schemas import ReviewDecision
from modules.academic.admin_correction_requests.service import AdminCorrectionRequestService
from modules.identity.auth.dependencies import get_authentication_service

LIST_URL = "/api/v1/administrators/me/correction-requests"
REQUEST_ID = UUID("32000000-0000-0000-0000-000000000001")
ADMIN_USER_ID = UUID("20000000-0000-0000-0000-000000000003")
NOW = datetime(2026, 9, 25, 4, 0, tzinfo=UTC)


def build_record(status: str = "pending") -> AdminCorrectionRequestRecord:
    return AdminCorrectionRequestRecord(
        id=REQUEST_ID,
        request_type="timetable",
        category="timetable_room",
        requester_name="Nadeesha Perera",
        requester_employee_number="EMP001",
        course_code="CS3203",
        course_name="Software Engineering Project",
        timetable_day_of_week=1,
        timetable_start_time=time(9, 0),
        timetable_end_time=time(11, 0),
        timetable_classroom_code="LH-02",
        description="The room shown is not the one we use.",
        status=status,
        review_note=None,
        created_at=NOW,
        reviewed_at=None,
    )


class FakeTransactionConnection:
    @asynccontextmanager
    async def transaction(self):
        yield


class FakeTransactionPool:
    def __init__(self) -> None:
        self.connection = FakeTransactionConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


class FakeRepository:
    def __init__(self, status: str | None = "pending") -> None:
        self.status = status
        self.decision: dict | None = None

    async def lock_status(self, connection, request_id):
        return self.status

    async def record_decision(self, connection, request_id, **values):
        self.decision = {"request_id": request_id, **values}

    async def find_request(self, connection, request_id):
        return build_record(self.decision["status"] if self.decision else "pending")


@pytest.fixture
def audit_calls(monkeypatch):
    calls: list[dict] = []

    async def fake_write_audit_log(connection, **values):
        calls.append(values)

    monkeypatch.setattr(service_module, "write_audit_log", fake_write_audit_log)
    return calls


async def decide(repository: FakeRepository, decision: ReviewDecision, note: str = ""):
    service = AdminCorrectionRequestService(repository)
    return await service.decide(
        FakeTransactionPool(),
        actor_user_id=ADMIN_USER_ID,
        request_id=REQUEST_ID,
        decision=decision,
        note=note,
    )


async def test_pending_request_can_be_approved_and_is_audited(audit_calls) -> None:
    repository = FakeRepository("pending")

    record = await decide(repository, ReviewDecision.APPROVED, "  Will update the timetable.  ")

    assert record.status == "approved"
    assert repository.decision["reviewed_by"] == ADMIN_USER_ID
    assert repository.decision["review_note"] == "Will update the timetable."
    assert audit_calls[0]["action"] == "correction_request.decided"
    assert audit_calls[0]["old_values"] == {"status": "pending"}
    assert audit_calls[0]["new_values"]["status"] == "approved"


async def test_rejection_requires_a_reason(audit_calls) -> None:
    repository = FakeRepository("pending")

    with pytest.raises(InvalidReviewNoteError):
        await decide(repository, ReviewDecision.REJECTED, " ")

    assert repository.decision is None
    assert audit_calls == []


@pytest.mark.parametrize(
    ("current", "decision"),
    [
        ("pending", ReviewDecision.RESOLVED),
        ("approved", ReviewDecision.APPROVED),
        ("approved", ReviewDecision.REJECTED),
        ("rejected", ReviewDecision.APPROVED),
        ("resolved", ReviewDecision.RESOLVED),
    ],
)
async def test_invalid_transitions_are_refused(current, decision, audit_calls) -> None:
    repository = FakeRepository(current)

    with pytest.raises(InvalidDecisionError):
        await decide(repository, decision, "a reason")

    assert repository.decision is None


async def test_approved_request_can_be_resolved(audit_calls) -> None:
    record = await decide(FakeRepository("approved"), ReviewDecision.RESOLVED)

    assert record.status == "resolved"


async def test_unknown_request_is_not_found(audit_calls) -> None:
    with pytest.raises(CorrectionRequestNotFoundError):
        await decide(FakeRepository(None), ReviewDecision.APPROVED)


class StubService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.list_status: str | None = None
        self.decisions: list[dict] = []

    async def list_requests(self, pool, *, status):
        self.list_status = status
        return [build_record()]

    async def decide(self, pool, **values):
        self.decisions.append(values)
        if self.error is not None:
            raise self.error
        return build_record(values["decision"].value)


def build_client(jwks_document, service: StubService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_correction_request_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def headers(make_access_token, subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",)):
    return {"Authorization": f"Bearer {make_access_token(subject=subject, roles=roles)}"}


def test_admin_lists_requests_with_optional_status_filter(jwks_document, make_access_token) -> None:
    service = StubService()
    with build_client(jwks_document, service) as client:
        response = client.get(f"{LIST_URL}?status=pending", headers=headers(make_access_token))

    assert response.status_code == 200
    assert response.json()[0]["requesterName"] == "Nadeesha Perera"
    assert response.json()[0]["timetableStartTime"] == "09:00:00"
    assert service.list_status == "pending"


def test_status_filter_rejects_unknown_values(jwks_document, make_access_token) -> None:
    with build_client(jwks_document, StubService()) as client:
        response = client.get(f"{LIST_URL}?status=bogus", headers=headers(make_access_token))

    assert response.status_code == 422


def test_lecturer_cannot_list_or_decide(jwks_document, make_access_token) -> None:
    service = StubService()
    lecturer = headers(make_access_token, LINKED_LECTURER_SUBJECT, ("lecturer",))
    with build_client(jwks_document, service) as client:
        listed = client.get(LIST_URL, headers=lecturer)
        decided = client.post(
            f"{LIST_URL}/{REQUEST_ID}/decision", json={"decision": "approved"}, headers=lecturer
        )

    assert listed.status_code == 403
    assert decided.status_code == 403
    assert service.decisions == []


def test_admin_decision_uses_the_token_identity(jwks_document, make_access_token) -> None:
    service = StubService()
    with build_client(jwks_document, service) as client:
        response = client.post(
            f"{LIST_URL}/{REQUEST_ID}/decision",
            json={"decision": "approved", "note": "ok"},
            headers=headers(make_access_token),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert service.decisions[0]["actor_user_id"] == ADMIN_USER_ID


def test_decision_rejects_client_supplied_identity(jwks_document, make_access_token) -> None:
    with build_client(jwks_document, StubService()) as client:
        response = client.post(
            f"{LIST_URL}/{REQUEST_ID}/decision",
            json={"decision": "approved", "reviewedBy": str(ADMIN_USER_ID)},
            headers=headers(make_access_token),
        )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (CorrectionRequestNotFoundError(), 404),
        (InvalidDecisionError("no"), 409),
        (InvalidReviewNoteError("no"), 422),
    ],
)
def test_review_errors_map_to_http(jwks_document, make_access_token, error, status_code) -> None:
    with build_client(jwks_document, StubService(error)) as client:
        response = client.post(
            f"{LIST_URL}/{REQUEST_ID}/decision",
            json={"decision": "approved"},
            headers=headers(make_access_token),
        )

    assert response.status_code == status_code
