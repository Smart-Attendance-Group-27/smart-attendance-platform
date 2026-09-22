from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import date, time
from decimal import Decimal
from typing import AsyncIterator
from uuid import UUID, uuid4

import asyncpg

from modules.academic.admin_academic_data.exception import (
    AcademicConflictError,
    AcademicEntityNotFoundError,
)
from modules.academic.admin_academic_data.repository import (
    AcademicOptionRecord,
    AdminAcademicDataRepository,
    AdminCourseOfferingRecord,
    AdminCourseRecord,
    AdminEnrolmentRecord,
    AdminTimetableEntryRecord,
)
from modules.audit.repository import write_audit_log

SOURCE_CONNECTION_STATUS = "not_configured"
ACTOR_TYPE = "administrator"


@dataclass(frozen=True)
class AcademicData:
    source_connection_status: str
    courses: list[AdminCourseRecord]
    offerings: list[AdminCourseOfferingRecord]
    timetable: list[AdminTimetableEntryRecord]
    enrolments: list[AdminEnrolmentRecord]


class AdminAcademicDataService:
    def __init__(self, repository: AdminAcademicDataRepository | None = None) -> None:
        self._repository = repository or AdminAcademicDataRepository()

    async def get_academic_data(self, pool: asyncpg.Pool) -> AcademicData:
        async with pool.acquire() as connection:
            return AcademicData(
                source_connection_status=SOURCE_CONNECTION_STATUS,
                courses=await self._repository.list_courses(connection),
                offerings=await self._repository.list_course_offerings(connection),
                timetable=await self._repository.list_timetable(connection),
                enrolments=await self._repository.list_enrolments(connection),
            )

    async def get_reference_options(
        self, pool: asyncpg.Pool
    ) -> dict[str, list[AcademicOptionRecord]]:
        async with pool.acquire() as connection:
            return await self._repository.list_reference_options(connection)

    async def create_course(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        *,
        course_code: str,
        course_name: str,
        department_id: UUID,
        credits: Decimal,
        status: str,
    ) -> AdminCourseRecord:
        course_id = uuid4()
        async with self._transaction(pool) as connection:
            await self._require_reference(connection, "departments", department_id, "department")
            if await self._repository.course_code_exists(connection, course_code):
                raise AcademicConflictError("A course with this code already exists.")
            await self._repository.create_course(
                connection,
                course_id=course_id,
                course_code=course_code.upper(),
                course_name=course_name,
                department_id=department_id,
                credits=credits,
                status=status,
            )
            created = await self._repository.find_course(connection, course_id)
            assert created is not None
            await self._audit(connection, actor_user_id, "course.create", "course", course_id, None, created)
        return created

    async def update_course(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        course_id: UUID,
        *,
        course_code: str,
        course_name: str,
        department_id: UUID,
        credits: Decimal,
        status: str,
    ) -> AdminCourseRecord:
        async with self._transaction(pool) as connection:
            before = await self._repository.find_course(connection, course_id, lock=True)
            if before is None:
                raise AcademicEntityNotFoundError("course")
            await self._require_reference(connection, "departments", department_id, "department")
            if await self._repository.course_code_exists(connection, course_code, course_id):
                raise AcademicConflictError("A course with this code already exists.")
            await self._repository.update_course(
                connection,
                course_id,
                course_code=course_code.upper(),
                course_name=course_name,
                department_id=department_id,
                credits=credits,
                status=status,
            )
            after = await self._repository.find_course(connection, course_id)
            assert after is not None
            await self._audit(connection, actor_user_id, "course.update", "course", course_id, before, after)
        return after

    async def create_offering(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        *,
        course_id: UUID,
        semester_id: UUID,
        lecturer_id: UUID,
        batch_year: int,
        course_type: str,
        attendance_threshold: Decimal,
        status: str,
    ) -> AdminCourseOfferingRecord:
        offering_id = uuid4()
        async with self._transaction(pool) as connection:
            await self._validate_offering_references(connection, course_id, semester_id, lecturer_id)
            if await self._repository.offering_natural_key_exists(
                connection,
                course_id=course_id,
                semester_id=semester_id,
                batch_year=batch_year,
                course_type=course_type,
            ):
                raise AcademicConflictError("This course offering already exists.")
            await self._repository.create_offering(
                connection,
                offering_id=offering_id,
                course_id=course_id,
                semester_id=semester_id,
                batch_year=batch_year,
                course_type=course_type,
                attendance_threshold=attendance_threshold,
                status=status,
            )
            await self._repository.set_offering_lecturer(connection, offering_id, lecturer_id)
            created = await self._repository.find_offering(connection, offering_id)
            assert created is not None
            await self._audit(connection, actor_user_id, "course_offering.create", "course_offering", offering_id, None, created)
        return created

    async def update_offering(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        offering_id: UUID,
        *,
        course_id: UUID,
        semester_id: UUID,
        lecturer_id: UUID,
        batch_year: int,
        course_type: str,
        attendance_threshold: Decimal,
        status: str,
    ) -> AdminCourseOfferingRecord:
        async with self._transaction(pool) as connection:
            before = await self._repository.find_offering(connection, offering_id, lock=True)
            if before is None:
                raise AcademicEntityNotFoundError("course offering")
            await self._validate_offering_references(connection, course_id, semester_id, lecturer_id)
            if await self._repository.offering_natural_key_exists(
                connection,
                course_id=course_id,
                semester_id=semester_id,
                batch_year=batch_year,
                course_type=course_type,
                exclude_id=offering_id,
            ):
                raise AcademicConflictError("This course offering already exists.")
            await self._repository.update_offering(
                connection,
                offering_id,
                course_id=course_id,
                semester_id=semester_id,
                batch_year=batch_year,
                course_type=course_type,
                attendance_threshold=attendance_threshold,
                status=status,
            )
            await self._repository.set_offering_lecturer(connection, offering_id, lecturer_id)
            after = await self._repository.find_offering(connection, offering_id)
            assert after is not None
            await self._audit(connection, actor_user_id, "course_offering.update", "course_offering", offering_id, before, after)
        return after

    async def assign_lecturer(
        self, pool: asyncpg.Pool, actor_user_id: UUID, offering_id: UUID, lecturer_id: UUID
    ) -> AdminCourseOfferingRecord:
        async with self._transaction(pool) as connection:
            before = await self._repository.find_offering(connection, offering_id, lock=True)
            if before is None:
                raise AcademicEntityNotFoundError("course offering")
            await self._require_reference(connection, "lecturer_profiles", lecturer_id, "lecturer")
            await self._repository.set_offering_lecturer(connection, offering_id, lecturer_id)
            after = await self._repository.find_offering(connection, offering_id)
            assert after is not None
            await self._audit(connection, actor_user_id, "course_offering.assign_lecturer", "course_offering", offering_id, before, after)
        return after

    async def list_offering_enrolments(
        self, pool: asyncpg.Pool, offering_id: UUID
    ) -> list[AdminEnrolmentRecord]:
        async with pool.acquire() as connection:
            await self._require_reference(connection, "course_offerings", offering_id, "course offering")
            return await self._repository.list_enrolments(connection, offering_id)

    async def enrol_student(
        self, pool: asyncpg.Pool, actor_user_id: UUID, offering_id: UUID, student_id: UUID
    ) -> AdminEnrolmentRecord:
        async with self._transaction(pool) as connection:
            await self._require_reference(connection, "course_offerings", offering_id, "course offering")
            await self._require_reference(connection, "student_profiles", student_id, "student")
            before = await self._repository.find_enrolment(connection, offering_id, student_id, lock=True)
            if before is not None and before.enrolment_status == "enrolled":
                raise AcademicConflictError("The student is already enrolled in this offering.")
            await self._repository.enrol_student(
                connection,
                enrolment_id=before.id if before else uuid4(),
                offering_id=offering_id,
                student_id=student_id,
            )
            after = await self._repository.find_enrolment(connection, offering_id, student_id)
            assert after is not None
            await self._audit(connection, actor_user_id, "course_enrolment.enrol", "course_enrolment", after.id, before, after)
        return after

    async def drop_student(
        self, pool: asyncpg.Pool, actor_user_id: UUID, offering_id: UUID, student_id: UUID
    ) -> AdminEnrolmentRecord:
        async with self._transaction(pool) as connection:
            before = await self._repository.find_enrolment(connection, offering_id, student_id, lock=True)
            if before is None:
                raise AcademicEntityNotFoundError("enrolment")
            await self._repository.drop_enrolment(connection, offering_id, student_id)
            after = await self._repository.find_enrolment(connection, offering_id, student_id)
            assert after is not None
            await self._audit(connection, actor_user_id, "course_enrolment.drop", "course_enrolment", after.id, before, after)
        return after

    async def create_timetable_entry(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        **values,
    ) -> AdminTimetableEntryRecord:
        entry_id = uuid4()
        async with self._transaction(pool) as connection:
            await self._validate_timetable_references(connection, values["offering_id"], values["classroom_id"])
            await self._ensure_timetable_key_available(connection, values)
            await self._repository.create_timetable_entry(
                connection, entry_id=entry_id, created_by=actor_user_id, **values
            )
            created = await self._repository.find_timetable_entry(connection, entry_id)
            assert created is not None
            await self._audit(connection, actor_user_id, "timetable_entry.create", "timetable_entry", entry_id, None, created)
        return created

    async def update_timetable_entry(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        entry_id: UUID,
        **values,
    ) -> AdminTimetableEntryRecord:
        async with self._transaction(pool) as connection:
            before = await self._repository.find_timetable_entry(connection, entry_id, lock=True)
            if before is None:
                raise AcademicEntityNotFoundError("timetable entry")
            await self._validate_timetable_references(connection, values["offering_id"], values["classroom_id"])
            await self._ensure_timetable_key_available(connection, values, entry_id)
            await self._repository.update_timetable_entry(connection, entry_id, **values)
            after = await self._repository.find_timetable_entry(connection, entry_id)
            assert after is not None
            await self._audit(connection, actor_user_id, "timetable_entry.update", "timetable_entry", entry_id, before, after)
        return after

    async def deactivate_timetable_entry(
        self, pool: asyncpg.Pool, actor_user_id: UUID, entry_id: UUID
    ) -> AdminTimetableEntryRecord:
        async with self._transaction(pool) as connection:
            before = await self._repository.find_timetable_entry(connection, entry_id, lock=True)
            if before is None:
                raise AcademicEntityNotFoundError("timetable entry")
            await self._repository.deactivate_timetable_entry(connection, entry_id)
            after = await self._repository.find_timetable_entry(connection, entry_id)
            assert after is not None
            await self._audit(connection, actor_user_id, "timetable_entry.deactivate", "timetable_entry", entry_id, before, after)
        return after

    @asynccontextmanager
    async def _transaction(self, pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
        try:
            async with pool.acquire() as connection, connection.transaction():
                yield connection
        except asyncpg.UniqueViolationError as error:
            raise AcademicConflictError("An academic record with these values already exists.") from error

    async def _require_reference(
        self, connection: asyncpg.Connection, table: str, entity_id: UUID, label: str
    ) -> None:
        if not await self._repository.reference_exists(connection, table, entity_id):
            raise AcademicEntityNotFoundError(label)

    async def _validate_offering_references(
        self, connection: asyncpg.Connection, course_id: UUID, semester_id: UUID, lecturer_id: UUID
    ) -> None:
        await self._require_reference(connection, "courses", course_id, "course")
        await self._require_reference(connection, "semesters", semester_id, "semester")
        await self._require_reference(connection, "lecturer_profiles", lecturer_id, "lecturer")

    async def _validate_timetable_references(
        self, connection: asyncpg.Connection, offering_id: UUID, classroom_id: UUID
    ) -> None:
        await self._require_reference(connection, "course_offerings", offering_id, "course offering")
        await self._require_reference(connection, "classrooms", classroom_id, "classroom")

    async def _ensure_timetable_key_available(
        self, connection: asyncpg.Connection, values: dict, exclude_id: UUID | None = None
    ) -> None:
        if await self._repository.timetable_key_exists(
            connection,
            offering_id=values["offering_id"],
            day_of_week=values["day_of_week"],
            start_time=values["start_time"],
            valid_from=values["valid_from"],
            exclude_id=exclude_id,
        ):
            raise AcademicConflictError("This timetable slot already exists.")

    async def _audit(
        self,
        connection: asyncpg.Connection,
        actor_user_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        before,
        after,
    ) -> None:
        await write_audit_log(
            connection,
            actor_user_id=actor_user_id,
            actor_type=ACTOR_TYPE,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=_snapshot(before),
            new_values=_snapshot(after),
        )


def _snapshot(record) -> dict | None:
    if record is None:
        return None
    values = asdict(record)
    return {
        key: (
            str(value)
            if isinstance(value, (UUID, Decimal, date, time))
            else value
        )
        for key, value in values.items()
    }
