class DeviceTokenError(Exception):
    """Base class for device-token failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidExpoPushTokenError(DeviceTokenError):
    """Raised when an Expo push token does not match the expected format."""


class UnsupportedPlatformError(DeviceTokenError):
    """Raised when the platform value is not android, ios, or web."""
