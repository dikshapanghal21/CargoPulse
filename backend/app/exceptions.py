from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class BusinessValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


def _error_body(code: str, message: str, field: str | None = None) -> dict:
    body: dict = {"detail": message, "code": code}
    if field:
        body["field"] = field
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_error_body(exc.code, exc.message, exc.field)
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        # Last line of defence: services pre-validate, but races can still hit DB constraints.
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        message = "The request conflicts with existing data"
        if constraint:
            message += f" (constraint: {constraint})"
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content=_error_body("integrity_error", message)
        )
