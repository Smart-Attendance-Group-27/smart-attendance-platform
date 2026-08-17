from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from modules.academic.admin_reference_faces.schemas import ReferenceFaceResponse
from modules.academic.admin_reference_faces.service import AdminReferenceFaceService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-reference-faces"])


def get_admin_reference_face_service() -> AdminReferenceFaceService:
    return AdminReferenceFaceService()


@router.get(
    "/reference-faces",
    response_model=list[ReferenceFaceResponse],
    status_code=status.HTTP_200_OK,
)
async def list_reference_faces(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    reference_face_service: Annotated[
        AdminReferenceFaceService,
        Depends(get_admin_reference_face_service),
    ] = None,  # type: ignore[assignment]
) -> list[ReferenceFaceResponse]:
    records = await reference_face_service.list_reference_faces(http_request.app.state.db_pool)
    return [ReferenceFaceResponse.from_record(record) for record in records]
