class AdminAcademicManagementError(Exception):
    """Base error for administrator academic-data mutations."""


class AcademicEntityNotFoundError(AdminAcademicManagementError):
    def __init__(self, entity: str) -> None:
        super().__init__(entity)
        self.entity = entity


class AcademicConflictError(AdminAcademicManagementError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
