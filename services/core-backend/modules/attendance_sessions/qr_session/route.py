from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent

from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    DynamicQrConfigurationError,
    DynamicQrSessionUnavailableError,
    QrSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.cache import QrBatchMetadataCache
from modules.attendance_sessions.qr_session.schemas import (
    CreateQrSessionRequest,
    CreateQrSessionResponse,
    CurrentDynamicQrSessionResponse,
    VerifyQrSessionRequest,
    VerifyQrSessionResponse,
)
from modules.attendance_sessions.qr_session.service import QrSessionService
from modules.attendance_sessions.qr_session.service import (
    CurrentDynamicQrSession,
    SSE_RECONNECT_RETRY_MS,
)

router = APIRouter(tags=["qr-sessions"])
create_qr_session_router = APIRouter(
    prefix="/attendance-sessions/{session_id}/qr-sessions",
)
verify_qr_session_router = APIRouter(prefix="/qr-sessions/{qr_session_id}")


def get_qr_session_service(request: Request) -> QrSessionService:
    redis_client = getattr(request.app.state, "redis_client", None)
    settings = getattr(request.app.state, "settings", None)
    dynamic_qr_hmac_secret = getattr(settings, "dynamic_qr_hmac_secret", None)
    return QrSessionService(
        qr_batch_cache=QrBatchMetadataCache(redis_client),
        dynamic_qr_hmac_secret=dynamic_qr_hmac_secret,
    )


async def get_initial_dynamic_qr_session(
    qr_session_id: UUID,
    http_request: Request,
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> CurrentDynamicQrSession:
    try:
        return await qr_session_service.get_current_dynamic_qr_session(
            http_request.app.state.db_pool,
            qr_session_id,
        )
    except QrSessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR session was not found.",
        ) from error
    except DynamicQrSessionUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error.message,
        ) from error
    except DynamicQrConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error.message,
        ) from error


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
    try:
        verified_qr_session = await qr_session_service.verify_qr_session(
            http_request.app.state.db_pool,
            qr_session_id,
            payload.qr_value,
        )
    except DynamicQrConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error.message,
        ) from error

    return VerifyQrSessionResponse(
        qr_session_id=verified_qr_session.qr_session_id,
        status=verified_qr_session.status,
        verified_at=verified_qr_session.verified_at,
    )


@verify_qr_session_router.get(
    "/current",
    response_model=CurrentDynamicQrSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_current_dynamic_qr_session(
    qr_session_id: UUID,
    http_request: Request,
    current_qr_session: CurrentDynamicQrSession = Depends(
        get_initial_dynamic_qr_session,
    ),
) -> CurrentDynamicQrSessionResponse:
    return CurrentDynamicQrSessionResponse(
        qr_session_id=current_qr_session.qr_session_id,
        qr_value=current_qr_session.qr_value,
        sequence=current_qr_session.sequence,
        valid_from=current_qr_session.valid_from,
        expires_at=current_qr_session.expires_at,
    )


@verify_qr_session_router.get(
    "/stream",
    response_class=EventSourceResponse,
    status_code=status.HTTP_200_OK,
)
async def stream_current_dynamic_qr_session(
    qr_session_id: UUID,
    http_request: Request,
    current_qr_session: CurrentDynamicQrSession = Depends(
        get_initial_dynamic_qr_session,
    ),
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> AsyncIterator[ServerSentEvent]:
    async for streamed_qr_session in qr_session_service.stream_current_dynamic_qr_sessions(
        http_request.app.state.db_pool,
        qr_session_id,
        initial_qr_session=current_qr_session,
        is_disconnected=http_request.is_disconnected,
    ):
        yield ServerSentEvent(
            event="qr.rotate",
            data=CurrentDynamicQrSessionResponse(
                qr_session_id=streamed_qr_session.qr_session_id,
                qr_value=streamed_qr_session.qr_value,
                sequence=streamed_qr_session.sequence,
                valid_from=streamed_qr_session.valid_from,
                expires_at=streamed_qr_session.expires_at,
            ).model_dump(mode="json", by_alias=True),
            retry=SSE_RECONNECT_RETRY_MS,
        )


router.include_router(create_qr_session_router)
router.include_router(verify_qr_session_router)
