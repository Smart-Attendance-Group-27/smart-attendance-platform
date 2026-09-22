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


@dataclass(frozen=True)
class DepartmentOptionRecord:
    id: UUID
    label: str


_FULL_NAME_EXPR = """
    TRIM(CONCAT_WS(' ', profile.first_name, NULLIF(profile.middle_name, ''), profile.last_name))
"""


class AdminUserRepository:
    async def list_active_departments(
        self,
        connection: asyncpg.Connection,
    ) -> list[DepartmentOptionRecord]:
        rows = await connection.fetch(
            """
            SELECT id, department_name AS label
            FROM academic.departments
            WHERE status = 'active'
            ORDER BY department_name
            """,
        )
        return [DepartmentOptionRecord(id=row["id"], label=row["label"] or "") for row in rows]

    async def email_exists(self, connection: asyncpg.Connection, email: str) -> bool:
        return bool(
            await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM identity.users WHERE lower(email)=lower($1))",
                email,
            ),
        )

    async def registration_number_exists(
        self,
        connection: asyncpg.Connection,
        registration_number: str,
    ) -> bool:
        return bool(
            await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM academic.student_profiles WHERE registration_number=$1)",
                registration_number,
            ),
        )

    async def employee_number_exists(
        self,
        connection: asyncpg.Connection,
        employee_number: str,
    ) -> bool:
        return bool(
            await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM academic.lecturer_profiles WHERE employee_number=$1)",
                employee_number,
            ),
        )

    async def create_user(
        self,
        connection: asyncpg.Connection,
        *,
        user_id: UUID,
        email: str,
        keycloak_user_id: str,
        created_by: UUID,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO identity.users (
                id, email, password_hash, account_status, failed_login_attempts,
                must_change_password, created_by, created_at, updated_at, keycloak_user_id
            ) VALUES ($1, $2, NULL, 'active', 0, TRUE, $3, now(), now(), $4)
            """,
            user_id,
            email,
            created_by,
            keycloak_user_id,
        )

    async def create_student_profile(
        self,
        connection: asyncpg.Connection,
        *,
        profile_id: UUID,
        user_id: UUID,
        registration_number: str,
        first_name: str,
        middle_name: str | None,
        last_name: str,
        department_id: UUID,
        intake_year: int,
        current_semester: int,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO academic.student_profiles (
                id, user_id, registration_number, first_name, middle_name, last_name,
                department_id, intake_year, current_semester, profile_status, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'active',now(),now())
            """,
            profile_id, user_id, registration_number, first_name, middle_name, last_name,
            department_id, intake_year, current_semester,
        )

    async def create_lecturer_profile(
        self,
        connection: asyncpg.Connection,
        *,
        profile_id: UUID,
        user_id: UUID,
        employee_number: str,
        first_name: str,
        middle_name: str | None,
        last_name: str,
        department_id: UUID,
        designation: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO academic.lecturer_profiles (
                id, user_id, employee_number, first_name, middle_name, last_name,
                department_id, designation, profile_status, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'active',now(),now())
            """,
            profile_id, user_id, employee_number, first_name, middle_name, last_name,
            department_id, designation,
        )

    async def create_administrator_profile(
        self,
        connection: asyncpg.Connection,
        *,
        profile_id: UUID,
        user_id: UUID,
        first_name: str,
        middle_name: str | None,
        last_name: str,
        department_id: UUID,
        administrative_scope: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO academic.administrator_profiles (
                id, user_id, first_name, middle_name, last_name, department_id,
                administrative_scope, profile_status, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,'active',now(),now())
            """,
            profile_id, user_id, first_name, middle_name, last_name,
            department_id, administrative_scope,
        )

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
