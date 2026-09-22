from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class AdminCourseRecord:
    id: UUID
    course_code: str | None
    course_name: str | None
    department_id: UUID | None
    department_name: str | None
    credits: Decimal | None
    status: str | None


@dataclass(frozen=True)
class AdminCourseOfferingRecord:
    id: UUID
    course_id: UUID
    semester_id: UUID
    lecturer_id: UUID | None
    lecturer_name: str | None
    course_code: str | None
    course_name: str | None
    semester_label: str
    batch_year: int | None
    course_type: str | None
    attendance_threshold_percent: Decimal | None
    enrolled_count: int
    status: str | None


@dataclass(frozen=True)
class AdminTimetableEntryRecord:
    id: UUID
    course_offering_id: UUID
    classroom_id: UUID | None
    course_code: str | None
    course_name: str | None
    day_of_week: int
    start_time: time
    end_time: time
    classroom_code: str | None
    lecturer_name: str | None
    course_type: str | None
    valid_from: date
    valid_until: date | None
    status: str | None


@dataclass(frozen=True)
class AdminEnrolmentRecord:
    id: UUID
    course_offering_id: UUID
    student_id: UUID
    student_name: str
    registration_number: str | None
    course_code: str | None
    semester_label: str
    enrolment_status: str | None


@dataclass(frozen=True)
class AcademicOptionRecord:
    id: UUID
    label: str


_SEMESTER_LABEL_EXPR = """
    'Semester ' || semester.semester_number || ' (' ||
    EXTRACT(YEAR FROM academic_year.start_date) || ')'
"""

_OFFERING_SELECT = f"""
    SELECT offering.id, offering.course_id, offering.semester_id,
        course.course_code, course.course_name,
        {_SEMESTER_LABEL_EXPR} AS semester_label,
        offering.batch_year, offering.course_type, offering.attendance_threshold,
        offering.status, lecturer.id AS lecturer_id,
        CASE WHEN lecturer.id IS NULL THEN NULL ELSE
            TRIM(CONCAT_WS(' ', lecturer.first_name, NULLIF(lecturer.middle_name, ''), lecturer.last_name))
        END AS lecturer_name,
        (SELECT COUNT(*) FROM academic.course_enrolments AS enrolment
         WHERE enrolment.course_offering_id = offering.id
           AND enrolment.enrolment_status = 'enrolled') AS enrolled_count
    FROM academic.course_offerings AS offering
    JOIN academic.courses AS course ON course.id = offering.course_id
    JOIN academic.semesters AS semester ON semester.id = offering.semester_id
    JOIN academic.academic_years AS academic_year ON academic_year.id = semester.academic_year_id
    LEFT JOIN LATERAL (
        SELECT lp.* FROM academic.course_lecturers AS assignment
        JOIN academic.lecturer_profiles AS lp ON lp.id = assignment.lecturer_id
        WHERE assignment.course_offering_id = offering.id
        ORDER BY assignment.assigned_at ASC NULLS LAST LIMIT 1
    ) AS lecturer ON TRUE
"""

_TIMETABLE_SELECT = """
    SELECT entry.id, entry.course_offering_id, entry.classroom_id,
        course.course_code, course.course_name, entry.day_of_week,
        entry.start_time, entry.end_time, classroom.classroom_code,
        lecturers.lecturer_name, entry.course_type, entry.valid_from,
        entry.valid_until, entry.status
    FROM academic.timetable_entries AS entry
    JOIN academic.course_offerings AS offering ON offering.id = entry.course_offering_id
    JOIN academic.courses AS course ON course.id = offering.course_id
    LEFT JOIN academic.classrooms AS classroom ON classroom.id = entry.classroom_id
    LEFT JOIN LATERAL (
        SELECT STRING_AGG(
            TRIM(CONCAT_WS(' ', lp.first_name, NULLIF(lp.middle_name, ''), lp.last_name)), ', '
        ) AS lecturer_name
        FROM academic.course_lecturers AS assignment
        JOIN academic.lecturer_profiles AS lp ON lp.id = assignment.lecturer_id
        WHERE assignment.course_offering_id = offering.id
    ) AS lecturers ON TRUE
"""

_ENROLMENT_SELECT = f"""
    SELECT enrolment.id, enrolment.course_offering_id, enrolment.student_id,
        TRIM(CONCAT_WS(' ', student.first_name, NULLIF(student.middle_name, ''), student.last_name))
            AS student_name,
        student.registration_number, course.course_code,
        {_SEMESTER_LABEL_EXPR} AS semester_label, enrolment.enrolment_status
    FROM academic.course_enrolments AS enrolment
    JOIN academic.student_profiles AS student ON student.id = enrolment.student_id
    JOIN academic.course_offerings AS offering ON offering.id = enrolment.course_offering_id
    JOIN academic.courses AS course ON course.id = offering.course_id
    JOIN academic.semesters AS semester ON semester.id = offering.semester_id
    JOIN academic.academic_years AS academic_year ON academic_year.id = semester.academic_year_id
"""


def _course(row: asyncpg.Record) -> AdminCourseRecord:
    return AdminCourseRecord(
        id=row["id"], course_code=row["course_code"], course_name=row["course_name"],
        department_id=row["department_id"], department_name=row["department_name"],
        credits=row["credits"], status=row["status"],
    )


def _offering(row: asyncpg.Record) -> AdminCourseOfferingRecord:
    return AdminCourseOfferingRecord(
        id=row["id"], course_id=row["course_id"], semester_id=row["semester_id"],
        lecturer_id=row["lecturer_id"], lecturer_name=row["lecturer_name"],
        course_code=row["course_code"], course_name=row["course_name"],
        semester_label=row["semester_label"], batch_year=row["batch_year"],
        course_type=row["course_type"], attendance_threshold_percent=row["attendance_threshold"],
        enrolled_count=row["enrolled_count"], status=row["status"],
    )


def _timetable(row: asyncpg.Record) -> AdminTimetableEntryRecord:
    return AdminTimetableEntryRecord(
        id=row["id"], course_offering_id=row["course_offering_id"],
        classroom_id=row["classroom_id"], course_code=row["course_code"],
        course_name=row["course_name"], day_of_week=row["day_of_week"],
        start_time=row["start_time"], end_time=row["end_time"],
        classroom_code=row["classroom_code"], lecturer_name=row["lecturer_name"],
        course_type=row["course_type"], valid_from=row["valid_from"],
        valid_until=row["valid_until"], status=row["status"],
    )


def _enrolment(row: asyncpg.Record) -> AdminEnrolmentRecord:
    return AdminEnrolmentRecord(
        id=row["id"], course_offering_id=row["course_offering_id"],
        student_id=row["student_id"], student_name=row["student_name"] or "",
        registration_number=row["registration_number"], course_code=row["course_code"],
        semester_label=row["semester_label"], enrolment_status=row["enrolment_status"],
    )


class AdminAcademicDataRepository:
    async def list_courses(self, connection: asyncpg.Connection) -> list[AdminCourseRecord]:
        rows = await connection.fetch("""
            SELECT course.id, course.course_code, course.course_name, course.department_id,
                   department.department_name, course.credits, course.status
            FROM academic.courses AS course
            LEFT JOIN academic.departments AS department ON department.id = course.department_id
            ORDER BY course.course_code ASC
        """)
        return [_course(row) for row in rows]

    async def find_course(self, connection: asyncpg.Connection, course_id: UUID, *, lock: bool = False) -> AdminCourseRecord | None:
        row = await connection.fetchrow(f"""
            SELECT course.id, course.course_code, course.course_name, course.department_id,
                   department.department_name, course.credits, course.status
            FROM academic.courses AS course
            LEFT JOIN academic.departments AS department ON department.id = course.department_id
            WHERE course.id = $1 {'FOR UPDATE OF course' if lock else ''}
        """, course_id)
        return _course(row) if row else None

    async def course_code_exists(self, connection: asyncpg.Connection, code: str, exclude_id: UUID | None = None) -> bool:
        return bool(await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM academic.courses WHERE upper(course_code)=upper($1) AND ($2::uuid IS NULL OR id<>$2))",
            code, exclude_id,
        ))

    async def create_course(self, connection: asyncpg.Connection, *, course_id: UUID, course_code: str, course_name: str, department_id: UUID, credits: Decimal, status: str) -> None:
        await connection.execute("""
            INSERT INTO academic.courses
                (id, course_code, course_name, department_id, credits, status, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,now(),now())
        """, course_id, course_code, course_name, department_id, credits, status)

    async def update_course(self, connection: asyncpg.Connection, course_id: UUID, *, course_code: str, course_name: str, department_id: UUID, credits: Decimal, status: str) -> bool:
        result = await connection.execute("""
            UPDATE academic.courses SET course_code=$2, course_name=$3, department_id=$4,
                credits=$5, status=$6, updated_at=now() WHERE id=$1
        """, course_id, course_code, course_name, department_id, credits, status)
        return result == "UPDATE 1"

    async def list_course_offerings(self, connection: asyncpg.Connection) -> list[AdminCourseOfferingRecord]:
        rows = await connection.fetch(f"{_OFFERING_SELECT} ORDER BY academic_year.start_date DESC, course.course_code ASC")
        return [_offering(row) for row in rows]

    async def find_offering(self, connection: asyncpg.Connection, offering_id: UUID, *, lock: bool = False) -> AdminCourseOfferingRecord | None:
        row = await connection.fetchrow(f"{_OFFERING_SELECT} WHERE offering.id=$1 {'FOR UPDATE OF offering' if lock else ''}", offering_id)
        return _offering(row) if row else None

    async def offering_natural_key_exists(self, connection: asyncpg.Connection, *, course_id: UUID, semester_id: UUID, batch_year: int, course_type: str, exclude_id: UUID | None = None) -> bool:
        return bool(await connection.fetchval("""
            SELECT EXISTS(SELECT 1 FROM academic.course_offerings
            WHERE course_id=$1 AND semester_id=$2 AND batch_year=$3 AND course_type=$4
              AND ($5::uuid IS NULL OR id<>$5))
        """, course_id, semester_id, batch_year, course_type, exclude_id))

    async def create_offering(self, connection: asyncpg.Connection, *, offering_id: UUID, course_id: UUID, semester_id: UUID, batch_year: int, course_type: str, attendance_threshold: Decimal, status: str) -> None:
        await connection.execute("""
            INSERT INTO academic.course_offerings
                (id, course_id, semester_id, batch_year, course_type, attendance_threshold, status, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,now(),now())
        """, offering_id, course_id, semester_id, batch_year, course_type, attendance_threshold, status)

    async def update_offering(self, connection: asyncpg.Connection, offering_id: UUID, *, course_id: UUID, semester_id: UUID, batch_year: int, course_type: str, attendance_threshold: Decimal, status: str) -> bool:
        result = await connection.execute("""
            UPDATE academic.course_offerings SET course_id=$2, semester_id=$3, batch_year=$4,
                course_type=$5, attendance_threshold=$6, status=$7, updated_at=now() WHERE id=$1
        """, offering_id, course_id, semester_id, batch_year, course_type, attendance_threshold, status)
        return result == "UPDATE 1"

    async def set_offering_lecturer(self, connection: asyncpg.Connection, offering_id: UUID, lecturer_id: UUID) -> None:
        await connection.execute("DELETE FROM academic.course_lecturers WHERE course_offering_id=$1", offering_id)
        await connection.execute("""
            INSERT INTO academic.course_lecturers
                (id, course_offering_id, lecturer_id, lecturer_role, assigned_at)
            VALUES (gen_random_uuid(),$1,$2,'primary',now())
        """, offering_id, lecturer_id)

    async def list_enrolments(self, connection: asyncpg.Connection, offering_id: UUID | None = None) -> list[AdminEnrolmentRecord]:
        rows = await connection.fetch(
            f"{_ENROLMENT_SELECT} WHERE ($1::uuid IS NULL OR enrolment.course_offering_id=$1) ORDER BY enrolment.enrolled_at DESC NULLS LAST",
            offering_id,
        )
        return [_enrolment(row) for row in rows]

    async def find_enrolment(self, connection: asyncpg.Connection, offering_id: UUID, student_id: UUID, *, lock: bool = False) -> AdminEnrolmentRecord | None:
        row = await connection.fetchrow(
            f"{_ENROLMENT_SELECT} WHERE enrolment.course_offering_id=$1 AND enrolment.student_id=$2 {'FOR UPDATE OF enrolment' if lock else ''}",
            offering_id, student_id,
        )
        return _enrolment(row) if row else None

    async def enrol_student(self, connection: asyncpg.Connection, *, enrolment_id: UUID, offering_id: UUID, student_id: UUID) -> None:
        await connection.execute("""
            INSERT INTO academic.course_enrolments
                (id, course_offering_id, student_id, enrolment_status, enrolled_at, created_at, updated_at)
            VALUES ($1,$2,$3,'enrolled',now(),now(),now())
            ON CONFLICT (course_offering_id, student_id) DO UPDATE
            SET enrolment_status='enrolled', enrolled_at=now(), dropped_at=NULL, updated_at=now()
        """, enrolment_id, offering_id, student_id)

    async def drop_enrolment(self, connection: asyncpg.Connection, offering_id: UUID, student_id: UUID) -> bool:
        result = await connection.execute("""
            UPDATE academic.course_enrolments SET enrolment_status='dropped',
                dropped_at=now(), updated_at=now()
            WHERE course_offering_id=$1 AND student_id=$2
        """, offering_id, student_id)
        return result == "UPDATE 1"

    async def list_timetable(self, connection: asyncpg.Connection) -> list[AdminTimetableEntryRecord]:
        rows = await connection.fetch(f"{_TIMETABLE_SELECT} WHERE entry.status='active' ORDER BY entry.day_of_week, entry.start_time")
        return [_timetable(row) for row in rows]

    async def find_timetable_entry(self, connection: asyncpg.Connection, entry_id: UUID, *, lock: bool = False) -> AdminTimetableEntryRecord | None:
        row = await connection.fetchrow(f"{_TIMETABLE_SELECT} WHERE entry.id=$1 {'FOR UPDATE OF entry' if lock else ''}", entry_id)
        return _timetable(row) if row else None

    async def timetable_key_exists(self, connection: asyncpg.Connection, *, offering_id: UUID, day_of_week: int, start_time: time, valid_from: date, exclude_id: UUID | None = None) -> bool:
        return bool(await connection.fetchval("""
            SELECT EXISTS(SELECT 1 FROM academic.timetable_entries
            WHERE course_offering_id=$1 AND day_of_week=$2 AND start_time=$3 AND valid_from=$4
              AND ($5::uuid IS NULL OR id<>$5))
        """, offering_id, day_of_week, start_time, valid_from, exclude_id))

    async def create_timetable_entry(self, connection: asyncpg.Connection, *, entry_id: UUID, offering_id: UUID, classroom_id: UUID, day_of_week: int, start_time: time, end_time: time, course_type: str, valid_from: date, valid_until: date | None, status: str, created_by: UUID) -> None:
        await connection.execute("""
            INSERT INTO academic.timetable_entries
                (id, course_offering_id, classroom_id, day_of_week, start_time, end_time,
                 course_type, valid_from, valid_until, status, created_by, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,now(),now())
        """, entry_id, offering_id, classroom_id, day_of_week, start_time, end_time, course_type, valid_from, valid_until, status, created_by)

    async def update_timetable_entry(self, connection: asyncpg.Connection, entry_id: UUID, *, offering_id: UUID, classroom_id: UUID, day_of_week: int, start_time: time, end_time: time, course_type: str, valid_from: date, valid_until: date | None, status: str) -> bool:
        result = await connection.execute("""
            UPDATE academic.timetable_entries SET course_offering_id=$2, classroom_id=$3,
                day_of_week=$4, start_time=$5, end_time=$6, course_type=$7,
                valid_from=$8, valid_until=$9, status=$10, updated_at=now() WHERE id=$1
        """, entry_id, offering_id, classroom_id, day_of_week, start_time, end_time, course_type, valid_from, valid_until, status)
        return result == "UPDATE 1"

    async def deactivate_timetable_entry(self, connection: asyncpg.Connection, entry_id: UUID) -> bool:
        result = await connection.execute("UPDATE academic.timetable_entries SET status='inactive', updated_at=now() WHERE id=$1", entry_id)
        return result == "UPDATE 1"

    async def reference_exists(self, connection: asyncpg.Connection, table: str, entity_id: UUID) -> bool:
        allowed = {"departments", "courses", "semesters", "lecturer_profiles", "student_profiles", "classrooms", "course_offerings"}
        if table not in allowed:
            raise ValueError("Unsupported academic reference table")
        return bool(await connection.fetchval(f"SELECT EXISTS(SELECT 1 FROM academic.{table} WHERE id=$1)", entity_id))

    async def list_reference_options(self, connection: asyncpg.Connection) -> dict[str, list[AcademicOptionRecord]]:
        queries = {
            "departments": "SELECT id, department_name AS label FROM academic.departments WHERE status='active' ORDER BY label",
            "semesters": f"SELECT semester.id, {_SEMESTER_LABEL_EXPR} AS label FROM academic.semesters semester JOIN academic.academic_years academic_year ON academic_year.id=semester.academic_year_id WHERE semester.status='active' ORDER BY academic_year.start_date DESC, semester.semester_number",
            "lecturers": "SELECT id, TRIM(CONCAT_WS(' ', first_name, NULLIF(middle_name,''), last_name)) AS label FROM academic.lecturer_profiles WHERE status='active' ORDER BY label",
            "students": "SELECT id, registration_number || ' - ' || TRIM(CONCAT_WS(' ', first_name, NULLIF(middle_name,''), last_name)) AS label FROM academic.student_profiles WHERE status='active' ORDER BY registration_number",
            "classrooms": "SELECT id, classroom_code AS label FROM academic.classrooms WHERE status='active' ORDER BY classroom_code",
        }
        result: dict[str, list[AcademicOptionRecord]] = {}
        for key, query in queries.items():
            rows = await connection.fetch(query)
            result[key] = [AcademicOptionRecord(id=row["id"], label=row["label"] or "") for row in rows]
        return result
