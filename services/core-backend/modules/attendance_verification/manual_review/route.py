from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.attendance_verification.manual_review.exception import (
    VerificationAttemptNotFailedError,
    VerificationAttemptNotFoundError,
)
from modules.attendance_verification.manual_review.schemas import (
    ManualReviewDecisionRequest,
    ManualReviewQueueItemResponse,
)
from modules.attendance_verification.manual_review.service import ManualReviewService
from modules.identity.auth.dependencies import CurrentLecturer

router = APIRouter(prefix="/lecturers/me/manual-reviews", tags=["manual-review"])

_PROFILE_NOT_FOUND_DETAIL = "An active lecturer profile was not found for this account."
_ATTEMPT_NOT_FOUND_DETAIL = "The verification attempt was not found."


def get_manual_review_service() -> ManualReviewService:
    return ManualReviewService()


@router.get("", response_model=list[ManualReviewQueueItemResponse], status_code=status.HTTP_200_OK)
async def list_my_manual_review_queue(
    http_request: Request,
    current_lecturer: CurrentLecturer,
    session_id: UUID | None = None,
    review_service: Annotated[
        ManualReviewService,
        Depends(get_manual_review_service),
    ] = None,  # type: ignore[assignment]
) -> list[ManualReviewQueueItemResponse]:
    try:
        items = await review_service.list_queue_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            session_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error

    return [ManualReviewQueueItemResponse.from_record(item) for item in items]


@router.post(
    "/{verification_attempt_id}/decision",
    response_model=ManualReviewQueueItemResponse,
    status_code=status.HTTP_200_OK,
)
async def decide_my_manual_review(
    verification_attempt_id: UUID,
    body: ManualReviewDecisionRequest,
    http_request: Request,
    current_lecturer: CurrentLecturer,
    review_service: Annotated[
        ManualReviewService,
        Depends(get_manual_review_service),
    ] = None,  # type: ignore[assignment]
) -> ManualReviewQueueItemResponse:
    try:
        item = await review_service.decide_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
            verification_attempt_id,
            body.decision,
            body.reason,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _PROFILE_NOT_FOUND_DETAIL) from error
    except VerificationAttemptNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ATTEMPT_NOT_FOUND_DETAIL) from error
    except VerificationAttemptNotFailedError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only failed verification attempts can be manually reviewed.",
        ) from error

    return ManualReviewQueueItemResponse.from_record(item)
