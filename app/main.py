"""FastAPI uygulama giriş noktası.

Çalıştırma:  python -m app.main   veya   uvicorn app.main:app
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import router
from app.api.errors import register_exception_handlers
from app.config import BASE_DIR, Settings, get_settings
from app.container import ServiceContainer
from app.core.logging import configure_logging, new_request_id, request_id_var
from app.core.rate_limit import RateLimitMiddleware
from app.core.startup import verify_environment

FRONTEND_DIR = BASE_DIR / "frontend"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = ServiceContainer.build(settings)
        verify_environment(settings)
        yield
        await app.state.container.aclose()

    app = FastAPI(
        title=settings.APP_NAME,
        description="Kamu evrak ve yazışma süreçleri için çok ajanlı yapay zekâ destek sistemi",
        version=__version__,
        lifespan=lifespan,
    )

    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type"],
        )

    app.add_middleware(RateLimitMiddleware, max_requests=60, window=60)

    @app.middleware("http")
    async def inject_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or new_request_id()
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        # Basit CSRF koruması: durum değiştiren API istekleri Content-Type başlığı gerektirir
        if (
            request.url.path.startswith("/api/")
            and request.method in ("POST", "PATCH", "PUT")
            and not request.url.path.endswith("/file")  # multipart upload hariç
        ):
            ct = (request.headers.get("content-type") or "").lower()
            if not ct.startswith(("application/json", "multipart/form-data")):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Geçersiz Content-Type başlığı.", "code": "invalid_content_type"},
                )

        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and request.url.path.startswith("/api/"):
            max_body = settings.max_file_bytes + 1024  # dosya limiti + header overhead
            if int(content_length) > max_body:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={"detail": "İstek gövdesi çok büyük.", "code": "body_too_large"},
                )
        return await call_next(request)

    register_exception_handlers(app)
    app.include_router(router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    _settings = get_settings()
    uvicorn.run("app.main:app", host=_settings.APP_HOST, port=_settings.APP_PORT)
