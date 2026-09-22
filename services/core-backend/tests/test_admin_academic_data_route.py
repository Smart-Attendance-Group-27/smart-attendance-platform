from datetime import date, time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_ADMINISTRATOR_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.admin_academic_data.exception import AcademicConflictError
from modules.academic.admin_academic_data.repository import (
    AdminCourseOfferingRecord,
    AdminCourseRecord,
    AdminEnrolmentRecord,
    AdminTimetableEntryRecord,
)
from modules.academic.admin_academic_data.route import get_admin_academic_data_service
from modules.academic.admin_academic_data.service import SOURCE_CONNECTION_STATUS, AcademicData
from modules.identity.auth.dependencies import get_authentication_service

ACADEMIC_DATA_URL = "/api/v1/administrators/me/academic-data"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


def build_academic_data() -> AcademicData:
    return AcademicData(
        source_connection_status=SOURCE_CONNECTION_STATUS,
        courses=[
            AdminCourseRecord(
                id=UUID("36000000-0000-0000-0000-000000000001"),
                course_code="CS3203",
                course_name="Software Engineering Project",
                department_id=UUID("35000000-0000-0000-0000-000000000001"),
                department_name="Computer Science",
                credits=3,
                status="active",
            )
        ],
        offerings=[
            AdminCourseOfferingRecord(
                id=UUID("37000000-0000-0000-0000-000000000001"),
                course_id=UUID("36000000-0000-0000-0000-000000000001"),
                semester_id=UUID("34000000-0000-0000-0000-000000000001"),
                lecturer_id=UUID("38000000-0000-0000-0000-000000000001"),
                lecturer_name="N. Perera",
                course_code="CS3203",
                course_name="Software Engineering Project",
                semester_label="Semester 1 (2026)",
                batch_year=2023,
                course_type="core",
                attendance_threshold_percent=80,
                enrolled_count=6,
                status="active",
            )
        ],
        timetable=[
            AdminTimetableEntryRecord(
                id=UUID("3a000000-0000-0000-0000-000000000001"),
                course_offering_id=UUID("37000000-0000-0000-0000-000000000001"),
                classroom_id=UUID("3b000000-0000-0000-0000-000000000001"),
                course_code="CS3203",
                course_name="Software Engineering Project",
                day_of_week=1,
                start_time=time(9, 0),
                end_time=time(11, 0),
                classroom_code="LH-02",
                lecturer_name="N. Perera",
                course_type="lecture",
                valid_from=date(2026, 1, 1),
                valid_until=date(2026, 6, 30),
                status="active",
            )
        ],
        enrolments=[
            AdminEnrolmentRecord(
                id=UUID("39000000-0000-0000-0000-000000000001"),
                course_offering_id=UUID("37000000-0000-0000-0000-000000000001"),
                student_id=UUID("33000000-0000-0000-0000-000000000001"),
                student_name="Amal Perera",
                registration_number="230701A",
                course_code="CS3203",
                semester_label="Semester 1 (2026)",
                enrolment_status="enrolled",
            )
        ],
    )


class StubAdminAcademicDataService:
    async def get_academic_data(self, pool):
        return build_academic_data()


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_academic_data_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document, StubAdminAcademicDataService()) as test_client:
        yield test_client


def test_returns_academic_data_with_honest_sync_status(client: TestClient, make_access_token) -> None:
    response = client.get(ACADEMIC_DATA_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["sourceConnectionStatus"] == "not_configured"
    assert body["courses"][0]["courseCode"] == "CS3203"
    assert body["timetable"][0]["lecturerName"] == "N. Perera"


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        ACADEMIC_DATA_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(ACADEMIC_DATA_URL)

    assert response.status_code == 401


class StubMutationService(StubAdminAcademicDataService):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def create_course(self, pool, actor_user_id, **values):
        self.calls.append(("course", values))
        return build_academic_data().courses[0]

    async def create_offering(self, pool, actor_user_id, **values):
        self.calls.append(("offering", values))
        return build_academic_data().offerings[0]

    async def enrol_student(self, pool, actor_user_id, offering_id, student_id):
        self.calls.append(("enrolment", {"student_id": student_id}))
        return build_academic_data().enrolments[0]

    async def create_timetable_entry(self, pool, actor_user_id, **values):
        self.calls.append(("timetable", values))
        return build_academic_data().timetable[0]


def mutation_client(jwks_document, service):
    return build_client(jwks_document, service)


def test_course_create_happy_path(jwks_document, make_access_token) -> None:
    service = StubMutationService()
    with mutation_client(jwks_document, service) as test_client:
        response = test_client.post(
            "/api/v1/administrators/me/courses",
            headers=authorize(admin_token(make_access_token)),
            json={
                "courseCode": "CS3203",
                "courseName": "Software Engineering Project",
                "departmentId": "35000000-0000-0000-0000-000000000001",
                "credits": 3,
                "status": "active",
            },
        )
    assert response.status_code == 201
    assert response.json()["courseCode"] == "CS3203"


def test_offering_create_happy_path(jwks_document, make_access_token) -> None:
    service = StubMutationService()
    with mutation_client(jwks_document, service) as test_client:
        response = test_client.post(
            "/api/v1/administrators/me/offerings",
            headers=authorize(admin_token(make_access_token)),
            json={
                "courseId": "36000000-0000-0000-0000-000000000001",
                "semesterId": "34000000-0000-0000-0000-000000000001",
                "lecturerId": "38000000-0000-0000-0000-000000000001",
                "batchYear": 2023,
                "courseType": "core",
                "attendanceThresholdPercent": 80,
                "status": "active",
            },
        )
    assert response.status_code == 201
    assert response.json()["lecturerName"] == "N. Perera"


def test_enrolment_create_happy_path(jwks_document, make_access_token) -> None:
    service = StubMutationService()
    with mutation_client(jwks_document, service) as test_client:
        response = test_client.post(
            "/api/v1/administrators/me/offerings/37000000-0000-0000-0000-000000000001/enrolments",
            headers=authorize(admin_token(make_access_token)),
            json={"studentId": "33000000-0000-0000-0000-000000000001"},
        )
    assert response.status_code == 201
    assert response.json()["enrolmentStatus"] == "enrolled"


def test_timetable_create_happy_path(jwks_document, make_access_token) -> None:
    service = StubMutationService()
    with mutation_client(jwks_document, service) as test_client:
        response = test_client.post(
            "/api/v1/administrators/me/timetable-entries",
            headers=authorize(admin_token(make_access_token)),
            json={
                "courseOfferingId": "37000000-0000-0000-0000-000000000001",
                "classroomId": "3b000000-0000-0000-0000-000000000001",
                "dayOfWeek": 1,
                "startTime": "09:00:00",
                "endTime": "11:00:00",
                "courseType": "lecture",
                "validFrom": "2026-01-01",
                "validUntil": "2026-06-30",
                "status": "active",
            },
        )
    assert response.status_code == 201
    assert response.json()["courseOfferingId"].startswith("37000000")


@pytest.mark.parametrize(
    ("method_name", "url", "payload"),
    [
        ("create_course", "/api/v1/administrators/me/courses", {
            "courseCode": "CS3203", "courseName": "Duplicate",
            "departmentId": "35000000-0000-0000-0000-000000000001",
            "credits": 3, "status": "active",
        }),
        ("create_offering", "/api/v1/administrators/me/offerings", {
            "courseId": "36000000-0000-0000-0000-000000000001",
            "semesterId": "34000000-0000-0000-0000-000000000001",
            "lecturerId": "38000000-0000-0000-0000-000000000001",
            "batchYear": 2023, "courseType": "core",
            "attendanceThresholdPercent": 80, "status": "active",
        }),
        ("create_timetable_entry", "/api/v1/administrators/me/timetable-entries", {
            "courseOfferingId": "37000000-0000-0000-0000-000000000001",
            "classroomId": "3b000000-0000-0000-0000-000000000001",
            "dayOfWeek": 1, "startTime": "09:00:00", "endTime": "11:00:00",
            "courseType": "lecture", "validFrom": "2026-01-01", "status": "active",
        }),
    ],
)
def test_duplicate_mutations_return_409(
    jwks_document, make_access_token, method_name, url, payload
) -> None:
    service = StubMutationService()

    async def conflict(*args, **kwargs):
        raise AcademicConflictError("Duplicate academic record.")

    setattr(service, method_name, conflict)
    with mutation_client(jwks_document, service) as test_client:
        response = test_client.post(
            url,
            headers=authorize(admin_token(make_access_token)),
            json=payload,
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Duplicate academic record."


def test_timetable_rejects_end_before_start(jwks_document, make_access_token) -> None:
    with mutation_client(jwks_document, StubMutationService()) as test_client:
        response = test_client.post(
            "/api/v1/administrators/me/timetable-entries",
            headers=authorize(admin_token(make_access_token)),
            json={
                "courseOfferingId": "37000000-0000-0000-0000-000000000001",
                "classroomId": "3b000000-0000-0000-0000-000000000001",
                "dayOfWeek": 1,
                "startTime": "11:00:00",
                "endTime": "09:00:00",
                "courseType": "lecture",
                "validFrom": "2026-01-01",
                "status": "active",
            },
        )
    assert response.status_code == 422


def test_mutation_rejects_non_administrator(jwks_document, make_access_token) -> None:
    with mutation_client(jwks_document, StubMutationService()) as test_client:
        response = test_client.post(
            "/api/v1/administrators/me/courses",
            headers=authorize(
                make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))
            ),
            json={
                "courseCode": "CS3203",
                "courseName": "Software Engineering Project",
                "departmentId": "35000000-0000-0000-0000-000000000001",
                "credits": 3,
                "status": "active",
            },
        )
    assert response.status_code == 403
