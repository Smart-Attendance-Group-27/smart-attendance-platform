from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.lecturer_courses.schemas import (
    LecturerCourseResponse,
    LecturerTimetableEntryResponse,
)
from modules.academic.lecturer_courses.service import LecturerCourseService
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.identity.auth.dependencies import CurrentLecturer

router = APIRouter(prefix="/lecturers", tags=["lecturer-courses"])


def get_lecturer_course_service() -> LecturerCourseService:
    return LecturerCourseService()


@router.get(
    "/me/courses",
    response_model=list[LecturerCourseResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_courses(
    http_request: Request,
    current_lecturer: CurrentLecturer,
    course_service: Annotated[
        LecturerCourseService,
        Depends(get_lecturer_course_service),
    ] = None,  # type: ignore[assignment]
) -> list[LecturerCourseResponse]:
    # The lecturer is taken from the verified token only — there is no
    # {lecturerId} path parameter, so one lecturer cannot browse another
    # lecturer's course list by substituting an id.
    try:
        courses = await course_service.list_courses_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An active lecturer profile was not found for this account.",
        ) from error

    return [
        LecturerCourseResponse(
            course_offering_id=course.course_offering_id,
            course_code=course.course_code or "",
            course_name=course.course_name or "",
            department_name=course.department_name,
            course_type=course.course_type,
            status=course.status or "",
            enrolled_count=course.enrolled_count,
            attendance_rate_percent=(
                float(course.attendance_rate_percent)
                if course.attendance_rate_percent is not None
                else None
            ),
        )
        for course in courses
    ]


@router.get(
    "/me/timetable",
    response_model=list[LecturerTimetableEntryResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_timetable(
    http_request: Request,
    current_lecturer: CurrentLecturer,
    course_service: Annotated[
        LecturerCourseService,
        Depends(get_lecturer_course_service),
    ] = None,  # type: ignore[assignment]
) -> list[LecturerTimetableEntryResponse]:
    try:
        entries = await course_service.list_timetable_for_user(
            http_request.app.state.db_pool,
            current_lecturer.user_id,
        )
    except LecturerProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An active lecturer profile was not found for this account.",
        ) from error

    return [
        LecturerTimetableEntryResponse(
            id=entry.id,
            course_code=entry.course_code or "",
            course_name=entry.course_name or "",
            day_of_week=entry.day_of_week,
            start_time=entry.start_time,
            end_time=entry.end_time,
            classroom_code=entry.classroom_code,
            building_name=entry.building_name,
        )
        for entry in entries
    ]
