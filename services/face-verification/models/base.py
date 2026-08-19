from sqlalchemy import Column, DateTime, String, Table
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase

# Shared declarative base for face-verification ORM models.
class Base(DeclarativeBase):

    pass


# External tables referenced by foreign keys
Table(
    "student_profiles",
    Base.metadata,
    Column("id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    schema="academic",
)

Table(
    "users",
    Base.metadata,
    Column("id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    schema="identity",
)

verification_attempts_table = Table(
    "verification_attempts",
    Base.metadata,
    Column("id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    # Read-only additions beyond the FK anchor — core-backend owns writes to
    # this table; face-verification only needs to look up an in-progress
    # attempt for the student currently completing the check-in wizard.
    Column("session_id", PostgreSQLUUID(as_uuid=True)),
    Column("student_id", PostgreSQLUUID(as_uuid=True)),
    Column("status", String(20)),
    Column("started_at", DateTime(timezone=True)),
    schema="attendance_verification",
)
