import argparse
import asyncio
import json
import time
from collections import Counter
from contextvars import ContextVar
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import Header
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine

from api.dependencies.auth import get_current_student_id
from core.config import Settings, get_settings
from core.embedding_crypto import EmbeddingCrypto
from db.engine import _build_database_url, create_database_engine, dispose_database_engine
from db.session import create_session_factory
from main import create_app
from services.face_engine import FaceAnalysisStatus
from adapters.insightface_engine import create_configured_insightface_engine


LOCAL_DATABASE_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
)
REQUEST_CHECKOUT_STARTED: ContextVar[float | None] = ContextVar(
    "request_checkout_started",
    default=None,
)


@dataclass(frozen=True, slots=True)
class SeededBurst:
    operator_id: UUID
    session_id: UUID
    student_ids: tuple[UUID, ...]
    user_ids: tuple[UUID, ...]
    verification_attempt_ids: tuple[UUID, ...]
    face_profile_ids: tuple[UUID, ...]
    created_config_id: UUID | None


@dataclass(slots=True)
class PoolMetrics:
    checkout_count: int = 0
    checked_out: int = 0
    max_checked_out: int = 0
    checkout_wait_ms: list[float] | None = None

    def __post_init__(self) -> None:
        self.checkout_wait_ms = []

    def checkout(self, *_args: object) -> None:
        self.checkout_count += 1
        self.checked_out += 1
        self.max_checked_out = max(self.max_checked_out, self.checked_out)
        checkout_started = REQUEST_CHECKOUT_STARTED.get()
        if checkout_started is not None:
            assert self.checkout_wait_ms is not None
            self.checkout_wait_ms.append(
                (time.perf_counter() - checkout_started) * 1000
            )
            REQUEST_CHECKOUT_STARTED.set(None)

    def checkin(self, *_args: object) -> None:
        self.checked_out = max(self.checked_out - 1, 0)


def require_local_database(settings: Settings) -> str:
    host = (_build_database_url(settings).host or "").casefold()
    if host not in LOCAL_DATABASE_HOSTS:
        raise ValueError(
            "Burst verification is restricted to a local PostgreSQL host"
        )
    return host


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def attempt_numbers_are_contiguous(numbers: list[int]) -> bool:
    return numbers == list(range(1, len(numbers) + 1))


async def seed_burst(
    engine: AsyncEngine,
    settings: Settings,
    *,
    requests: int,
    reference_image: bytes,
    face_engine,
) -> SeededBurst:
    analysis = await face_engine.analyze(reference_image)
    if (
        analysis.status is not FaceAnalysisStatus.SUCCESS
        or analysis.embedding is None
        or analysis.model_name is None
    ):
        raise RuntimeError(
            f"Reference image analysis failed: {analysis.status.value}"
        )

    operator_id = uuid4()
    session_id = uuid4()
    user_ids = tuple(uuid4() for _ in range(requests))
    student_ids = tuple(uuid4() for _ in range(requests))
    attempt_ids = tuple(uuid4() for _ in range(requests))
    profile_ids = tuple(uuid4() for _ in range(requests))
    created_config_id: UUID | None = None
    now = datetime.now(UTC)
    encrypted_embedding = EmbeddingCrypto(
        settings.face_embedding_encryption_key.get_secret_value()
    ).encrypt(analysis.embedding)

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO identity.users (
                    id, email, account_status, failed_login_attempts,
                    must_change_password, created_at, updated_at
                ) VALUES (
                    :id, :email, 'active', 0, false, :now, :now
                )
                """
            ),
            [
                {
                    "id": user_id,
                    "email": f"burst-{user_id}@local.invalid",
                    "now": now,
                }
                for user_id in (operator_id, *user_ids)
            ],
        )
        await connection.execute(
            text(
                """
                INSERT INTO academic.student_profiles (
                    id, user_id, registration_number, first_name, last_name,
                    profile_status, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :registration_number, 'Burst', 'Student',
                    'active', :now, :now
                )
                """
            ),
            [
                {
                    "id": student_id,
                    "user_id": user_id,
                    "registration_number": f"BURST-{index}-{student_id.hex[:8]}",
                    "now": now,
                }
                for index, (student_id, user_id) in enumerate(
                    zip(student_ids, user_ids, strict=True),
                    start=1,
                )
            ],
        )
        await connection.execute(
            text(
                """
                INSERT INTO attendance_session.sessions (
                    id, created_by, session_title, session_type,
                    scheduled_start_at, scheduled_end_at,
                    check_in_opens_at, check_in_closes_at, late_after_at,
                    status, requires_face_verification, requires_geofence,
                    requires_qr, activated_at, created_at, updated_at
                ) VALUES (
                    :id, :created_by, 'Local burst verification', 'lecture',
                    :scheduled_start, :scheduled_end,
                    :check_in_opens, :check_in_closes, :late_after,
                    'active', true, false, false, :now, :now, :now
                )
                """
            ),
            {
                "id": session_id,
                "created_by": operator_id,
                "scheduled_start": now - timedelta(minutes=5),
                "scheduled_end": now + timedelta(hours=1),
                "check_in_opens": now - timedelta(minutes=5),
                "check_in_closes": now + timedelta(hours=1),
                "late_after": now + timedelta(minutes=10),
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO attendance_verification.verification_attempts (
                    id, session_id, student_id, status, started_at
                ) VALUES (
                    :id, :session_id, :student_id, 'in_progress', :now
                )
                """
            ),
            [
                {
                    "id": attempt_id,
                    "session_id": session_id,
                    "student_id": student_id,
                    "now": now,
                }
                for attempt_id, student_id in zip(
                    attempt_ids, student_ids, strict=True
                )
            ],
        )
        await connection.execute(
            text(
                """
                INSERT INTO face_verification.face_profiles (
                    id, student_id, embedding_encrypted,
                    embedding_model_name, embedding_model_version,
                    embedding_dimension, embedding_generation_status,
                    generated_at, readiness_status, created_at, updated_at
                ) VALUES (
                    :id, :student_id, :embedding_encrypted,
                    :model_name, :model_version, :dimension, 'generated',
                    :now, 'not_checked', :now, :now
                )
                """
            ),
            [
                {
                    "id": profile_id,
                    "student_id": student_id,
                    "embedding_encrypted": encrypted_embedding,
                    "model_name": analysis.model_name,
                    "model_version": settings.face_model_version,
                    "dimension": len(analysis.embedding),
                    "now": now,
                }
                for profile_id, student_id in zip(
                    profile_ids, student_ids, strict=True
                )
            ],
        )
        active_config = await connection.scalar(
            text(
                """
                SELECT id FROM face_verification.verification_configs
                WHERE is_active IS TRUE LIMIT 1
                """
            )
        )
        if active_config is None:
            created_config_id = uuid4()
            await connection.execute(
                text(
                    """
                    INSERT INTO face_verification.verification_configs (
                        id, similarity_threshold, is_active, configured_by,
                        effective_from, created_at
                    ) VALUES (:id, 0.5, true, :configured_by, :now, :now)
                    """
                ),
                {
                    "id": created_config_id,
                    "configured_by": operator_id,
                    "now": now,
                },
            )

    return SeededBurst(
        operator_id=operator_id,
        session_id=session_id,
        student_ids=student_ids,
        user_ids=user_ids,
        verification_attempt_ids=attempt_ids,
        face_profile_ids=profile_ids,
        created_config_id=created_config_id,
    )


async def cleanup_burst(engine: AsyncEngine, seeded: SeededBurst) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "DELETE FROM face_verification.face_validation_attempts "
                "WHERE verification_attempt_id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": list(seeded.verification_attempt_ids)},
        )
        await connection.execute(
            text("DELETE FROM face_verification.face_profiles WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": list(seeded.face_profile_ids)},
        )
        await connection.execute(
            text(
                "DELETE FROM attendance_verification.verification_attempts "
                "WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": list(seeded.verification_attempt_ids)},
        )
        await connection.execute(
            text("DELETE FROM attendance_session.sessions WHERE id = :id"),
            {"id": seeded.session_id},
        )
        await connection.execute(
            text("DELETE FROM academic.student_profiles WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": list(seeded.student_ids)},
        )
        if seeded.created_config_id is not None:
            await connection.execute(
                text(
                    "DELETE FROM face_verification.verification_configs "
                    "WHERE id = :id"
                ),
                {"id": seeded.created_config_id},
            )
        await connection.execute(
            text("DELETE FROM identity.users WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": [seeded.operator_id, *seeded.user_ids]},
        )


def liveness_payload() -> str:
    completed_at = datetime.now(UTC)
    return json.dumps(
        {
            "version": 1,
            "method": "mlkit_challenge",
            "passed": True,
            "challenges": ["turn_left", "eyes_closed_hold"],
            "startedAt": (completed_at - timedelta(seconds=5)).isoformat(),
            "completedAt": completed_at.isoformat(),
            "engine": "local-burst-harness",
        },
        separators=(",", ":"),
    )


async def run_burst(
    *,
    settings: Settings,
    requests: int,
    reference_image: bytes,
    capture_image: bytes,
) -> dict[str, object]:
    require_local_database(settings)
    engine = create_database_engine(settings)
    face_engine = create_configured_insightface_engine(settings)
    seeded: SeededBurst | None = None
    pool_metrics = PoolMetrics()
    event.listen(engine.sync_engine, "checkout", pool_metrics.checkout)
    event.listen(engine.sync_engine, "checkin", pool_metrics.checkin)

    try:
        seeded = await seed_burst(
            engine,
            settings,
            requests=requests,
            reference_image=reference_image,
            face_engine=face_engine,
        )
        app = create_app(enable_database=False)
        app.state.settings = settings
        app.state.db_session_factory = create_session_factory(engine)
        app.state.face_engine = face_engine

        async def burst_student(
            x_burst_student_id: Annotated[UUID, Header()],
        ) -> UUID:
            return x_burst_student_id

        app.dependency_overrides[get_current_student_id] = burst_student
        transport = httpx.ASGITransport(app=app)
        latencies: list[float] = []

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://local-burst",
        ) as client:
            async def submit(student_id: UUID) -> tuple[int, str]:
                started = time.perf_counter()
                checkout_token = REQUEST_CHECKOUT_STARTED.set(started)
                try:
                    response = await client.post(
                        f"/internal/v1/attendance-sessions/{seeded.session_id}/face-verifications",
                        headers={"X-Burst-Student-Id": str(student_id)},
                        files={"image": ("capture.jpg", capture_image, "image/jpeg")},
                        data={"liveness": liveness_payload()},
                    )
                finally:
                    REQUEST_CHECKOUT_STARTED.reset(checkout_token)
                latencies.append((time.perf_counter() - started) * 1000)
                status_value = "invalid-json"
                with suppress(ValueError):
                    status_value = str(response.json().get("status", "unknown"))
                return response.status_code, status_value

            outcomes = await asyncio.gather(
                *(submit(student_id) for student_id in seeded.student_ids)
            )

        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT verification_attempt_id,
                               array_agg(attempt_number ORDER BY attempt_number) AS numbers
                        FROM face_verification.face_validation_attempts
                        WHERE verification_attempt_id = ANY(CAST(:ids AS uuid[]))
                        GROUP BY verification_attempt_id
                        """
                    ),
                    {"ids": list(seeded.verification_attempt_ids)},
                )
            ).mappings().all()

        attempt_integrity = all(
            attempt_numbers_are_contiguous(list(row["numbers"])) for row in rows
        ) and len(rows) == requests
        return {
            "requests": requests,
            "statuses": dict(Counter(f"{code}:{status}" for code, status in outcomes)),
            "latency_ms": {
                "p50": round(percentile(latencies, 0.50), 2),
                "p95": round(percentile(latencies, 0.95), 2),
                "p99": round(percentile(latencies, 0.99), 2),
                "max": round(max(latencies, default=0), 2),
            },
            "pool": {
                "checkouts": pool_metrics.checkout_count,
                "max_checked_out": pool_metrics.max_checked_out,
                "configured_size": settings.db_pool_max_size,
                "checkout_wait_p95_ms": round(
                    percentile(pool_metrics.checkout_wait_ms or [], 0.95), 2
                ),
                "checkout_wait_max_ms": round(
                    max(pool_metrics.checkout_wait_ms or [0]), 2
                ),
                "checkout_waits_over_5ms": sum(
                    wait > 5 for wait in (pool_metrics.checkout_wait_ms or [])
                ),
            },
            "attempt_number_integrity": attempt_integrity,
        }
    finally:
        if seeded is not None:
            await cleanup_burst(engine, seeded)
        await dispose_database_engine(engine)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run concurrent face verification against local PostgreSQL only."
    )
    parser.add_argument("reference_image", type=Path)
    parser.add_argument("capture_image", type=Path)
    parser.add_argument("--requests", type=int, default=30)
    return parser


def main() -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args()
    if arguments.requests < 1:
        parser.error("--requests must be at least one")

    try:
        result = asyncio.run(
            run_burst(
                settings=get_settings(),
                requests=arguments.requests,
                reference_image=arguments.reference_image.read_bytes(),
                capture_image=arguments.capture_image.read_bytes(),
            )
        )
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Burst verification failed: {error}\n")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["attempt_number_integrity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
