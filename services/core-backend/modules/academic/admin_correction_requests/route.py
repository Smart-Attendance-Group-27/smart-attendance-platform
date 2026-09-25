from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from core.errors import error_detail
from modules.academic.admin_correction_requests.exception import (
    CorrectionRequestNotFoundError,
    InvalidDecisionError,
    InvalidReviewNoteError,
)
from modules.academic.admin_correction_requests.schemas import (
    AdminCorrectionRequestResponse,
    DecideCorrectionRequestBody,
)
from modules.academic.admin_correction_requests.service import AdminCorrectionRequestService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-correction-requests"])


def get_admin_correction_request_service() -> AdminCorrectionRequestService:
    return AdminCorrectionRequestService()


@router.get(
    "/correction-requests",
    response_model=list[AdminCorrectionRequestResponse],
    status_code=status.HTTP_200_OK,
)
async def list_correction_requests(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    status_filter: Annotated[
        str | None,
        Query(alias="status", pattern="^(pending|approved|rejected|resolved)$"),
    ] = None,
    service: Annotated[
        AdminCorrectionRequestService,
        Depends(get_admin_correction_request_service),
    ] = None,  # type: ignore[assignment]
) -> list[AdminCorrectionRequestResponse]:
    records = await service.list_requests(http_request.app.state.db_pool, status=status_filter)
    return [AdminCorrectionRequestResponse.from_record(record) for record in records]


@router.post(
    "/correction-requests/{request_id}/decision",
    response_model=AdminCorrectionRequestResponse,
    status_code=status.HTTP_200_OK,
)
async def decide_correction_request(
    request_id: UUID,
    body: DecideCorrectionRequestBody,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    service: Annotated[
        AdminCorrectionRequestService,
        Depends(get_admin_correction_request_service),
    ] = None,  # type: ignore[assignment]
) -> AdminCorrectionRequestResponse:
    try:
        record = await service.decide(
            http_request.app.state.db_pool,
            actor_user_id=current_administrator.user_id,
            request_id=request_id,
            decision=body.decision,
            note=body.note,
        )
    except CorrectionRequestNotFoundError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            error_detail("CORRECTION_REQUEST_NOT_FOUND", "The correction request was not found."),
        ) from error
    except InvalidDecisionError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            error_detail("CORRECTION_DECISION_NOT_ALLOWED", str(error)),
        ) from error
    except InvalidReviewNoteError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_detail("CORRECTION_NOTE_INVALID", str(error)),
        ) from error

    return AdminCorrectionRequestResponse.from_record(record)
