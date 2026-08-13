from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.schemas import (
    CreateQrSessionRequest,
    CreateQrSessionResponse,
    VerifyQrSessionRequest,
    VerifyQrSessionResponse,
)
from modules.attendance_sessions.qr_session.service import QrSessionService

router = APIRouter(tags=["qr-sessions"])
create_qr_session_router = APIRouter(
    prefix="/attendance-sessions/{session_id}/qr-sessions",
)
verify_qr_session_router = APIRouter(prefix="/qr-sessions/{qr_session_id}")


def get_qr_session_service() -> QrSessionService:
    return QrSessionService()


@create_qr_session_router.post(
    "",
    response_model=CreateQrSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_qr_session(
    session_id: UUID,
    http_request: Request,
    payload: Annotated[CreateQrSessionRequest | None, Body()] = None,
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> CreateQrSessionResponse:
    request_payload = payload or CreateQrSessionRequest()

    try:
        if request_payload.mode == "dynamic":
            assert request_payload.refresh_interval_seconds is not None
            created_qr_session = await qr_session_service.create_dynamic_qr_session(
                http_request.app.state.db_pool,
                session_id,
                request_payload.valid_for_seconds,
                request_payload.refresh_interval_seconds,
            )
        else:
            created_qr_session = await qr_session_service.create_static_qr_session(
                http_request.app.state.db_pool,
                session_id,
                request_payload.valid_for_seconds,
            )
    except AttendanceSessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session was not found.",
        ) from error
    except AttendanceSessionNotActiveError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error.message,
        ) from error

    return CreateQrSessionResponse(
        qr_session_id=created_qr_session.qr_session_id,
        attendance_session_id=created_qr_session.attendance_session_id,
        mode=created_qr_session.mode,
        qr_value=created_qr_session.qr_value,
        refresh_interval_seconds=created_qr_session.refresh_interval_seconds,
        status=created_qr_session.status,
        valid_from=created_qr_session.valid_from,
        expires_at=created_qr_session.expires_at,
    )


@verify_qr_session_router.post(
    "/verify",
    response_model=VerifyQrSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_qr_session(
    qr_session_id: UUID,
    http_request: Request,
    payload: VerifyQrSessionRequest,
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> VerifyQrSessionResponse:
    verified_qr_session = await qr_session_service.verify_qr_session(
        http_request.app.state.db_pool,
        qr_session_id,
        payload.qr_value,
    )

    return VerifyQrSessionResponse(
        qr_session_id=verified_qr_session.qr_session_id,
        status=verified_qr_session.status,
        verified_at=verified_qr_session.verified_at,
    )


router.include_router(create_qr_session_router)
router.include_router(verify_qr_session_router)
