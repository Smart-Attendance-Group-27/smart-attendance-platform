from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import ValidationError

from modules.academic.attendance_policy.repository import PolicySnapshot
from modules.academic.attendance_policy.schemas import PolicyResponse, PolicyWriteRequest
from modules.academic.attendance_policy.service import (
    AttendancePolicyService,
    PolicyUnavailableError,
)
from modules.identity.auth.dependencies import CurrentAdministrator


router = APIRouter(prefix="/administrators/me/attendance-policy", tags=["attendance-policy"])


def get_attendance_policy_service() -> AttendancePolicyService:
    return AttendancePolicyService()


def _response(policy: PolicySnapshot) -> PolicyResponse:
    return PolicyResponse(
        check_in_window_minutes=policy.check_in_window_minutes,
        late_threshold_minutes=policy.late_threshold_minutes,
        qr_default_validity_minutes=policy.qr_default_validity_minutes,
        face_confidence_threshold_percent=policy.face_confidence_threshold_percent,
        updated_at=policy.updated_at,
        updated_by_name=policy.updated_by_name,
    )


@router.get("", response_model=PolicyResponse)
async def get_attendance_policy(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    policy_service: Annotated[
        AttendancePolicyService, Depends(get_attendance_policy_service),
    ] = None,  # type: ignore[assignment]
) -> PolicyResponse:
    try:
        return _response(await policy_service.get_current(http_request.app.state.db_pool))
    except PolicyUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Attendance policy is unavailable.") from error


@router.put("", response_model=PolicyResponse)
async def put_attendance_policy(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    body: Annotated[object | None, Body()] = None,
    policy_service: Annotated[
        AttendancePolicyService, Depends(get_attendance_policy_service),
    ] = None,  # type: ignore[assignment]
) -> PolicyResponse:
    try:
        validated = PolicyWriteRequest.model_validate(body)
    except ValidationError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "INVALID_POLICY", "message": "Attendance policy values are invalid."},
        ) from error
    return _response(await policy_service.replace_active(
        http_request.app.state.db_pool, current_administrator.user_id, validated,
    ))
