from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.schemas import StudentProfileResponse
from modules.academic.student_profile.service import StudentProfileService
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(prefix="/students", tags=["student-profile"])


def get_student_profile_service() -> StudentProfileService:
    return StudentProfileService()


@router.get(
    "/me/profile",
    response_model=StudentProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def read_my_student_profile(
    http_request: Request,
    current_student: CurrentStudent,
    student_profile_service: Annotated[
        StudentProfileService,
        Depends(get_student_profile_service),
    ] = None,  # type: ignore[assignment]
) -> StudentProfileResponse:
    # The student is taken from the verified token only. No user ID or student
    # ID is accepted from the request, so one student cannot read another's
    # profile by changing a parameter.
    try:
        student_profile = await student_profile_service.get_profile_for_user(
            http_request.app.state.db_pool,
            current_student.user_id,
        )
    except StudentProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A student profile was not found for this account.",
        ) from error

    return StudentProfileResponse(
        id=student_profile.id,
        registration_number=student_profile.registration_number,
        full_name=student_profile.full_name,
        university_email=student_profile.university_email,
    )
