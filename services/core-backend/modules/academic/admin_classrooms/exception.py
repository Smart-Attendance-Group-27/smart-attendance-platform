class AdminClassroomError(Exception):
    """Base class for admin classroom/geofence administration errors."""


class ClassroomNotFoundError(AdminClassroomError):
    """The classroom does not exist."""


class BuildingNotFoundError(AdminClassroomError):
    """The referenced building does not exist."""
