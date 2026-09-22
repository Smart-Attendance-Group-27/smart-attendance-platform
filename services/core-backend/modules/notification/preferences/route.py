from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.errors import error_detail
from modules.identity.auth.dependencies import CurrentStudent
from modules.notification.preferences.schemas import (
    NotificationPreferenceResponse,
    NotificationPreferencesUpdateRequest,
)
from modules.notification.preferences.service import (
    InvalidNotificationPreferenceError,
    NotificationPreferencesService,
)

router = APIRouter(
    prefix="/students/me/notification-preferences",
    tags=["notification-preferences"],
)


def get_notification_preferences_service() -> NotificationPreferencesService:
    return NotificationPreferencesService()


@router.get("", response_model=list[NotificationPreferenceResponse])
async def list_notification_preferences(
    request: Request,
    current_user: CurrentStudent,
    service: Annotated[
        NotificationPreferencesService,
        Depends(get_notification_preferences_service),
    ] = None,  # type: ignore[assignment]
) -> list[NotificationPreferenceResponse]:
    records = await service.list_for_user(request.app.state.db_pool, current_user.user_id)
    return [NotificationPreferenceResponse.from_record(record) for record in records]


@router.put("", response_model=list[NotificationPreferenceResponse])
async def update_notification_preferences(
    body: NotificationPreferencesUpdateRequest,
    request: Request,
    current_user: CurrentStudent,
    service: Annotated[
        NotificationPreferencesService,
        Depends(get_notification_preferences_service),
    ] = None,  # type: ignore[assignment]
) -> list[NotificationPreferenceResponse]:
    try:
        records = await service.update_for_user(
            request.app.state.db_pool,
            user_id=current_user.user_id,
            updates=body.preferences,
        )
    except InvalidNotificationPreferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_detail(
                "INVALID_NOTIFICATION_PREFERENCE",
                f"Notification type '{error.type_code}' is not configurable.",
            ),
        ) from error
    return [NotificationPreferenceResponse.from_record(record) for record in records]
