class SocialiteException(Exception):
    pass


class InvalidStateException(SocialiteException):
    pass


class DriverMissingConfigurationException(SocialiteException):
    pass


class AuthorizationDeniedException(SocialiteException):
    def __init__(self, error: str, error_description: str | None = None):
        self.error = error
        self.error_description = error_description
        super().__init__(
            f"OAuth authorization failed: {error}" + (f" ({error_description})" if error_description else "")
        )


class ProviderRequestException(SocialiteException):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)
