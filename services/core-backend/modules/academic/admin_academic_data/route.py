from typing import Annotated, Awaitable, Callable, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.admin_academic_data.exception import (
    AcademicConflictError,
    AcademicEntityNotFoundError,
)
from modules.academic.admin_academic_data.schemas import (
    AcademicOptionResponse,
    AcademicReferenceDataResponse,
    AdminAcademicDataResponse,
    AdminCourseOfferingResponse,
    AdminCourseResponse,
    AdminEnrolmentResponse,
    AdminTimetableEntryResponse,
    CourseWriteRequest,
    EnrolmentWriteRequest,
    LecturerAssignmentRequest,
    OfferingWriteRequest,
    TimetableWriteRequest,
)
from modules.academic.admin_academic_data.service import AdminAcademicDataService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-academic-data"])
T = TypeVar("T")


def get_admin_academic_data_service() -> AdminAcademicDataService:
    return AdminAcademicDataService()


ServiceDependency = Annotated[
    AdminAcademicDataService,
    Depends(get_admin_academic_data_service),
]


async def _resolve(operation: Callable[[], Awaitable[T]]) -> T:
    try:
        return await operation()
    except AcademicEntityNotFoundError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"The referenced {error.entity} was not found.",
        ) from error
    except AcademicConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, error.detail) from error


@router.get("/academic-data", response_model=AdminAcademicDataResponse)
async def get_academic_data(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminAcademicDataResponse:
    data = await academic_data_service.get_academic_data(http_request.app.state.db_pool)
    return AdminAcademicDataResponse(
        source_connection_status=data.source_connection_status,
        courses=[AdminCourseResponse.from_record(item) for item in data.courses],
        offerings=[AdminCourseOfferingResponse.from_record(item) for item in data.offerings],
        timetable=[AdminTimetableEntryResponse.from_record(item) for item in data.timetable],
        enrolments=[AdminEnrolmentResponse.from_record(item) for item in data.enrolments],
    )


@router.get("/academic-options", response_model=AcademicReferenceDataResponse)
async def get_academic_options(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AcademicReferenceDataResponse:
    options = await academic_data_service.get_reference_options(http_request.app.state.db_pool)
    return AcademicReferenceDataResponse(**{
        key: [AcademicOptionResponse.from_record(item) for item in values]
        for key, values in options.items()
    })


@router.post("/courses", response_model=AdminCourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminCourseResponse:
    record = await _resolve(lambda: academic_data_service.create_course(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        course_code=body.course_code,
        course_name=body.course_name,
        department_id=body.department_id,
        credits=body.credits,
        status=body.status,
    ))
    return AdminCourseResponse.from_record(record)


@router.put("/courses/{course_id}", response_model=AdminCourseResponse)
async def update_course(
    course_id: UUID,
    body: CourseWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminCourseResponse:
    record = await _resolve(lambda: academic_data_service.update_course(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        course_id,
        course_code=body.course_code,
        course_name=body.course_name,
        department_id=body.department_id,
        credits=body.credits,
        status=body.status,
    ))
    return AdminCourseResponse.from_record(record)


@router.post("/offerings", response_model=AdminCourseOfferingResponse, status_code=status.HTTP_201_CREATED)
async def create_offering(
    body: OfferingWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminCourseOfferingResponse:
    record = await _resolve(lambda: academic_data_service.create_offering(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        course_id=body.course_id,
        semester_id=body.semester_id,
        lecturer_id=body.lecturer_id,
        batch_year=body.batch_year,
        course_type=body.course_type,
        attendance_threshold=body.attendance_threshold_percent,
        status=body.status,
    ))
    return AdminCourseOfferingResponse.from_record(record)


@router.put("/offerings/{offering_id}", response_model=AdminCourseOfferingResponse)
async def update_offering(
    offering_id: UUID,
    body: OfferingWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminCourseOfferingResponse:
    record = await _resolve(lambda: academic_data_service.update_offering(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        offering_id,
        course_id=body.course_id,
        semester_id=body.semester_id,
        lecturer_id=body.lecturer_id,
        batch_year=body.batch_year,
        course_type=body.course_type,
        attendance_threshold=body.attendance_threshold_percent,
        status=body.status,
    ))
    return AdminCourseOfferingResponse.from_record(record)


@router.put("/offerings/{offering_id}/lecturer", response_model=AdminCourseOfferingResponse)
async def assign_offering_lecturer(
    offering_id: UUID,
    body: LecturerAssignmentRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminCourseOfferingResponse:
    record = await _resolve(lambda: academic_data_service.assign_lecturer(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        offering_id,
        body.lecturer_id,
    ))
    return AdminCourseOfferingResponse.from_record(record)


@router.get("/offerings/{offering_id}/enrolments", response_model=list[AdminEnrolmentResponse])
async def list_offering_enrolments(
    offering_id: UUID,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> list[AdminEnrolmentResponse]:
    records = await _resolve(lambda: academic_data_service.list_offering_enrolments(
        http_request.app.state.db_pool, offering_id
    ))
    return [AdminEnrolmentResponse.from_record(record) for record in records]


@router.post("/offerings/{offering_id}/enrolments", response_model=AdminEnrolmentResponse, status_code=status.HTTP_201_CREATED)
async def enrol_student(
    offering_id: UUID,
    body: EnrolmentWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminEnrolmentResponse:
    record = await _resolve(lambda: academic_data_service.enrol_student(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        offering_id,
        body.student_id,
    ))
    return AdminEnrolmentResponse.from_record(record)


@router.delete("/offerings/{offering_id}/enrolments/{student_id}", response_model=AdminEnrolmentResponse)
async def drop_student(
    offering_id: UUID,
    student_id: UUID,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminEnrolmentResponse:
    record = await _resolve(lambda: academic_data_service.drop_student(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        offering_id,
        student_id,
    ))
    return AdminEnrolmentResponse.from_record(record)


def _timetable_values(body: TimetableWriteRequest) -> dict:
    return {
        "offering_id": body.course_offering_id,
        "classroom_id": body.classroom_id,
        "day_of_week": body.day_of_week,
        "start_time": body.start_time,
        "end_time": body.end_time,
        "course_type": body.course_type,
        "valid_from": body.valid_from,
        "valid_until": body.valid_until,
        "status": body.status,
    }


@router.post("/timetable-entries", response_model=AdminTimetableEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_timetable_entry(
    body: TimetableWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminTimetableEntryResponse:
    record = await _resolve(lambda: academic_data_service.create_timetable_entry(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        **_timetable_values(body),
    ))
    return AdminTimetableEntryResponse.from_record(record)


@router.put("/timetable-entries/{entry_id}", response_model=AdminTimetableEntryResponse)
async def update_timetable_entry(
    entry_id: UUID,
    body: TimetableWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminTimetableEntryResponse:
    record = await _resolve(lambda: academic_data_service.update_timetable_entry(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        entry_id,
        **_timetable_values(body),
    ))
    return AdminTimetableEntryResponse.from_record(record)


@router.delete("/timetable-entries/{entry_id}", response_model=AdminTimetableEntryResponse)
async def deactivate_timetable_entry(
    entry_id: UUID,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    academic_data_service: ServiceDependency = None,  # type: ignore[assignment]
) -> AdminTimetableEntryResponse:
    record = await _resolve(lambda: academic_data_service.deactivate_timetable_entry(
        http_request.app.state.db_pool,
        current_administrator.user_id,
        entry_id,
    ))
    return AdminTimetableEntryResponse.from_record(record)
