import inspect
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.contracts.notifications import NotificationProducer as NotificationProducerProtocol
from modules.notification.producer.repository import NotificationProducerRepository
from modules.notification.producer.service import NotificationProducer


class FakeConnection:
    """Mock asyncpg connection recording executed queries."""

    def __init__(self) -> None:
        self.fetch = AsyncMock(return_value=[])
        self.fetchrow = AsyncMock(return_value=None)
        self.execute = AsyncMock(return_value=None)
        self.executemany = AsyncMock(return_value=None)


def test_notification_producer_conforms_to_protocol():
    producer = NotificationProducer()
    assert isinstance(producer, NotificationProducerProtocol)


def test_notification_producer_method_signatures():
    parameters = list(inspect.signature(NotificationProducer.notify_users).parameters)
    assert parameters == [
        "self",
        "connection",
        "recipient_user_ids",
        "type_code",
        "title",
        "body",
        "related_entity_type",
        "related_entity_id",
        "priority",
    ]


@pytest.mark.asyncio
async def test_notify_users_empty_recipients():
    producer = NotificationProducer()
    conn = FakeConnection()
    result = await producer.notify_users(
        conn,
        recipient_user_ids=[],
        type_code="GENERAL",
        title="Hello",
        body="World",
    )
    assert result == []
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_notify_users_deduplicates_recipients_and_queries_preferences():
    repo = MagicMock(spec=NotificationProducerRepository)
    user_id = uuid4()
    repo.fetch_user_preferences = AsyncMock(return_value={user_id: (True, True)})
    token_id = uuid4()
    repo.fetch_active_device_tokens = AsyncMock(return_value={user_id: [token_id]})
    repo.insert_notifications_and_attempts = AsyncMock()

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    # Pass duplicate user IDs
    created_ids = await producer.notify_users(
        conn,
        recipient_user_ids=[user_id, user_id],
        type_code="TEST_TYPE",
        title="Test Title",
        body="Test Body",
        priority="high",
    )

    assert len(created_ids) == 1
    repo.fetch_user_preferences.assert_awaited_once_with(conn, [user_id], "TEST_TYPE")
    repo.fetch_active_device_tokens.assert_awaited_once_with(conn, [user_id])
    repo.insert_notifications_and_attempts.assert_awaited_once()

    notifications, attempts = repo.insert_notifications_and_attempts.call_args[0][1:3]
    assert len(notifications) == 1
    assert notifications[0][0] == created_ids[0]
    assert notifications[0][1] == user_id
    assert notifications[0][2] == "TEST_TYPE"
    assert notifications[0][3] == "Test Title"
    assert notifications[0][4] == "Test Body"
    assert notifications[0][5] == "high"
    assert notifications[0][8] is True  # in_app_visible

    assert len(attempts) == 1
    assert attempts[0][1] == created_ids[0]
    assert attempts[0][2] == token_id


@pytest.mark.asyncio
async def test_notify_users_skips_users_with_all_channels_disabled():
    repo = MagicMock(spec=NotificationProducerRepository)
    user_enabled = uuid4()
    user_disabled = uuid4()
    repo.fetch_user_preferences = AsyncMock(
        return_value={
            user_enabled: (True, False),
            user_disabled: (False, False),
        }
    )
    repo.fetch_active_device_tokens = AsyncMock(return_value={})
    repo.insert_notifications_and_attempts = AsyncMock()

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    created_ids = await producer.notify_users(
        conn,
        recipient_user_ids=[user_enabled, user_disabled],
        type_code="TEST_TYPE",
        title="Test Title",
        body="Test Body",
    )

    assert len(created_ids) == 1
    notifications, attempts = repo.insert_notifications_and_attempts.call_args[0][1:3]
    assert len(notifications) == 1
    assert notifications[0][1] == user_enabled
    assert notifications[0][8] is True  # in_app_visible
    assert len(attempts) == 0


@pytest.mark.asyncio
async def test_session_opened_notifies_enrolled_students():
    repo = MagicMock(spec=NotificationProducerRepository)
    session_id = uuid4()
    student_1 = uuid4()
    student_2 = uuid4()

    repo.fetch_session_course_info = AsyncMock(return_value=("Distributed Systems", "CS401"))
    repo.fetch_enrolled_student_user_ids = AsyncMock(return_value=[student_1, student_2])
    repo.fetch_user_preferences = AsyncMock(
        return_value={
            student_1: (True, True),
            student_2: (True, False),
        }
    )
    repo.fetch_active_device_tokens = AsyncMock(return_value={student_1: [uuid4()]})
    repo.insert_notifications_and_attempts = AsyncMock()

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    created_ids = await producer.session_opened(conn, session_id=session_id)

    assert len(created_ids) == 2
    repo.fetch_session_course_info.assert_awaited_once_with(conn, session_id)
    repo.fetch_enrolled_student_user_ids.assert_awaited_once_with(conn, session_id)

    notifications = repo.insert_notifications_and_attempts.call_args[0][1]
    assert notifications[0][2] == "ATTENDANCE_SESSION_OPENED"
    assert "Distributed Systems" in notifications[0][4]
    assert notifications[0][6] == "ATTENDANCE_SESSION"
    assert notifications[0][7] == session_id


@pytest.mark.asyncio
async def test_session_opened_returns_empty_when_no_enrolled_students():
    repo = MagicMock(spec=NotificationProducerRepository)
    session_id = uuid4()
    repo.fetch_session_course_info = AsyncMock(return_value=("Algorithms", "CS301"))
    repo.fetch_enrolled_student_user_ids = AsyncMock(return_value=[])

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    result = await producer.session_opened(conn, session_id=session_id)
    assert result == []


@pytest.mark.asyncio
async def test_qr_batch_activated_notifies_recipients():
    repo = MagicMock(spec=NotificationProducerRepository)
    session_id = uuid4()
    batch_id = uuid4()
    student_id = uuid4()

    repo.fetch_session_course_info = AsyncMock(return_value=("Networks", "CS302"))
    repo.fetch_user_preferences = AsyncMock(return_value={student_id: (True, True)})
    repo.fetch_active_device_tokens = AsyncMock(return_value={})
    repo.insert_notifications_and_attempts = AsyncMock()

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    result = await producer.qr_batch_activated(
        conn,
        session_id=session_id,
        qr_batch_id=batch_id,
        recipient_user_ids=[student_id],
    )

    assert len(result) == 1
    notifications = repo.insert_notifications_and_attempts.call_args[0][1]
    assert notifications[0][2] == "QR_SESSION_ACTIVE"
    assert "Networks" in notifications[0][4]


@pytest.mark.asyncio
async def test_qr_batch_activated_empty_recipients():
    producer = NotificationProducer()
    conn = FakeConnection()
    result = await producer.qr_batch_activated(
        conn,
        session_id=uuid4(),
        qr_batch_id=uuid4(),
        recipient_user_ids=[],
    )
    assert result == []


@pytest.mark.asyncio
async def test_attendance_finalized_notifies_each_student():
    repo = MagicMock(spec=NotificationProducerRepository)
    session_id = uuid4()
    student_1 = uuid4()
    student_2 = uuid4()

    repo.fetch_session_course_info = AsyncMock(return_value=("Databases", "CS201"))
    repo.fetch_user_preferences = AsyncMock(
        return_value={
            student_1: (True, True),
            student_2: (True, True),
        }
    )
    repo.fetch_active_device_tokens = AsyncMock(return_value={})
    repo.insert_notifications_and_attempts = AsyncMock()

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    result = await producer.attendance_finalized(
        conn,
        session_id=session_id,
        results=[
            (student_1, FinalAttendanceStatus.PRESENT),
            (student_2, FinalAttendanceStatus.ABSENT),
        ],
    )

    assert len(result) == 2
    assert repo.insert_notifications_and_attempts.call_count == 2


@pytest.mark.asyncio
async def test_attendance_finalized_empty_results():
    producer = NotificationProducer()
    conn = FakeConnection()
    result = await producer.attendance_finalized(conn, session_id=uuid4(), results=[])
    assert result == []


@pytest.mark.asyncio
async def test_attendance_changed_notifies_student():
    repo = MagicMock(spec=NotificationProducerRepository)
    session_id = uuid4()
    student_id = uuid4()

    repo.fetch_session_course_info = AsyncMock(return_value=("Databases", "CS201"))
    repo.fetch_user_preferences = AsyncMock(return_value={student_id: (True, True)})
    repo.fetch_active_device_tokens = AsyncMock(return_value={})
    repo.insert_notifications_and_attempts = AsyncMock()

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    result = await producer.attendance_changed(
        conn,
        session_id=session_id,
        student_user_id=student_id,
        status=FinalAttendanceStatus.LATE,
    )

    assert len(result) == 1
    notifications = repo.insert_notifications_and_attempts.call_args[0][1]
    assert notifications[0][2] == "ATTENDANCE_RESULT"
    assert "Late" in notifications[0][4]


@pytest.mark.asyncio
async def test_session_cancelled_notifies_enrolled():
    repo = MagicMock(spec=NotificationProducerRepository)
    session_id = uuid4()
    student_id = uuid4()

    repo.fetch_session_course_info = AsyncMock(return_value=("Operating Systems", "CS304"))
    repo.fetch_enrolled_student_user_ids = AsyncMock(return_value=[student_id])
    repo.fetch_user_preferences = AsyncMock(return_value={student_id: (True, True)})
    repo.fetch_active_device_tokens = AsyncMock(return_value={})
    repo.insert_notifications_and_attempts = AsyncMock()

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    result = await producer.session_cancelled(conn, session_id=session_id)

    assert len(result) == 1
    notifications = repo.insert_notifications_and_attempts.call_args[0][1]
    assert notifications[0][2] == "ATTENDANCE_SESSION_CANCELLED"
    assert "Operating Systems" in notifications[0][4]


@pytest.mark.asyncio
async def test_session_cancelled_empty_when_no_students():
    repo = MagicMock(spec=NotificationProducerRepository)
    session_id = uuid4()
    repo.fetch_session_course_info = AsyncMock(return_value=("Operating Systems", "CS304"))
    repo.fetch_enrolled_student_user_ids = AsyncMock(return_value=[])

    producer = NotificationProducer(repository=repo)
    conn = FakeConnection()

    result = await producer.session_cancelled(conn, session_id=session_id)
    assert result == []


@pytest.mark.asyncio
async def test_repository_fetch_user_preferences():
    repo = NotificationProducerRepository()
    conn = FakeConnection()
    u1 = uuid4()
    u2 = uuid4()
    conn.fetch.return_value = [
        {"user_id": u1, "type_is_active": True, "in_app_enabled": True, "push_enabled": False},
        {"user_id": u2, "type_is_active": False, "in_app_enabled": True, "push_enabled": True},
    ]

    prefs = await repo.fetch_user_preferences(conn, [u1, u2], "SOME_TYPE")
    assert prefs[u1] == (True, False)
    assert prefs[u2] == (False, False)  # Inactive type disables all channels


@pytest.mark.asyncio
async def test_repository_fetch_active_device_tokens_filters_android():
    repo = NotificationProducerRepository()
    conn = FakeConnection()
    u1 = uuid4()
    t1 = uuid4()
    conn.fetch.return_value = [{"id": t1, "user_id": u1}]

    tokens = await repo.fetch_active_device_tokens(conn, [u1])
    assert tokens == {u1: [t1]}
    executed_query = conn.fetch.call_args[0][0]
    assert "LOWER(platform) = 'android'" in executed_query
    assert "is_active IS TRUE" in executed_query
