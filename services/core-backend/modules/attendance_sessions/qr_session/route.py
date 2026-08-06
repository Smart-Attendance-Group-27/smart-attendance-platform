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
)
from modules.attendance_sessions.qr_session.service import QrSessionService

router = APIRouter(
    prefix="/attendance-sessions/{session_id}/qr-sessions",
    tags=["qr-sessions"],
)


def get_qr_session_service() -> QrSessionService:
    return QrSessionService()


@router.post(
    "",
    response_model=CreateQrSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_static_qr_session(
    session_id: UUID,
    http_request: Request,
    payload: Annotated[CreateQrSessionRequest | None, Body()] = None,
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> CreateQrSessionResponse:
    request_payload = payload or CreateQrSessionRequest()

    try:
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
        qr_value=created_qr_session.qr_value,
        status=created_qr_session.status,
        valid_from=created_qr_session.valid_from,
        expires_at=created_qr_session.expires_at,
    )
