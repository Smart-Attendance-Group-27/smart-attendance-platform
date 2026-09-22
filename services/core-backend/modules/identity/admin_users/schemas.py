from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from modules.identity.admin_users.repository import (
    AdministratorAccountRecord,
    DepartmentOptionRecord,
    LecturerAccountRecord,
    StudentAccountRecord,
    UserAccountRecord,
)

ACTIVE_ACCOUNT_STATUS = "active"


class SettableAccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ProvisionedAccountRole(str, Enum):
    STUDENT = "student"
    LECTURER = "lecturer"
    ADMINISTRATOR = "administrator"


class AccountProvisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    role: ProvisionedAccountRole
    email: str = Field(min_length=3, max_length=255)
    first_name: str = Field(alias="firstName", min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, alias="middleName", max_length=100)
    last_name: str = Field(alias="lastName", min_length=1, max_length=100)
    department_id: UUID = Field(alias="departmentId")
    registration_number: str | None = Field(
        default=None,
        alias="registrationNumber",
        max_length=30,
    )
    intake_year: int | None = Field(default=None, alias="intakeYear", ge=1900, le=2100)
    current_semester: int | None = Field(default=None, alias="currentSemester", ge=1, le=20)
    employee_number: str | None = Field(default=None, alias="employeeNumber", max_length=30)
    designation: str | None = Field(default=None, max_length=100)
    administrative_scope: str | None = Field(
        default=None,
        alias="administrativeScope",
        max_length=30,
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.lower()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("email must be a valid address")
        return normalized

    @model_validator(mode="after")
    def require_role_fields(self) -> "AccountProvisionRequest":
        required_by_role = {
            ProvisionedAccountRole.STUDENT: (
                "registration_number",
                "intake_year",
                "current_semester",
            ),
            ProvisionedAccountRole.LECTURER: ("employee_number", "designation"),
            ProvisionedAccountRole.ADMINISTRATOR: ("administrative_scope",),
        }
        missing = [field for field in required_by_role[self.role] if not getattr(self, field)]
        if missing:
            aliases = {
                "registration_number": "registrationNumber",
                "intake_year": "intakeYear",
                "current_semester": "currentSemester",
                "employee_number": "employeeNumber",
                "administrative_scope": "administrativeScope",
            }
            raise ValueError(
                f"{', '.join(aliases.get(field, field) for field in missing)} required for {self.role.value}",
            )
        return self


class ProvisionedAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    keycloak_user_id: str = Field(alias="keycloakUserId")
    role: ProvisionedAccountRole
    email: str
    temporary_password: str = Field(alias="temporaryPassword")


class ProvisioningOptionResponse(BaseModel):
    id: UUID
    label: str

    @staticmethod
    def from_record(record: DepartmentOptionRecord) -> "ProvisioningOptionResponse":
        return ProvisioningOptionResponse(id=record.id, label=record.label)


class AccountProvisioningOptionsResponse(BaseModel):
    departments: list[ProvisioningOptionResponse]


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
