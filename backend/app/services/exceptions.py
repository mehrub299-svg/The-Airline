class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "Internal server error", headers: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.headers = headers


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_failed"

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, message: str = "Not found"):
        super().__init__(message)


class ConflictError(AppError):
    status_code = 409
    code = "conflict"

    def __init__(self, message: str = "Conflict"):
        super().__init__(message)


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str = "Too many requests", retry_after: int | None = None):
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        super().__init__(message, headers=headers)


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"

    def __init__(self, message: str = "Service maintenance"):
        super().__init__(message)



class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str = "Bad request"):
        super().__init__(message)


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"

    def __init__(self, message: str = "Payload too large"):
        super().__init__(message)