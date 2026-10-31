from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.validation.message_bag import MessageBag


class DriverNotFound(Exception):
    pass


class DriverLibraryNotFound(Exception):
    pass


class FileTypeException(Exception):
    pass


class RequiredContainerBindingNotFound(Exception):
    pass


class MissingContainerBindingNotFound(Exception):
    pass


class UnacceptableDriverType(Exception):
    pass


class ContainerError(Exception):
    pass


class InvalidCSRFToken(Exception):
    pass


class InvalidHTTPStatusCode(Exception):
    pass


class RouteMiddlewareNotFound(Exception):
    pass


class ResponseError(Exception):
    pass


class InvalidAutoloadPath(Exception):
    pass


class AutoloadContainerOverwrite(Exception):
    pass


class InvalidSecretKey(Exception):
    pass


class InvalidToken(Exception):
    pass


class StrictContainerException(Exception):
    pass


class InvalidRouteCompileException(Exception):
    pass


class RouteException(Exception):
    pass


class HttpException(Exception):
    is_http_exception = True

    def get_status(self) -> int:
        raise NotImplementedError

    def get_response(self) -> str:
        raise NotImplementedError

    def get_headers(self) -> dict[str, str] | None:
        return None


class RouteNotFoundException(HttpException):
    def __init__(self, message):
        super().__init__(message)
        self.message = message or "Route Not Found"

    def get_response(self):
        return self.message

    def get_status(self):
        return 404


class MethodNotAllowedException(HttpException):
    def __init__(self, allowed_methods, method):
        allowed_list = ", ".join(allowed_methods)
        message = f"{method} method not allowed for this route. Supported methods are: {allowed_list}."
        super().__init__(message)
        self.message = message
        self.headers = {"Allow": allowed_list}

    def get_response(self):
        return self.message

    def get_headers(self):
        return self.headers

    def get_status(self):
        return 405


class DebugException(Exception):
    pass


class DumpException(Exception):
    pass


class ViewException(Exception):
    pass


class QueueException(Exception):
    pass


class AmbiguousError(Exception):
    pass


class ProjectLimitReached(Exception):
    pass


class ProjectProviderTimeout(Exception):
    pass


class ProjectProviderHttpError(Exception):
    pass


class ProjectTargetNotEmpty(Exception):
    pass


class NotificationException(Exception):
    pass


class AuthorizationException(HttpException):
    def __init__(self, message="", status=403):
        super().__init__(message)
        self.message = message or "Action not authorized"
        self.status = status or 403

    def get_response(self):
        return self.message

    def get_status(self):
        return self.status


class ThrottleRequestsException(HttpException):
    def __init__(self, message="Too many attempts", status=429, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.headers = headers

    def get_headers(self):
        return self.headers

    def get_response(self):
        return self.message

    def get_status(self):
        return self.status


class GateDoesNotExist(Exception):
    pass


class PolicyDoesNotExist(Exception):
    pass


class MixManifestNotFound(Exception):
    pass


class MixFileNotFound(Exception):
    pass


class InvalidConfigurationLocation(Exception):
    pass


class InvalidConfigurationSetup(Exception):
    pass


class InvalidPackageName(Exception):
    pass


class LoaderNotFound(Exception):
    pass


class ValidationException(HttpException):
    def __init__(self, errors: "MessageBag | Mapping[str, Iterable[str]]"):
        from fastapi_startkit.validation.message_bag import MessageBag

        self.bag = errors if isinstance(errors, MessageBag) else MessageBag(errors)
        self.errors = self.bag.messages
        super().__init__(self.bag.summary())

    def get_status(self) -> int:
        return 422

    def get_response(self) -> str:
        return self.bag.summary()
