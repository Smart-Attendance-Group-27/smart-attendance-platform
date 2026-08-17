from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.academic.admin_classrooms.exception import (
    BuildingNotFoundError,
    ClassroomNotFoundError,
)
from modules.academic.admin_classrooms.schemas import (
    BuildingResponse,
    ClassroomResponse,
    ClassroomWriteRequest,
)
from modules.academic.admin_classrooms.service import AdminClassroomService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-classrooms"])

_CLASSROOM_NOT_FOUND_DETAIL = "The classroom was not found."
_BUILDING_NOT_FOUND_DETAIL = "The referenced building was not found."


def get_admin_classroom_service() -> AdminClassroomService:
    return AdminClassroomService()


@router.get("/buildings", response_model=list[BuildingResponse], status_code=status.HTTP_200_OK)
async def list_buildings(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    classroom_service: Annotated[
        AdminClassroomService,
        Depends(get_admin_classroom_service),
    ] = None,  # type: ignore[assignment]
) -> list[BuildingResponse]:
    buildings = await classroom_service.list_buildings(http_request.app.state.db_pool)
    return [BuildingResponse.from_record(building) for building in buildings]


@router.get("/classrooms", response_model=list[ClassroomResponse], status_code=status.HTTP_200_OK)
async def list_classrooms(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    classroom_service: Annotated[
        AdminClassroomService,
        Depends(get_admin_classroom_service),
    ] = None,  # type: ignore[assignment]
) -> list[ClassroomResponse]:
    classrooms = await classroom_service.list_classrooms(http_request.app.state.db_pool)
    return [ClassroomResponse.from_record(classroom) for classroom in classrooms]


@router.get(
    "/classrooms/{classroom_id}",
    response_model=ClassroomResponse,
    status_code=status.HTTP_200_OK,
)
async def get_classroom(
    classroom_id: UUID,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    classroom_service: Annotated[
        AdminClassroomService,
        Depends(get_admin_classroom_service),
    ] = None,  # type: ignore[assignment]
) -> ClassroomResponse:
    try:
        classroom = await classroom_service.get_classroom(
            http_request.app.state.db_pool,
            classroom_id,
        )
    except ClassroomNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _CLASSROOM_NOT_FOUND_DETAIL) from error

    return ClassroomResponse.from_record(classroom)


@router.post(
    "/classrooms",
    response_model=ClassroomResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_classroom(
    body: ClassroomWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    classroom_service: Annotated[
        AdminClassroomService,
        Depends(get_admin_classroom_service),
    ] = None,  # type: ignore[assignment]
) -> ClassroomResponse:
    try:
        classroom = await classroom_service.create_classroom(
            http_request.app.state.db_pool,
            current_administrator.user_id,
            building_id=body.building_id,
            classroom_code=body.classroom_code,
            floor_number=body.floor_number,
            capacity=body.capacity,
            latitude=body.latitude,
            longitude=body.longitude,
            default_geofence_radius_m=body.default_geofence_radius_m,
            status=body.status,
        )
    except BuildingNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _BUILDING_NOT_FOUND_DETAIL) from error

    return ClassroomResponse.from_record(classroom)


@router.put(
    "/classrooms/{classroom_id}",
    response_model=ClassroomResponse,
    status_code=status.HTTP_200_OK,
)
async def update_classroom(
    classroom_id: UUID,
    body: ClassroomWriteRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    classroom_service: Annotated[
        AdminClassroomService,
        Depends(get_admin_classroom_service),
    ] = None,  # type: ignore[assignment]
) -> ClassroomResponse:
    try:
        classroom = await classroom_service.update_classroom(
            http_request.app.state.db_pool,
            current_administrator.user_id,
            classroom_id,
            building_id=body.building_id,
            classroom_code=body.classroom_code,
            floor_number=body.floor_number,
            capacity=body.capacity,
            latitude=body.latitude,
            longitude=body.longitude,
            default_geofence_radius_m=body.default_geofence_radius_m,
            status=body.status,
        )
    except ClassroomNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _CLASSROOM_NOT_FOUND_DETAIL) from error
    except BuildingNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _BUILDING_NOT_FOUND_DETAIL) from error

    return ClassroomResponse.from_record(classroom)
