"""FastAPI uygulama giriş noktası.

Çalıştırma:  python -m app.main   veya   uvicorn app.main:app
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app import __version__
from app.api import router
from app.api.errors import register_exception_handlers
from app.config import BASE_DIR, Settings, get_settings
from app.container import ServiceContainer
from app.core.logging import configure_logging, new_request_id, request_id_var
from app.core.metrics import metrics
from app.core.rate_limit import RateLimitMiddleware
from app.core.startup import verify_environment

FRONTEND_DIR = BASE_DIR / "frontend"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
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

    app.add_middleware(RateLimitMiddleware, max_requests=settings.RATE_LIMIT_REQUESTS, window=settings.RATE_LIMIT_WINDOW)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def inject_request_id(request: Request, call_next):
        import time as _time
        rid = request.headers.get("X-Request-ID") or new_request_id()
        request_id_var.set(rid)
        start = _time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time"] = f"{((_time.perf_counter() - start) * 1000):.0f}ms"
        if request.url.path.startswith("/api/"):
            metrics.record_request(response.status_code)
        return response

    @app.middleware("http")
    async def log_api_requests(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            import logging
            api_logger = logging.getLogger("api.access")
            response = await call_next(request)
            api_logger.info(
                "%s %s -> %d (%s)",
                request.method,
                request.url.path,
                response.status_code,
                response.headers.get("X-Response-Time", "?"),
            )
            return response
        return await call_next(request)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        # Basit CSRF koruması: durum değiştiren API istekleri Content-Type başlığı gerektirir
        if (
            request.url.path.startswith("/api/")
            and request.method in ("POST", "PATCH", "PUT", "DELETE")
            and not request.url.path.endswith("/file")  # multipart upload hariç
        ):
            ct = (request.headers.get("content-type") or "").lower()
            if request.method == "DELETE" and not ct:
                pass  # DELETE istekleri body gerektirmez
            elif not ct.startswith(("application/json", "multipart/form-data")):
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

        if not request.url.path.startswith("/api/"):
            csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
            header_name = "Content-Security-Policy-Report-Only" if settings.CSP_REPORT_ONLY else "Content-Security-Policy"
            response.headers.setdefault(header_name, csp)

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
