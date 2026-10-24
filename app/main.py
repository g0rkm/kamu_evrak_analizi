"""FastAPI uygulama giriş noktası.

Çalıştırma:  python -m app.main   veya   uvicorn app.main:app
"""
import uuid
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app import __version__
from app.api import router, TAGS_METADATA
from app.api.errors import register_exception_handlers
from app.config import BASE_DIR, Settings, get_settings
from app.container import ServiceContainer
from app.core.logging import configure_logging, new_request_id, request_id_var
from app.core.metrics import metrics
from app.core.rate_limit import RateLimitMiddleware
from app.core.startup import verify_environment
from app.core.timeout_middleware import RequestTimeoutMiddleware, ActiveJobsMiddleware
from app.core.security_middleware import SecurityHeadersMiddleware
from app.core.ip_filter_middleware import IPFilterMiddleware
from app.core.audit_middleware import AuditMiddleware
from app.core.metrics_middleware import MetricsMiddleware
from app.services.audit_logger import AuditLogger
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService
from app.services.integrity_service import IntegrityService
from app.services.notification_service import NotificationService
from app.services.scheduler_service import SchedulerService
from app.services.template_service import TemplateService
from app.services.webhook_service import WebhookService
from app.services.migration_service import MigrationService
from app.services.file_validator import FileValidator
from app.services.session_manager import SessionManager
from app.services.health_checker import HealthChecker
from app.services.cache_service import CacheService
from app.services.retry_service import RetryService
from app.services.metrics_service import MetricsService
from app.services.log_service import LogService

FRONTEND_DIR = BASE_DIR / "frontend"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL, settings.LOG_FORMAT, settings.LOG_FILE)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = ServiceContainer.build(settings)
        app.state.container = container
        app.state.container.audit = AuditLogger(log_dir=str(Path(settings.HISTORY_DIR) / 'audit'))
        app.state.container.backup = BackupService(history_dir=str(Path(settings.HISTORY_DIR)))
        app.state.container.webhooks = WebhookService()
        app.state.container.integrity = IntegrityService()
        app.state.container.notifications = NotificationService(str(Path(settings.HISTORY_DIR).parent / "notifications"))
        app.state.container.templates = TemplateService(str(Path(settings.HISTORY_DIR).parent / "templates"))
        app.state.container.auth = AuthService(str(Path(settings.HISTORY_DIR).parent / "auth"))
        app.state.container.scheduler = SchedulerService()
        app.state.container.scheduler.start()
        app.state.container.file_validator = FileValidator(max_file_size_mb=settings.MAX_FILE_SIZE_MB)
        app.state.container.session_manager = SessionManager(timeout_minutes=settings.SESSION_TIMEOUT_MINUTES)
        app.state.container.health_checker = HealthChecker()
        app.state.container.cache = CacheService(default_ttl=settings.CACHE_TTL)
        app.state.container.retry = RetryService()
        app.state.container.metrics = MetricsService()
        app.state.container.log_service = LogService()
        migration_svc = MigrationService(settings.HISTORY_DIR)
        app.state.migration = migration_svc
        app.state.active_jobs = 0
        app.state.startup_time = time.time()
        verify_environment(settings)
        import logging as _logging
        _logging.getLogger("startup").info("Uygulama başlatıldı, istekler kabul ediliyor.")
        yield
        if container := getattr(app.state, 'container', None):
            if getattr(container, 'scheduler', None):
                container.scheduler.stop()
        active_jobs = getattr(app.state, 'active_jobs', 0)
        _logging.getLogger("startup").info('Kapatiliyor, aktif is sayisi: %d', active_jobs)
        active = len(app.state.container.jobs._tasks)
        if active > 0:
            _logging.getLogger("startup").info("Aktif iş sayısı: %d — tamamlanması bekleniyor…", active)
        _logging.getLogger("startup").info("Uygulama kapatılıyor…")
        await app.state.container.aclose()

    app = FastAPI(
        title=settings.APP_NAME,
        description="Kamu evraklarını yapay zekâ ile analiz eden, sınıflandıran ve karşılaştıran API servisi.",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )

    app.add_middleware(ActiveJobsMiddleware)

    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type"],
        )

    app.add_middleware(RateLimitMiddleware, max_requests=settings.RATE_LIMIT_REQUESTS, window=settings.RATE_LIMIT_WINDOW)
    
    @app.middleware("http")
    async def maintenance_mode_middleware(request: Request, call_next):
        if request.app.state.container.settings.MAINTENANCE_MODE:
            if not request.url.path.startswith("/api/health"):
                from starlette.responses import JSONResponse as _JSONResp
                return _JSONResp(
                    status_code=503,
                    content={"error": "maintenance_mode", "message": "Sistem şu anda bakım modundadır. Lütfen daha sonra tekrar deneyin."},
                )
        return await call_next(request)

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        return response

    @app.middleware("http")
    async def inject_request_id(request: Request, call_next):
        import time as _time
        rid = request.headers.get("X-Request-ID") or new_request_id()
        request_id_var.set(rid)
        start = _time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time"] = f"{((_time.perf_counter() - start) * 1000):.0f}ms"
        response.headers["X-API-Version"] = __version__
        if request.url.path.startswith("/api/"):
            metrics.record_request(response.status_code, endpoint=request.url.path)
        return response

    @app.middleware("http")
    async def log_api_requests(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            import logging
            api_logger = logging.getLogger("api.access")
            response = await call_next(request)
            api_logger.info(
                "%s %s -> %d (%s) ua=%s cl=%s",
                request.method,
                request.url.path,
                response.status_code,
                response.headers.get("X-Response-Time", "?"),
                (request.headers.get("user-agent") or "-")[:80],
                request.headers.get("content-length", "-"),
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
            if request.method == "GET":
                response.headers.setdefault("Cache-Control", "private, max-age=0, must-revalidate")
            else:
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

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuditMiddleware, audit_service=lambda: app.state.container.audit)

    if settings.IP_WHITELIST or settings.IP_BLACKLIST:
        app.add_middleware(IPFilterMiddleware, whitelist=settings.IP_WHITELIST, blacklist=settings.IP_BLACKLIST)

    app.add_middleware(MetricsMiddleware, metrics_service_getter=lambda: app.state.container.metrics)

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
