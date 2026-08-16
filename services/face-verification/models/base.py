from sqlalchemy import Column, Table
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

Table(
    "verification_attempts",
    Base.metadata,
    Column("id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    schema="attendance_verification",
)
