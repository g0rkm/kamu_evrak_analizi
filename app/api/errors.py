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
        from app.core.logging import request_id_var
        rid = request_id_var.get("")
        if exc.status_code >= 500:
            logger.warning("%s %s -> %s: %s [request_id=%s]", request.method, request.url.path, exc.code, exc.message, rid)
        
        headers = {"Retry-After": "60"} if exc.status_code == 429 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code, "request_id": rid},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        from app.core.logging import request_id_var
        rid = request_id_var.get("")
        errors = exc.errors()
        first = errors[0] if errors else {}
        location = ".".join(str(p) for p in first.get("loc", ()) if p not in ("body", "query", "path"))
        detail = f"Geçersiz istek{f' ({location})' if location else ''}: {first.get('msg', 'alan doğrulanamadı')}"
        return JSONResponse(
            status_code=422,
            content={
                "detail": errors[0]["msg"] if errors else "Doğrulama hatası.",
                "code": "validation_error",
                "errors": [
                    {k: v for k, v in e.items() if k != "ctx"}
                    for e in errors
                ],
                "request_id": rid,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        from app.core.logging import request_id_var
        rid = request_id_var.get("")
        headers = {"Retry-After": "60"} if exc.status_code == 429 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc.detail), "code": "http_error", "request_id": rid},
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        from app.core.logging import request_id_var
        rid = request_id_var.get("")
        logger.exception("Beklenmeyen hata: %s %s [request_id=%s]", request.method, request.url.path, rid)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Sunucuda beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
                "code": "internal_error",
                "request_id": rid,
            },
        )
