"""Application error type + global exception handlers.

Handlers guarantee that users never receive raw stack traces: every error
returns a JSON body of the form {"detail": {"code": ..., "message": ...}}.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("ddht")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra

    def body(self) -> dict:
        return {"detail": {"code": self.code, "message": self.message, **self.extra}}


def not_found(what: str) -> AppError:
    return AppError(404, f"{what.upper().replace(' ', '_')}_NOT_FOUND", f"{what.capitalize()} not found.")


def forbidden(message: str, code: str = "FORBIDDEN", **extra) -> AppError:
    return AppError(403, code, message, **extra)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=exc.body())

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict):
            content = {"detail": exc.detail}
        else:
            content = {"detail": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)}}
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        fields = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path"))
            fields.append({"field": loc, "message": err.get("msg", "Invalid value")})
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "VALIDATION_ERROR", "message": "Some fields are invalid.", "fields": fields}},
        )

    @app.exception_handler(OperationalError)
    async def _db_down(_: Request, exc: OperationalError):
        log.error("Database operational error: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": {"code": "DATABASE_UNAVAILABLE", "message": "The database is currently unavailable. Please try again later."}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError):
        log.exception("Database error")
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "DATABASE_ERROR", "message": "A database error occurred. Please try again."}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred. Please try again."}},
        )
