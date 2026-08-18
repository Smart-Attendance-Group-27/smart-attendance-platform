from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.student_courses.schemas import (
    StudentCourseAttendanceRecordResponse,
    StudentCourseResponse,
    StudentCourseSessionResponse,
)
from modules.academic.student_courses.service import StudentCourseService
from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.identity.auth.dependencies import CurrentStudent

router = APIRouter(prefix="/students/me", tags=["student-courses"])


def get_student_course_service() -> StudentCourseService:
    return StudentCourseService()


@router.get(
    "/courses",
    response_model=list[StudentCourseResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_courses(
    http_request: Request,
    current_student: CurrentStudent,
    course_service: Annotated[
        StudentCourseService,
        Depends(get_student_course_service),
    ] = None,  # type: ignore[assignment]
) -> list[StudentCourseResponse]:
    try:
        courses = await course_service.list_courses_for_user(
            http_request.app.state.db_pool,
            current_student.user_id,
        )
    except StudentProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An active student profile was not found for this account.",
        ) from error

    return [
        StudentCourseResponse(
            id=course.id,
            code=course.code,
            title=course.title,
            lecturer=course.lecturer,
            semester=course.semester,
            attended_sessions=course.attended_sessions,
            total_sessions=course.total_sessions,
            attendance_percentage=course.attendance_percentage,
            sessions=[
                StudentCourseSessionResponse(
                    id=session.id,
                    title=session.title,
                    time_text=session.time_text,
                    type=session.type,
                    status=session.status,
                    recorded_time=session.recorded_time,
                    week_header=session.week_header,
                )
                for session in course.sessions
            ],
            attendance_records=[
                StudentCourseAttendanceRecordResponse(
                    id=record.id,
                    day=record.day,
                    month=record.month,
                    title=record.title,
                    recorded_text=record.recorded_text,
                    status=record.status,
                )
                for record in course.attendance_records
            ],
        )
        for course in courses
    ]
