class LecturerReportError(Exception):
    """Base class for lecturer report domain errors."""


class CourseOfferingNotFoundError(LecturerReportError):
    """The course offering does not exist, or is not taught by this lecturer."""
