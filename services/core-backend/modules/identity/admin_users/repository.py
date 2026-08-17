from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class StudentAccountRecord:
    user_id: UUID
    registration_number: str | None
    full_name: str
    email: str | None
    department_name: str | None
    intake_year: int | None
    current_semester: int | None
    account_status: str | None
    profile_status: str | None


@dataclass(frozen=True)
class LecturerAccountRecord:
    user_id: UUID
    employee_number: str | None
    full_name: str
    email: str | None
    department_name: str | None
    designation: str | None
    account_status: str | None
    profile_status: str | None


@dataclass(frozen=True)
class AdministratorAccountRecord:
    user_id: UUID
    full_name: str
    email: str | None
    department_name: str | None
    administrative_scope: str | None
    account_status: str | None
    profile_status: str | None


@dataclass(frozen=True)
class UserAccountRecord:
    id: UUID
    account_status: str | None
    locked_until: datetime | None


_FULL_NAME_EXPR = """
    TRIM(CONCAT_WS(' ', profile.first_name, NULLIF(profile.middle_name, ''), profile.last_name))
"""


class AdminUserRepository:
    async def list_students(self, connection: asyncpg.Connection) -> list[StudentAccountRecord]:
        rows = await connection.fetch(
            f"""
            SELECT
                app_user.id AS user_id,
                profile.registration_number,
                {_FULL_NAME_EXPR} AS full_name,
                app_user.email,
                department.department_name,
                profile.intake_year,
                profile.current_semester,
                app_user.account_status,
                profile.profile_status
            FROM academic.student_profiles AS profile
            JOIN identity.users AS app_user
                ON app_user.id = profile.user_id
            LEFT JOIN academic.departments AS department
                ON department.id = profile.department_id
            ORDER BY profile.registration_number ASC
            """,
        )
        return [
            StudentAccountRecord(
                user_id=row["user_id"],
                registration_number=row["registration_number"],
                full_name=row["full_name"] or "",
                email=row["email"],
                department_name=row["department_name"],
                intake_year=row["intake_year"],
                current_semester=row["current_semester"],
                account_status=row["account_status"],
                profile_status=row["profile_status"],
            )
            for row in rows
        ]

    async def list_lecturers(self, connection: asyncpg.Connection) -> list[LecturerAccountRecord]:
        rows = await connection.fetch(
            f"""
            SELECT
                app_user.id AS user_id,
                profile.employee_number,
                {_FULL_NAME_EXPR} AS full_name,
                app_user.email,
                department.department_name,
                profile.designation,
                app_user.account_status,
                profile.profile_status
            FROM academic.lecturer_profiles AS profile
            JOIN identity.users AS app_user
                ON app_user.id = profile.user_id
            LEFT JOIN academic.departments AS department
                ON department.id = profile.department_id
            ORDER BY profile.employee_number ASC
            """,
        )
        return [
            LecturerAccountRecord(
                user_id=row["user_id"],
                employee_number=row["employee_number"],
                full_name=row["full_name"] or "",
                email=row["email"],
                department_name=row["department_name"],
                designation=row["designation"],
                account_status=row["account_status"],
                profile_status=row["profile_status"],
            )
            for row in rows
        ]

    async def list_administrators(
        self,
        connection: asyncpg.Connection,
    ) -> list[AdministratorAccountRecord]:
        rows = await connection.fetch(
            f"""
            SELECT
                app_user.id AS user_id,
                {_FULL_NAME_EXPR} AS full_name,
                app_user.email,
                department.department_name,
                profile.administrative_scope,
                app_user.account_status,
                profile.profile_status
            FROM academic.administrator_profiles AS profile
            JOIN identity.users AS app_user
                ON app_user.id = profile.user_id
            LEFT JOIN academic.departments AS department
                ON department.id = profile.department_id
            ORDER BY full_name ASC
            """,
        )
        return [
            AdministratorAccountRecord(
                user_id=row["user_id"],
                full_name=row["full_name"] or "",
                email=row["email"],
                department_name=row["department_name"],
                administrative_scope=row["administrative_scope"],
                account_status=row["account_status"],
                profile_status=row["profile_status"],
            )
            for row in rows
        ]

    async def find_user_account(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
        *,
        lock_for_update: bool = False,
    ) -> UserAccountRecord | None:
        lock_clause = "FOR UPDATE" if lock_for_update else ""
        row = await connection.fetchrow(
            f"""
            SELECT id, account_status, locked_until
            FROM identity.users
            WHERE id = $1
            {lock_clause}
            """,
            user_id,
        )
        if row is None:
            return None
        return UserAccountRecord(
            id=row["id"],
            account_status=row["account_status"],
            locked_until=row["locked_until"],
        )

    async def update_account_status(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
        account_status: str,
    ) -> None:
        await connection.execute(
            """
            UPDATE identity.users
            SET account_status = $2, updated_at = now()
            WHERE id = $1
            """,
            user_id,
            account_status,
        )
