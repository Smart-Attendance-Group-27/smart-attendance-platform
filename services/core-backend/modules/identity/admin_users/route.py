from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from modules.identity.admin_users.exception import (
    CannotModifyOwnAccountError,
    UserNotFoundError,
)
from modules.identity.admin_users.schemas import (
    AccountStatusResponse,
    AccountStatusUpdateRequest,
    AdministratorAccountResponse,
    LecturerAccountResponse,
    StudentAccountResponse,
    UserDirectoryResponse,
)
from modules.identity.admin_users.service import AdminUserService
from modules.identity.auth.dependencies import CurrentAdministrator

router = APIRouter(prefix="/administrators/me", tags=["admin-users"])

_USER_NOT_FOUND_DETAIL = "The user account was not found."
_CANNOT_MODIFY_OWN_ACCOUNT_DETAIL = "You cannot change your own account status."


def get_admin_user_service() -> AdminUserService:
    return AdminUserService()


@router.get("/users", response_model=UserDirectoryResponse, status_code=status.HTTP_200_OK)
async def get_user_directory(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    user_service: Annotated[
        AdminUserService,
        Depends(get_admin_user_service),
    ] = None,  # type: ignore[assignment]
) -> UserDirectoryResponse:
    directory = await user_service.get_directory(http_request.app.state.db_pool)
    return UserDirectoryResponse(
        students=[StudentAccountResponse.from_record(s) for s in directory.students],
        lecturers=[LecturerAccountResponse.from_record(l) for l in directory.lecturers],
        administrators=[AdministratorAccountResponse.from_record(a) for a in directory.administrators],
    )


@router.patch(
    "/users/{user_id}/account-status",
    response_model=AccountStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def update_user_account_status(
    user_id: UUID,
    body: AccountStatusUpdateRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    user_service: Annotated[
        AdminUserService,
        Depends(get_admin_user_service),
    ] = None,  # type: ignore[assignment]
) -> AccountStatusResponse:
    try:
        updated = await user_service.update_account_status(
            http_request.app.state.db_pool,
            current_administrator.user_id,
            user_id,
            body.account_status.value,
        )
    except UserNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _USER_NOT_FOUND_DETAIL) from error
    except CannotModifyOwnAccountError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            _CANNOT_MODIFY_OWN_ACCOUNT_DETAIL,
        ) from error

    return AccountStatusResponse.from_record(updated)
