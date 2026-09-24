from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.lecturer_correction_requests import service as service_module
from modules.academic.lecturer_correction_requests.exception import (
    CorrectionRequestInvalidError,
    CorrectionTargetNotFoundError,
)
from modules.academic.lecturer_correction_requests.repository import CorrectionRequestRecord
from modules.academic.lecturer_correction_requests.route import get_correction_request_service
from modules.academic.lecturer_correction_requests.schemas import (
    CorrectionCategory,
    CorrectionRequestType,
)
from modules.academic.lecturer_correction_requests.service import CorrectionRequestService
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.identity.auth.dependencies import get_authentication_service

URL = "/api/v1/lecturers/me/correction-requests"
USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
OFFERING_ID = UUID("30000000-0000-0000-0000-000000000001")
OTHER_OFFERING_ID = UUID("30000000-0000-0000-0000-000000000002")
ENTRY_ID = UUID("31000000-0000-0000-0000-000000000001")
REQUEST_ID = UUID("32000000-0000-0000-0000-000000000001")
DESCRIPTION = "The room shown for this lecture is wrong."


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


class FakeProfileRepository:
    def __init__(self, status: str = "active") -> None:
        self.status = status
        self.requested_user_id: UUID | None = None

    async def find_by_user_id(self, connection, user_id):
        self.requested_user_id = user_id
        return LecturerProfileRecord(
            id=LECTURER_ID,
            user_id=USER_ID,
            employee_number="EMP001",
            first_name="Nadeesha",
            middle_name=None,
            last_name="Perera",
            profile_status=self.status,
            university_email="n.perera@staff.uniattend.test",
        )


class FakeRepository:
    def __init__(self) -> None:
        self.inserted: dict | None = None
        self.assigned_lecturer_id: UUID | None = None

    async def is_offering_assigned(self, connection, lecturer_id, course_offering_id):
        self.assigned_lecturer_id = lecturer_id
        return course_offering_id == OFFERING_ID

    async def find_assigned_timetable_offering(self, connection, lecturer_id, timetable_entry_id):
        self.assigned_lecturer_id = lecturer_id
        return OFFERING_ID if timetable_entry_id == ENTRY_ID else None

    async def insert(self, connection, **values):
        self.inserted = values
        return CorrectionRequestRecord(
            id=REQUEST_ID,
            request_type=values["request_type"],
            category=values["category"],
            course_offering_id=values["course_offering_id"],
            timetable_entry_id=values["timetable_entry_id"],
            status="pending",
        )


@pytest.fixture
def audit_calls(monkeypatch):
    calls: list[dict] = []

    async def fake_write_audit_log(connection, **values):
        calls.append(values)

    monkeypatch.setattr(service_module, "write_audit_log", fake_write_audit_log)
    return calls


def build_service(status: str = "active"):
    repository = FakeRepository()
    profiles = FakeProfileRepository(status)
    return CorrectionRequestService(repository, profiles), repository, profiles


async def submit(service, **overrides):
    values = {
        "user_id": USER_ID,
        "request_type": CorrectionRequestType.COURSE_DATA,
        "category": CorrectionCategory.ENROLMENT,
        "course_offering_id": OFFERING_ID,
        "timetable_entry_id": None,
        "description": DESCRIPTION,
    }
    values.update(overrides)
    return await service.submit(FakeTransactionPool(), **values)


async def test_course_request_is_stored_pending_and_audited(audit_calls) -> None:
    service, repository, profiles = build_service()

    record = await submit(service)

    assert record.status == "pending"
    assert profiles.requested_user_id == USER_ID
    assert repository.assigned_lecturer_id == LECTURER_ID
    assert repository.inserted["requested_by"] == USER_ID
    assert repository.inserted["timetable_entry_id"] is None
    assert audit_calls[0]["action"] == "correction_request.submitted"
    assert audit_calls[0]["entity_id"] == REQUEST_ID


async def test_timetable_request_derives_offering_from_entry(audit_calls) -> None:
    service, repository, _ = build_service()

    await submit(
        service,
        request_type=CorrectionRequestType.TIMETABLE,
        category=CorrectionCategory.TIMETABLE_ROOM,
        course_offering_id=None,
        timetable_entry_id=ENTRY_ID,
    )

    assert repository.inserted["course_offering_id"] == OFFERING_ID
    assert repository.inserted["timetable_entry_id"] == ENTRY_ID


async def test_unassigned_course_is_rejected_without_writing(audit_calls) -> None:
    service, repository, _ = build_service()

    with pytest.raises(CorrectionTargetNotFoundError):
        await submit(service, course_offering_id=OTHER_OFFERING_ID)

    assert repository.inserted is None
    assert audit_calls == []


async def test_unassigned_timetable_entry_is_rejected(audit_calls) -> None:
    service, repository, _ = build_service()

    with pytest.raises(CorrectionTargetNotFoundError):
        await submit(
            service,
            request_type=CorrectionRequestType.TIMETABLE,
            category=CorrectionCategory.TIMETABLE_ROOM,
            course_offering_id=None,
            timetable_entry_id=UUID("31000000-0000-0000-0000-0000000000ff"),
        )

    assert repository.inserted is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "too short"},
        {"description": "x" * 1001},
        {"category": CorrectionCategory.TIMETABLE_ROOM},
        {"course_offering_id": None},
    ],
)
async def test_invalid_input_is_rejected(overrides, audit_calls) -> None:
    service, repository, _ = build_service()

    with pytest.raises(CorrectionRequestInvalidError):
        await submit(service, **overrides)

    assert repository.inserted is None


async def test_inactive_lecturer_profile_is_rejected(audit_calls) -> None:
    service, repository, _ = build_service(status="inactive")

    with pytest.raises(LecturerProfileNotFoundError):
        await submit(service)

    assert repository.inserted is None


class StubService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def submit(self, pool, **values):
        self.calls.append(values)
        if self.error is not None:
            raise self.error
        return CorrectionRequestRecord(
            id=REQUEST_ID,
            request_type=values["request_type"].value,
            category=values["category"].value,
            course_offering_id=OFFERING_ID,
            timetable_entry_id=values["timetable_entry_id"],
            status="pending",
        )


def build_client(jwks_document, service: StubService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_correction_request_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def headers(make_access_token, subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",)):
    return {"Authorization": f"Bearer {make_access_token(subject=subject, roles=roles)}"}


BODY = {
    "requestType": "course_data",
    "category": "enrolment",
    "courseOfferingId": str(OFFERING_ID),
    "description": DESCRIPTION,
}


def test_lecturer_submits_request(jwks_document, make_access_token) -> None:
    service = StubService()
    with build_client(jwks_document, service) as client:
        response = client.post(URL, json=BODY, headers=headers(make_access_token))

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert len(service.calls) == 1


def test_requester_identity_cannot_be_supplied_by_client(jwks_document, make_access_token) -> None:
    with build_client(jwks_document, StubService()) as client:
        response = client.post(
            URL,
            json={**BODY, "requestedBy": str(USER_ID)},
            headers=headers(make_access_token),
        )

    assert response.status_code == 422


def test_non_lecturer_is_forbidden(jwks_document, make_access_token) -> None:
    service = StubService()
    with build_client(jwks_document, service) as client:
        response = client.post(
            URL,
            json=BODY,
            headers=headers(make_access_token, LINKED_STUDENT_SUBJECT, ("student",)),
        )

    assert response.status_code == 403
    assert service.calls == []


def test_unauthenticated_is_rejected(jwks_document) -> None:
    with build_client(jwks_document, StubService()) as client:
        response = client.post(URL, json=BODY)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (CorrectionTargetNotFoundError("x"), 404),
        (LecturerProfileNotFoundError("x"), 404),
        (CorrectionRequestInvalidError("bad"), 422),
    ],
)
def test_domain_errors_map_to_http(jwks_document, make_access_token, error, status_code) -> None:
    with build_client(jwks_document, StubService(error)) as client:
        response = client.post(URL, json=BODY, headers=headers(make_access_token))

    assert response.status_code == status_code
