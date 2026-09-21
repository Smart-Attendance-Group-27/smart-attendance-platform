from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.identity.auth.dependencies import CurrentUser
from modules.notification.device_tokens.exception import (
    InvalidExpoPushTokenError,
    UnsupportedPlatformError,
)
from modules.notification.device_tokens.schemas import (
    DeviceTokenResponse,
    RegisterDeviceRequest,
    RevokeDeviceRequest,
)
from modules.notification.device_tokens.service import DeviceTokenService

router = APIRouter(prefix="/notifications/devices", tags=["notification-devices"])


def get_device_token_service() -> DeviceTokenService:
    return DeviceTokenService()


@router.post(
    "",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_device(
    payload: RegisterDeviceRequest,
    http_request: Request,
    current_user: CurrentUser,
    service: Annotated[
        DeviceTokenService,
        Depends(get_device_token_service),
    ] = None,  # type: ignore[assignment]
) -> DeviceTokenResponse:
    """Register (or reactivate) a device push token for the authenticated user.

    Called by the mobile app after the user grants notification permission.
    The authenticated user's ID is always resolved from the verified JWT —
    the request body must never supply a user_id.
    """
    try:
        record = await service.register(
            http_request.app.state.db_pool,
            user_id=current_user.user_id,
            expo_push_token=payload.expo_push_token,
            platform=payload.platform,
        )
    except InvalidExpoPushTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error.message,
        ) from error
    except UnsupportedPlatformError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error.message,
        ) from error

    return DeviceTokenResponse(
        id=record.id,
        platform=record.platform,
        isActive=record.is_active,
        registeredAt=record.registered_at,
    )


@router.post(
    "/revoke",
    status_code=status.HTTP_200_OK,
)
@router.delete(
    "",
    status_code=status.HTTP_200_OK,
)
async def revoke_device(
    payload: RevokeDeviceRequest,
    http_request: Request,
    current_user: CurrentUser,
    service: Annotated[
        DeviceTokenService,
        Depends(get_device_token_service),
    ] = None,  # type: ignore[assignment]
) -> dict[str, bool]:
    """Revoke a registered device push token for the authenticated user."""
    try:
        revoked = await service.revoke(
            http_request.app.state.db_pool,
            user_id=current_user.user_id,
            expo_push_token=payload.expo_push_token,
        )
    except InvalidExpoPushTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error.message,
        ) from error

    return {"ok": True, "revoked": revoked}

