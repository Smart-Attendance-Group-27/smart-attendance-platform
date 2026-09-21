from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    ADMINISTRATOR_USER_ID,
    LINKED_ADMINISTRATOR_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.attendance_policy.repository import (
    AttendancePolicyRepository,
    PolicySnapshot,
)
from modules.academic.attendance_policy.route import get_attendance_policy_service
from modules.academic.attendance_policy.schemas import PolicyWriteRequest
from modules.academic.attendance_policy.service import AttendancePolicyService
from modules.contracts.attendance_policy import AttendancePolicy, AttendancePolicyProvider
from modules.identity.auth.dependencies import get_authentication_service


POLICY_ID = UUID("80000000-0000-0000-0000-000000000001")
UPDATED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
POLICY_URL = "/api/v1/administrators/me/attendance-policy"
VALID_BODY = {
    "checkInWindowMinutes": 15,
    "lateThresholdMinutes": 10,
    "qrDefaultValidityMinutes": 5,
    "faceConfidenceThresholdPercent": 75,
}


class FakePolicyConnection:
    def __init__(self, row=None) -> None:
        self.row = row
        self.queries: list[tuple[str, tuple]] = []

    async def fetchrow(self, query, *args):
        self.queries.append((query, args))
        return self.row

    async def fetchval(self, query, *args):
        self.queries.append((query, args))
        return POLICY_ID

    async def execute(self, query, *args):
        self.queries.append((query, args))


@pytest.mark.asyncio
async def test_repository_implements_i04_and_returns_none_without_an_active_row() -> None:
    repository = AttendancePolicyRepository()
    assert isinstance(repository, AttendancePolicyProvider)
    connection = FakePolicyConnection({
        "check_in_window_minutes": 20,
        "late_threshold_minutes": 8,
        "qr_default_validity_minutes": 6,
    })
    assert await repository.get_active(connection) == AttendancePolicy(20, 8, 6)
    assert "WHERE is_active" in connection.queries[0][0]
    assert await repository.get_active(FakePolicyConnection()) is None


@pytest.mark.asyncio
async def test_repository_replaces_policy_and_face_threshold_together() -> None:
    repository = AttendancePolicyRepository()
    connection = FakePolicyConnection()
    await repository.lock_for_replace(connection)
    policy_id = await repository.replace_active(
        connection,
        actor_user_id=ADMINISTRATOR_USER_ID,
        check_in_window_minutes=20,
        late_threshold_minutes=8,
        qr_default_validity_minutes=6,
        face_confidence_threshold_percent=82,
    )
    assert policy_id == POLICY_ID
    queries = [query for query, _ in connection.queries]
    assert "pg_advisory_xact_lock" in queries[0]
    assert "UPDATE academic.attendance_policies" in queries[1]
    assert "INSERT INTO academic.attendance_policies" in queries[2]
    assert "UPDATE face_verification.verification_configs" in queries[3]
    assert "INSERT INTO face_verification.verification_configs" in queries[4]
    assert connection.queries[4][1][0] == Decimal("0.82")


@pytest.mark.asyncio
async def test_current_policy_reads_face_threshold_and_updater_name() -> None:
    connection = FakePolicyConnection({
        "id": POLICY_ID,
        "check_in_window_minutes": 15,
        "late_threshold_minutes": 10,
        "qr_default_validity_minutes": 5,
        "similarity_threshold": 0.825,
        "updated_at": UPDATED_AT,
        "updated_by_name": "Dr. Sunimal Rathnayake",
    })
    snapshot = await AttendancePolicyRepository().get_current(connection)
    assert snapshot is not None
    assert snapshot.face_confidence_threshold_percent == 83
    assert snapshot.updated_by_name == "Dr. Sunimal Rathnayake"


class TransactionConnection(FakePolicyConnection):
    def __init__(self) -> None:
        super().__init__()
        self.in_transaction = False

    @asynccontextmanager
    async def transaction(self):
        self.in_transaction = True
        try:
            yield self
        finally:
            self.in_transaction = False


class TransactionPool:
    def __init__(self) -> None:
        self.connection = TransactionConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


class FakePolicyRepository:
    def __init__(self) -> None:
        self.current = PolicySnapshot(POLICY_ID, 15, 10, 5, 75, UPDATED_AT, None)
        self.events: list[str] = []

    async def lock_for_replace(self, connection):
        assert connection.in_transaction
        self.events.append("lock")

    async def get_current(self, connection):
        assert connection.in_transaction
        self.events.append("read")
        return self.current

    async def replace_active(self, connection, **values):
        assert connection.in_transaction
        self.events.append("replace")
        self.current = PolicySnapshot(
            POLICY_ID, values["check_in_window_minutes"],
            values["late_threshold_minutes"], values["qr_default_validity_minutes"],
            values["face_confidence_threshold_percent"], UPDATED_AT,
            "Dr. Sunimal Rathnayake",
        )
        return POLICY_ID


@pytest.mark.asyncio
async def test_service_audits_policy_and_face_change_inside_transaction() -> None:
    pool = TransactionPool()
    repository = FakePolicyRepository()
    service = AttendancePolicyService(repository=repository)
    result = await service.replace_active(
        pool, ADMINISTRATOR_USER_ID, PolicyWriteRequest.model_validate({
            **VALID_BODY, "checkInWindowMinutes": 20,
        }),
    )
    assert result.check_in_window_minutes == 20
    assert repository.events == ["lock", "read", "replace", "read"]
    audit_query, audit_args = pool.connection.queries[-1]
    assert "audit.audit_logs" in audit_query
    assert audit_args[0] == ADMINISTRATOR_USER_ID
    assert audit_args[2] == "attendance_policy.update"
    assert pool.connection.in_transaction is False


class StubPolicyService:
    def __init__(self) -> None:
        self.saved: PolicyWriteRequest | None = None
        self.snapshot = PolicySnapshot(POLICY_ID, 15, 10, 5, 75, UPDATED_AT, None)

    async def get_current(self, pool):
        return self.snapshot

    async def replace_active(self, pool, actor_user_id, body):
        assert actor_user_id == ADMINISTRATOR_USER_ID
        self.saved = body
        return self.snapshot


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_attendance_policy_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def authorize(make_access_token, *, role="administrator", subject=LINKED_ADMINISTRATOR_SUBJECT):
    token = make_access_token(subject=subject, roles=(role,))
    return {"Authorization": f"Bearer {token}"}


def test_get_and_put_policy_use_c17_shape(jwks_document, make_access_token) -> None:
    service = StubPolicyService()
    with build_client(jwks_document, service) as client:
        response = client.get(POLICY_URL, headers=authorize(make_access_token))
        updated = client.put(POLICY_URL, headers=authorize(make_access_token), json=VALID_BODY)
    assert response.status_code == 200
    assert updated.status_code == 200
    assert updated.json() == {
        **VALID_BODY,
        "updatedAt": UPDATED_AT.isoformat().replace("+00:00", "Z"),
        "updatedByName": None,
    }
    assert service.saved is not None
    assert service.saved.qr_default_validity_minutes == 5


@pytest.mark.parametrize("body", [
    {**VALID_BODY, "checkInWindowMinutes": 0},
    {**VALID_BODY, "lateThresholdMinutes": 16},
    {**VALID_BODY, "qrDefaultValidityMinutes": 61},
    {**VALID_BODY, "faceConfidenceThresholdPercent": 49},
    {**VALID_BODY, "checkInWindowMinutes": True},
    {**VALID_BODY, "extra": 1},
])
def test_invalid_policy_returns_contract_error(jwks_document, make_access_token, body) -> None:
    service = StubPolicyService()
    with build_client(jwks_document, service) as client:
        response = client.put(POLICY_URL, headers=authorize(make_access_token), json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_POLICY"
    assert service.saved is None


def test_missing_policy_body_returns_contract_error(jwks_document, make_access_token) -> None:
    with build_client(jwks_document, StubPolicyService()) as client:
        response = client.put(POLICY_URL, headers=authorize(make_access_token))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_POLICY"


def test_policy_routes_enforce_administrator_role(jwks_document, make_access_token) -> None:
    service = StubPolicyService()
    with build_client(jwks_document, service) as client:
        assert client.get(POLICY_URL).status_code == 401
        assert client.get(POLICY_URL, headers=authorize(
            make_access_token, role="student", subject=LINKED_STUDENT_SUBJECT,
        )).status_code == 403
        assert client.put(POLICY_URL, headers=authorize(
            make_access_token, role="student", subject=LINKED_STUDENT_SUBJECT,
        ), json=VALID_BODY).status_code == 403
