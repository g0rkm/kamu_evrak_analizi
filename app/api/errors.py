"""Hataları tutarlı JSON biçimine (`{"detail", "code"}`) çeviren işleyiciler."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger("api")


def _error(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.warning("%s %s -> %s: %s", request.method, request.url.path, exc.code, exc.message)
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(p) for p in first.get("loc", ()) if p not in ("body", "query", "path"))
        detail = f"Geçersiz istek{f' ({location})' if location else ''}: {first.get('msg', 'alan doğrulanamadı')}"
        return _error(422, "validation_error", detail)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Beklenmeyen hata: %s %s", request.method, request.url.path)
        return _error(500, "internal_error", "Sunucuda beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.")
