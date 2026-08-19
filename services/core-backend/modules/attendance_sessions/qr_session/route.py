from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent

from modules.attendance_sessions.qr_session.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    DynamicQrConfigurationError,
    DynamicQrSessionUnavailableError,
    LecturerSessionAccessError,
    QrNotRequiredError,
    QrSessionNotFoundError,
    StudentNotEligibleError,
    VerificationNotStartedError,
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
from modules.identity.auth.dependencies import CurrentLecturer, CurrentStudent

router = APIRouter(tags=["qr-sessions"])
# Lecturer-facing endpoint group: a QR session is always launched under a
# parent attendance session.
create_qr_session_router = APIRouter(
    prefix="/attendance-sessions/{session_id}/qr-sessions",
)
# Student/stream endpoint group: after creation, the QR batch ID becomes the
# qr_session_id used for current QR, SSE stream, and verification requests.
verify_qr_session_router = APIRouter(prefix="/qr-sessions/{qr_session_id}")

_SESSION_NOT_FOUND_DETAIL = "The attendance session was not found, or does not belong to this lecturer."
_QR_SESSION_NOT_FOUND_DETAIL = "The QR session was not found, or does not belong to this lecturer."
_QR_NOT_REQUIRED_DETAIL = "QR verification is not enabled for this attendance session."


def get_qr_session_service(request: Request) -> QrSessionService:
    # Infrastructure is injected from FastAPI app.state. Redis is optional:
    # without it, the cache wrapper returns misses and the service reads the
    # source-of-truth metadata from PostgreSQL.
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
    current_lecturer: CurrentLecturer,
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> CurrentDynamicQrSession:
    # Shared dependency for /current and /stream. It checks lecturer ownership
    # before exposing any dynamic QR value to the lecturer web UI.
    try:
        await qr_session_service.assert_lecturer_owns_qr_session(
            http_request.app.state.db_pool,
            qr_session_id,
            current_lecturer.user_id,
        )
        return await qr_session_service.get_current_dynamic_qr_session(
            http_request.app.state.db_pool,
            qr_session_id,
        )
    except LecturerSessionAccessError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_QR_SESSION_NOT_FOUND_DETAIL,
        ) from error
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
    current_lecturer: CurrentLecturer,
    payload: Annotated[CreateQrSessionRequest | None, Body()] = None,
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> CreateQrSessionResponse:
    request_payload = payload or CreateQrSessionRequest()

    try:
        # Static and dynamic QR session creation accordingly 
        if request_payload.mode == "dynamic":
            assert request_payload.refresh_interval_seconds is not None
            created_qr_session = await qr_session_service.create_dynamic_qr_session(
                http_request.app.state.db_pool,
                session_id,
                request_payload.valid_for_seconds,
                request_payload.refresh_interval_seconds,
                current_lecturer.user_id,
            )
        else:
            created_qr_session = await qr_session_service.create_static_qr_session(
                http_request.app.state.db_pool,
                session_id,
                request_payload.valid_for_seconds,
                current_lecturer.user_id,
            )
    except (AttendanceSessionNotFoundError, LecturerSessionAccessError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_SESSION_NOT_FOUND_DETAIL,
        ) from error
    except QrNotRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_QR_NOT_REQUIRED_DETAIL,
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
    current_student: CurrentStudent,
    qr_session_service: QrSessionService = Depends(get_qr_session_service),
) -> VerifyQrSessionResponse:
    try:
        # The route receives the scanned raw qrValue from mobile, but the
        # service immediately hashes/classifies it and never stores that raw
        # value.
        verified_qr_session = await qr_session_service.verify_qr_session(
            http_request.app.state.db_pool,
            qr_session_id,
            payload.qr_value,
            current_student.user_id,
        )
    except QrSessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR session was not found.",
        ) from error
    except ActiveStudentProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An active student profile was not found for this account.",
        ) from error
    except StudentNotEligibleError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The student is not eligible for this attendance session.",
        ) from error
    except VerificationNotStartedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verification has not started for this session yet.",
        ) from error
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
    # Dynamic QR uses SSE so the lecturer page keeps one connection open and
    # receives each rotated QR value as a qr.rotate event.
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
