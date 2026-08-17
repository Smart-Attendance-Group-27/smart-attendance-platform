class AdminUserError(Exception):
    """Base class for admin user-directory errors."""


class UserNotFoundError(AdminUserError):
    """The application user does not exist."""


class CannotModifyOwnAccountError(AdminUserError):
    """An administrator cannot change their own account status through this endpoint."""
