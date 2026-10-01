"""User-facing application errors."""


class OutboundError(Exception):
    """Base error with a message safe to show in the UI."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class LocationNotFoundError(OutboundError):
    pass


class InvalidLocationError(OutboundError):
    pass


class InvalidDateError(OutboundError):
    pass


class ServiceUnavailableError(OutboundError):
    pass


class DataParseError(OutboundError):
    pass
