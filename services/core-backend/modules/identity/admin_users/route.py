from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.config import ConfigurationError
from core.errors import error_detail
from modules.identity.admin_users.exception import (
    AccountProvisioningError,
    AccountProvisioningUnavailableError,
    CannotModifyOwnAccountError,
    DuplicateAccountFieldError,
    OrphanedKeycloakUserError,
    UserNotFoundError,
)
from modules.identity.admin_users.schemas import (
    AccountProvisionRequest,
    AccountProvisioningOptionsResponse,
    AccountStatusResponse,
    AccountStatusUpdateRequest,
    AdministratorAccountResponse,
    LecturerAccountResponse,
    ProvisionedAccountResponse,
    ProvisioningOptionResponse,
    StudentAccountResponse,
    UserDirectoryResponse,
)
from modules.identity.admin_users.service import AdminUserService
from modules.identity.auth.dependencies import CurrentAdministrator
from modules.identity.keycloak_admin.client import KeycloakAdminClient

router = APIRouter(prefix="/administrators/me", tags=["admin-users"])

_USER_NOT_FOUND_DETAIL = error_detail("USER_NOT_FOUND", "The user account was not found.")
_CANNOT_MODIFY_OWN_ACCOUNT_DETAIL = error_detail(
    "CANNOT_MODIFY_OWN_ACCOUNT", "You cannot change your own account status.",
)


def get_admin_user_service() -> AdminUserService:
    return AdminUserService()


def get_account_provisioning_service(request: Request) -> AdminUserService:
    try:
        keycloak_client = KeycloakAdminClient.from_settings(request.app.state.settings)
    except ConfigurationError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            error_detail("KEYCLOAK_ADMIN_UNAVAILABLE", str(error)),
        ) from error
    return AdminUserService(keycloak_client=keycloak_client)


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


@router.post(
    "/users",
    response_model=ProvisionedAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_user_account(
    body: AccountProvisionRequest,
    http_request: Request,
    current_administrator: CurrentAdministrator,
    user_service: Annotated[
        AdminUserService,
        Depends(get_account_provisioning_service),
    ] = None,  # type: ignore[assignment]
) -> ProvisionedAccountResponse:
    try:
        account = await user_service.provision_account(
            http_request.app.state.db_pool,
            current_administrator.user_id,
            body,
        )
    except DuplicateAccountFieldError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            error_detail("DUPLICATE_ACCOUNT_FIELD", str(error)),
        ) from error
    except OrphanedKeycloakUserError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_detail("ORPHANED_KEYCLOAK_USER", str(error)),
        ) from error
    except AccountProvisioningUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            error_detail(
                "ACCOUNT_PROVISIONING_UNAVAILABLE",
                "Account provisioning is temporarily unavailable. Please try again.",
            ),
        ) from error
    except AccountProvisioningError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            error_detail(
                "ACCOUNT_PROVISIONING_FAILED",
                "The account could not be provisioned. Any partial identity was cleaned up.",
            ),
        ) from error

    return ProvisionedAccountResponse(
        user_id=account.user_id,
        keycloak_user_id=account.keycloak_user_id,
        role=account.role,
        email=account.email,
        temporary_password=account.temporary_password,
    )


@router.get(
    "/users/provisioning-options",
    response_model=AccountProvisioningOptionsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_account_provisioning_options(
    http_request: Request,
    current_administrator: CurrentAdministrator,
    user_service: Annotated[
        AdminUserService,
        Depends(get_admin_user_service),
    ] = None,  # type: ignore[assignment]
) -> AccountProvisioningOptionsResponse:
    departments = await user_service.get_provisioning_departments(http_request.app.state.db_pool)
    return AccountProvisioningOptionsResponse(
        departments=[ProvisioningOptionResponse.from_record(item) for item in departments],
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
