class AdminUserError(Exception):
    """Base class for admin user-directory errors."""


class UserNotFoundError(AdminUserError):
    """The application user does not exist."""


class CannotModifyOwnAccountError(AdminUserError):
    """An administrator cannot change their own account status through this endpoint."""


class DuplicateAccountFieldError(AdminUserError):
    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"An account with this {field_name} already exists.")


class AccountProvisioningError(AdminUserError):
    """Provisioning failed without leaving a known orphaned account."""


class AccountProvisioningUnavailableError(AccountProvisioningError):
    """The external identity provider cannot currently provision accounts."""


class OrphanedKeycloakUserError(AccountProvisioningError):
    def __init__(self, keycloak_user_id: str) -> None:
        self.keycloak_user_id = keycloak_user_id
        super().__init__(
            f"Provisioning failed and Keycloak user {keycloak_user_id} could not be removed or disabled.",
        )
