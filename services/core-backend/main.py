import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from cache.redis import close_redis_client, create_redis_client
from core.config import get_settings
from db.pool import close_database_pool, create_database_pool
from modules.academic.admin_academic_data.route import (
    router as admin_academic_data_router,
)
from modules.academic.admin_classrooms.route import router as admin_classrooms_router
from modules.academic.admin_dashboard.route import router as admin_dashboard_router
from modules.academic.admin_institution_reports.route import (
    router as admin_institution_reports_router,
)
from modules.academic.admin_reference_faces.route import (
    router as admin_reference_faces_router,
)
from modules.academic.attendance_policy.route import router as attendance_policy_router
from modules.academic.lecturer_correction_requests.route import (
    router as lecturer_correction_requests_router,
)
from modules.academic.lecturer_courses.route import router as lecturer_courses_router
from modules.academic.lecturer_reports.route import router as lecturer_reports_router
from modules.academic.student_courses.route import router as student_courses_router
from modules.academic.student_profile.route import router as student_profile_router
from modules.attendance_sessions.active_sessions.route import (
    router as active_session_router,
)
from modules.attendance_sessions.lecturer_sessions.route import (
    router as lecturer_sessions_router,
)
from modules.attendance_sessions.qr_session.route import router as qr_session_router
from modules.attendance_verification.check_in.route import router as check_in_router
from modules.attendance_verification.face.route import router as face_router
from modules.attendance_verification.geofence.route import router as geofence_router
from modules.attendance_verification.manual_review.route import (
    router as manual_review_router,
)
from modules.audit.admin_log.route import router as admin_audit_log_router
from modules.identity.admin_users.route import router as admin_users_router
from modules.identity.auth.route import router as auth_router
from modules.notification.device_tokens.route import router as device_tokens_router
from modules.notification.preferences.route import router as notification_preferences_router
from modules.notification.push.expo_provider import ExpoPushProvider
from modules.notification.push.repository import PushDeliveryRepository
from modules.notification.push.worker import PushDeliveryWorker, PushWorkerConfig
from modules.notification.readiness import (
    NotificationSchemaReadiness,
    check_notification_schema_readiness,
)
from modules.notification.reminders.scheduler import UpcomingClassReminderScheduler
from modules.notification.student_notifications.route import (
    router as student_notifications_router,
)
from modules.routes.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings

    if not settings.is_keycloak_configured:
        logger.warning(
            "Keycloak validation is not configured. Set KEYCLOAK_EXPECTED_ISSUER "
            "and KEYCLOAK_JWKS_URL; authenticated endpoints will return 503.",
        )

    app.state.db_pool = await create_database_pool(settings)
    app.state.redis_client = await create_redis_client(settings)
    app.state.push_provider = ExpoPushProvider(
        timeout_seconds=settings.expo_push_timeout_seconds,
        access_token=(
            settings.expo_access_token.get_secret_value()
            if settings.expo_access_token
            else None
        ),
    )
    push_worker_stop = asyncio.Event()
    push_worker_task: asyncio.Task[None] | None = None
    notification_readiness = NotificationSchemaReadiness(False, False)
    if settings.push_worker_enabled or settings.reminder_scheduler_enabled:
        try:
            notification_readiness = await check_notification_schema_readiness(
                app.state.db_pool,
            )
        except Exception as error:
            logger.error(
                "Notification background tasks not started: schema preflight failed",
                extra={"preflight_error_type": type(error).__name__},
            )

    if settings.push_worker_enabled and notification_readiness.push_worker_ready:
        app.state.push_worker = PushDeliveryWorker(
            repository=PushDeliveryRepository(app.state.db_pool),
            provider=app.state.push_provider,
            config=PushWorkerConfig(
                batch_size=settings.push_worker_batch_size,
                receipt_batch_size=settings.push_worker_receipt_batch_size,
                poll_interval_seconds=settings.push_worker_poll_interval_seconds,
                receipt_delay_seconds=settings.push_worker_receipt_delay_seconds,
                lease_timeout_seconds=settings.push_worker_lease_timeout_seconds,
                max_attempts=settings.push_worker_max_attempts,
                retry_base_seconds=settings.push_worker_retry_base_seconds,
                retry_max_seconds=settings.push_worker_retry_max_seconds,
            ),
        )
        push_worker_task = asyncio.create_task(
            app.state.push_worker.run(push_worker_stop),
            name="push-delivery-worker",
        )
    elif settings.push_worker_enabled:
        logger.error(
            "Push delivery worker not started: notification.delivery_attempts.next_attempt_at is missing",
        )
    reminder_stop = asyncio.Event()
    reminder_task: asyncio.Task[None] | None = None
    if (
        settings.reminder_scheduler_enabled
        and notification_readiness.reminder_scheduler_ready
    ):
        app.state.reminder_scheduler = UpcomingClassReminderScheduler(
            pool=app.state.db_pool,
            interval_seconds=settings.reminder_scheduler_interval_seconds,
            lead_minutes=settings.reminder_lead_minutes,
        )
        reminder_task = asyncio.create_task(
            app.state.reminder_scheduler.run(reminder_stop),
            name="upcoming-class-reminder-scheduler",
        )
    elif settings.reminder_scheduler_enabled:
        logger.error(
            "Reminder scheduler not started: upcoming-class idempotency index is missing",
        )
    # Deliberately no connection details here: the URI, user and password must
    # never reach the logs.
    logger.info(
        "Database pool ready (ssl_mode=%s, pool=%s-%s)",
        settings.db_ssl_mode,
        settings.db_pool_min_size,
        settings.db_pool_max_size,
    )

    try:
        yield
    finally:
        if reminder_task is not None:
            reminder_stop.set()
            try:
                await asyncio.wait_for(
                    reminder_task,
                    timeout=settings.push_worker_shutdown_timeout_seconds,
                )
            except TimeoutError:
                reminder_task.cancel()
                await asyncio.gather(reminder_task, return_exceptions=True)
                logger.warning("Reminder scheduler cancelled during shutdown")
        if push_worker_task is not None:
            push_worker_stop.set()
            try:
                await asyncio.wait_for(
                    push_worker_task,
                    timeout=settings.push_worker_shutdown_timeout_seconds,
                )
            except TimeoutError:
                push_worker_task.cancel()
                await asyncio.gather(push_worker_task, return_exceptions=True)
                logger.warning("Push delivery worker cancelled during shutdown")
        await close_redis_client(app.state.redis_client)
        await close_database_pool(app.state.db_pool)


def create_app(*, enable_database: bool = True) -> FastAPI:
    # The interactive docs and schema describe every route to anyone who can
    # reach the API host, so they are only served outside production.
    docs_enabled = get_settings().app_environment.strip().lower() != "production"
    app = FastAPI(
        title="UniAttend Core API",
        lifespan=lifespan if enable_database else None,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(student_profile_router, prefix="/api/v1")
    app.include_router(student_courses_router, prefix="/api/v1")
    app.include_router(student_notifications_router, prefix="/api/v1")
    app.include_router(device_tokens_router, prefix="/api/v1")
    app.include_router(notification_preferences_router, prefix="/api/v1")
    app.include_router(active_session_router, prefix="/api/v1")
    app.include_router(qr_session_router, prefix="/api/v1")
    app.include_router(geofence_router, prefix="/api/v1")
    app.include_router(face_router, prefix="/api/v1")
    app.include_router(check_in_router, prefix="/api/v1")
    app.include_router(lecturer_courses_router, prefix="/api/v1")
    app.include_router(lecturer_correction_requests_router, prefix="/api/v1")
    app.include_router(lecturer_sessions_router, prefix="/api/v1")
    app.include_router(manual_review_router, prefix="/api/v1")
    app.include_router(lecturer_reports_router, prefix="/api/v1")
    app.include_router(admin_classrooms_router, prefix="/api/v1")
    app.include_router(admin_users_router, prefix="/api/v1")
    app.include_router(admin_academic_data_router, prefix="/api/v1")
    app.include_router(admin_reference_faces_router, prefix="/api/v1")
    app.include_router(attendance_policy_router, prefix="/api/v1")
    app.include_router(admin_audit_log_router, prefix="/api/v1")
    app.include_router(admin_dashboard_router, prefix="/api/v1")
    app.include_router(admin_institution_reports_router, prefix="/api/v1")
    return app


app = create_app()
