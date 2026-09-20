class PushDeliveryError(Exception):
    """Base class for push-delivery failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ExpoServiceError(PushDeliveryError):
    """Raised when the Expo Push API returns a non-2xx response."""


class ExpoNetworkError(PushDeliveryError):
    """Raised when the network request to Expo fails or times out."""


class NotificationTypeNotFoundError(Exception):
    """Raised when the requested notification type code does not exist."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Notification type '{code}' does not exist.")
        self.code = code


class InactiveNotificationTypeError(Exception):
    """Raised when the notification type exists but is marked inactive."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Notification type '{code}' is not active.")
        self.code = code
