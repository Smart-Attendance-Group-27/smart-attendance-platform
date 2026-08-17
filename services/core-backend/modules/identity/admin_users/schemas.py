from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.identity.admin_users.repository import (
    AdministratorAccountRecord,
    LecturerAccountRecord,
    StudentAccountRecord,
    UserAccountRecord,
)

ACTIVE_ACCOUNT_STATUS = "active"


class SettableAccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


def derive_effective_status(record: UserAccountRecord, *, now: datetime | None = None) -> str:
    """"locked" is derived from locked_until (a security lockout, not an admin
    choice) — the same derive-from-timestamp pattern used for session status,
    so a stale account_status column can never misreport an active lockout."""
    current_time = now or datetime.now(UTC)
    if record.locked_until is not None and record.locked_until > current_time:
        return "locked"
    return record.account_status or ACTIVE_ACCOUNT_STATUS


class AccountStatusUpdateRequest(BaseModel):
    account_status: SettableAccountStatus = Field(alias="accountStatus")

    model_config = ConfigDict(populate_by_name=True)


class AccountStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    account_status: str = Field(alias="accountStatus")

    @staticmethod
    def from_record(record: UserAccountRecord) -> "AccountStatusResponse":
        return AccountStatusResponse(
            user_id=record.id,
            account_status=derive_effective_status(record),
        )


class StudentAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    registration_number: str = Field(alias="registrationNumber")
    full_name: str = Field(alias="fullName")
    email: str = Field(alias="email")
    department: str | None = Field(alias="department")
    intake_year: int | None = Field(alias="intakeYear")
    current_semester: int | None = Field(alias="currentSemester")
    account_status: str = Field(alias="accountStatus")
    profile_status: str = Field(alias="profileStatus")

    @staticmethod
    def from_record(record: StudentAccountRecord) -> "StudentAccountResponse":
        return StudentAccountResponse(
            user_id=record.user_id,
            registration_number=record.registration_number or "",
            full_name=record.full_name,
            email=record.email or "",
            department=record.department_name,
            intake_year=record.intake_year,
            current_semester=record.current_semester,
            account_status=record.account_status or ACTIVE_ACCOUNT_STATUS,
            profile_status=record.profile_status or "",
        )


class LecturerAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    employee_number: str = Field(alias="employeeNumber")
    full_name: str = Field(alias="fullName")
    email: str = Field(alias="email")
    department: str | None = Field(alias="department")
    designation: str | None = Field(alias="designation")
    account_status: str = Field(alias="accountStatus")
    profile_status: str = Field(alias="profileStatus")

    @staticmethod
    def from_record(record: LecturerAccountRecord) -> "LecturerAccountResponse":
        return LecturerAccountResponse(
            user_id=record.user_id,
            employee_number=record.employee_number or "",
            full_name=record.full_name,
            email=record.email or "",
            department=record.department_name,
            designation=record.designation,
            account_status=record.account_status or ACTIVE_ACCOUNT_STATUS,
            profile_status=record.profile_status or "",
        )


class AdministratorAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    full_name: str = Field(alias="fullName")
    email: str = Field(alias="email")
    department: str | None = Field(alias="department")
    administrative_scope: str | None = Field(alias="administrativeScope")
    account_status: str = Field(alias="accountStatus")
    profile_status: str = Field(alias="profileStatus")

    @staticmethod
    def from_record(record: AdministratorAccountRecord) -> "AdministratorAccountResponse":
        return AdministratorAccountResponse(
            user_id=record.user_id,
            full_name=record.full_name,
            email=record.email or "",
            department=record.department_name,
            administrative_scope=record.administrative_scope,
            account_status=record.account_status or ACTIVE_ACCOUNT_STATUS,
            profile_status=record.profile_status or "",
        )


class UserDirectoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    students: list[StudentAccountResponse]
    lecturers: list[LecturerAccountResponse]
    administrators: list[AdministratorAccountResponse]
