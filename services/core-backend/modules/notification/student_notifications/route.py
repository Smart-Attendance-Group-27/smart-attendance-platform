from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.identity.auth.dependencies import CurrentStudent
from modules.notification.student_notifications.schemas import (
    StudentNotificationResponse,
)
from modules.notification.student_notifications.service import (
    StudentNotificationService,
)

router = APIRouter(prefix="/students/me/notifications", tags=["student-notifications"])


def get_student_notification_service() -> StudentNotificationService:
    return StudentNotificationService()


@router.get(
    "",
    response_model=list[StudentNotificationResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_notifications(
    http_request: Request,
    current_student: CurrentStudent,
    notification_service: Annotated[
        StudentNotificationService,
        Depends(get_student_notification_service),
    ] = None,  # type: ignore[assignment]
) -> list[StudentNotificationResponse]:
    notifications = await notification_service.list_for_user(
        http_request.app.state.db_pool,
        current_student.user_id,
    )

    return [
        StudentNotificationResponse(
            id=notification.id,
            title=notification.title,
            message=notification.message,
            type=notification.type,
            created_at=notification.created_at,
            is_read=notification.is_read,
            related_id=notification.related_id,
        )
        for notification in notifications
    ]


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_200_OK,
)
async def mark_my_notification_as_read(
    notification_id: UUID,
    http_request: Request,
    current_student: CurrentStudent,
    notification_service: Annotated[
        StudentNotificationService,
        Depends(get_student_notification_service),
    ] = None,  # type: ignore[assignment]
) -> dict[str, bool]:
    marked = await notification_service.mark_as_read(
        http_request.app.state.db_pool,
        user_id=current_student.user_id,
        notification_id=notification_id,
    )
    if not marked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification was not found for this account.",
        )

    return {"ok": True}
