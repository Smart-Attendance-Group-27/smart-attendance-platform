from pydantic import BaseModel, ConfigDict, Field


class ReferenceFaceEnrollmentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    discovered: int
    enrolled: int
    already_enrolled: int = Field(alias="alreadyEnrolled")
    skipped: int
    failed: int

