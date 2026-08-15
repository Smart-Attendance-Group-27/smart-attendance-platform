from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudentProfileResponse(BaseModel):
    """Mirrors the mobile `StudentProfile` model.

    Only identity fields the student already knows about are exposed. Account
    status, password data, token data, department IDs and Keycloak fields are
    all deliberately left out.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    registration_number: str = Field(alias="registrationNumber")
    full_name: str = Field(alias="fullName")
    university_email: str = Field(alias="universityEmail")
