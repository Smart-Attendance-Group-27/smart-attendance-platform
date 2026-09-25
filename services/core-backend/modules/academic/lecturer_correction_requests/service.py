from uuid import UUID, uuid4

import asyncpg

from modules.academic.lecturer_correction_requests.exception import (
    CorrectionRequestInvalidError,
    CorrectionTargetNotFoundError,
)
from modules.academic.lecturer_correction_requests.repository import (
    CorrectionRequestRecord,
    CorrectionRequestRepository,
    OwnCorrectionRequestRecord,
)
from modules.academic.lecturer_correction_requests.schemas import (
    CorrectionCategory,
    CorrectionRequestType,
)
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.audit.repository import write_audit_log

ACTIVE_PROFILE_STATUS = "active"
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ACTION = "correction_request.submitted"
AUDIT_ENTITY_TYPE = "correction_request"
MIN_DESCRIPTION_LENGTH = 10
MAX_DESCRIPTION_LENGTH = 1000

_TIMETABLE_CATEGORIES = {
    CorrectionCategory.TIMETABLE_DAY_TIME,
    CorrectionCategory.TIMETABLE_ROOM,
    CorrectionCategory.TIMETABLE_MISSING,
    CorrectionCategory.OTHER,
}
_COURSE_CATEGORIES = {
    CorrectionCategory.COURSE_DETAILS,
    CorrectionCategory.ENROLMENT,
    CorrectionCategory.LECTURER_ASSIGNMENT,
    CorrectionCategory.OTHER,
}


class CorrectionRequestService:
    """Records a lecturer's correction request for administrative review.

    The academic tables are never edited here. Only requests that concern a
    course offering the lecturer is assigned to are accepted.
    """

    def __init__(
        self,
        repository: CorrectionRequestRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
    ) -> None:
        self._repository = repository or CorrectionRequestRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )

    async def list_own(
        self,
        pool: asyncpg.Pool,
        *,
        user_id: UUID,
    ) -> list[OwnCorrectionRequestRecord]:
        async with pool.acquire() as connection:
            profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
            if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
                raise LecturerProfileNotFoundError(
                    "No active lecturer profile exists for this account."
                )
            return await self._repository.list_for_requester(connection, user_id)

    async def submit(
        self,
        pool: asyncpg.Pool,
        *,
        user_id: UUID,
        request_type: CorrectionRequestType,
        category: CorrectionCategory,
        course_offering_id: UUID | None,
        timetable_entry_id: UUID | None,
        description: str,
    ) -> CorrectionRequestRecord:
        description = description.strip()
        if not MIN_DESCRIPTION_LENGTH <= len(description) <= MAX_DESCRIPTION_LENGTH:
            raise CorrectionRequestInvalidError(
                f"Description must be {MIN_DESCRIPTION_LENGTH}-{MAX_DESCRIPTION_LENGTH} characters."
            )

        allowed = (
            _TIMETABLE_CATEGORIES
            if request_type is CorrectionRequestType.TIMETABLE
            else _COURSE_CATEGORIES
        )
        if category not in allowed:
            raise CorrectionRequestInvalidError("Category does not apply to this request type.")

        async with pool.acquire() as connection, connection.transaction():
            profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
            if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
                raise LecturerProfileNotFoundError(
                    "No active lecturer profile exists for this account."
                )

            if request_type is CorrectionRequestType.TIMETABLE:
                if timetable_entry_id is None:
                    raise CorrectionRequestInvalidError("Select the timetable entry.")
                offering_id = await self._repository.find_assigned_timetable_offering(
                    connection, profile.id, timetable_entry_id
                )
                if offering_id is None:
                    raise CorrectionTargetNotFoundError("Timetable entry not found.")
            else:
                if course_offering_id is None:
                    raise CorrectionRequestInvalidError("Select the course.")
                if not await self._repository.is_offering_assigned(
                    connection, profile.id, course_offering_id
                ):
                    raise CorrectionTargetNotFoundError("Course not found.")
                offering_id = course_offering_id
                timetable_entry_id = None

            record = await self._repository.insert(
                connection,
                request_id=uuid4(),
                requested_by=user_id,
                request_type=request_type.value,
                course_offering_id=offering_id,
                timetable_entry_id=timetable_entry_id,
                category=category.value,
                description=description,
            )
            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action=AUDIT_ACTION,
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=record.id,
                new_values={
                    "requestType": record.request_type,
                    "category": record.category,
                    "courseOfferingId": str(record.course_offering_id),
                    "timetableEntryId": (
                        str(record.timetable_entry_id) if record.timetable_entry_id else None
                    ),
                },
            )
            return record
