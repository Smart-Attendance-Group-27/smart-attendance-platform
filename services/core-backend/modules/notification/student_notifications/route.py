from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from core.errors import error_detail
from modules.identity.auth.dependencies import CurrentStudent
from modules.notification.student_notifications.schemas import (
    StudentNotificationPageResponse,
    StudentNotificationResponse,
)
from modules.notification.student_notifications.service import (
    StudentNotificationService,
)

router = APIRouter(prefix="/students/me/notifications", tags=["student-notifications"])


def get_student_notification_service() -> StudentNotificationService:
    return StudentNotificationService()


def _response(notification) -> StudentNotificationResponse:
    return StudentNotificationResponse(
        id=notification.id,
        title=notification.title,
        message=notification.message,
        type=notification.type,
        code=notification.code,
        created_at=notification.created_at,
        is_read=notification.is_read,
        related_id=notification.related_id,
        related_entity_type=notification.related_entity_type,
    )


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

    return [_response(notification) for notification in notifications]


@router.get("/page", response_model=StudentNotificationPageResponse)
async def list_my_notification_page(
    http_request: Request,
    current_student: CurrentStudent,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    notification_service: Annotated[
        StudentNotificationService, Depends(get_student_notification_service),
    ] = None,  # type: ignore[assignment]
) -> StudentNotificationPageResponse:
    page = await notification_service.page_for_user(
        http_request.app.state.db_pool, current_student.user_id,
        limit=limit, offset=offset,
    )
    return StudentNotificationPageResponse(
        items=[_response(item) for item in page.items],
        next_offset=page.next_offset,
        unread_count=page.unread_count,
    )


@router.get("/unread-count")
async def get_my_unread_count(
    http_request: Request,
    current_student: CurrentStudent,
    notification_service: Annotated[
        StudentNotificationService, Depends(get_student_notification_service),
    ] = None,  # type: ignore[assignment]
) -> dict[str, int]:
    count = await notification_service.unread_count(
        http_request.app.state.db_pool, current_student.user_id,
    )
    return {"unreadCount": count}


@router.post("/read-all")
async def mark_all_my_notifications_as_read(
    http_request: Request,
    current_student: CurrentStudent,
    notification_service: Annotated[
        StudentNotificationService, Depends(get_student_notification_service),
    ] = None,  # type: ignore[assignment]
) -> dict[str, int]:
    updated = await notification_service.mark_all_as_read(
        http_request.app.state.db_pool, current_student.user_id,
    )
    return {"updated": updated}


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
            detail=error_detail(
                "NOTIFICATION_NOT_FOUND", "Notification was not found for this account.",
            ),
        )

    return {"ok": True}
