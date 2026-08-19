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
from modules.attendance_verification.completion.route import (
    router as completion_router,
)
from modules.attendance_verification.geofence.route import router as geofence_router
from modules.attendance_verification.manual_review.route import (
    router as manual_review_router,
)
from modules.audit.admin_log.route import router as admin_audit_log_router
from modules.identity.admin_users.route import router as admin_users_router
from modules.identity.auth.route import router as auth_router
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
        await close_redis_client(app.state.redis_client)
        await close_database_pool(app.state.db_pool)


def create_app(*, enable_database: bool = True) -> FastAPI:
    app = FastAPI(
        title="UniAttend Core API",
        lifespan=lifespan if enable_database else None,
    )
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(student_profile_router, prefix="/api/v1")
    app.include_router(student_courses_router, prefix="/api/v1")
    app.include_router(student_notifications_router, prefix="/api/v1")
    app.include_router(active_session_router, prefix="/api/v1")
    app.include_router(qr_session_router, prefix="/api/v1")
    app.include_router(geofence_router, prefix="/api/v1")
    app.include_router(completion_router, prefix="/api/v1")
    app.include_router(lecturer_courses_router, prefix="/api/v1")
    app.include_router(lecturer_sessions_router, prefix="/api/v1")
    app.include_router(manual_review_router, prefix="/api/v1")
    app.include_router(lecturer_reports_router, prefix="/api/v1")
    app.include_router(admin_classrooms_router, prefix="/api/v1")
    app.include_router(admin_users_router, prefix="/api/v1")
    app.include_router(admin_academic_data_router, prefix="/api/v1")
    app.include_router(admin_reference_faces_router, prefix="/api/v1")
    app.include_router(admin_audit_log_router, prefix="/api/v1")
    app.include_router(admin_dashboard_router, prefix="/api/v1")
    app.include_router(admin_institution_reports_router, prefix="/api/v1")
    return app


app = create_app()
