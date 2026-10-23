from fastapi import APIRouter, Depends, Request
from app.api.dependencies import get_container
from app.container import ServiceContainer

router = APIRouter(tags=["Konfigürasyon"])


@router.get("/system/config-report")
async def config_report(request: Request, container: ServiceContainer = Depends(get_container)):
    settings = container.settings
    return {
        "environment": getattr(settings, "ENVIRONMENT", "development"),
        "max_file_size_mb": getattr(settings, "MAX_FILE_SIZE_MB", 50),
        "request_body_limit_mb": getattr(settings, "REQUEST_BODY_LIMIT_MB", 100),
        "rate_limit_per_minute": getattr(settings, "RATE_LIMIT_PER_MINUTE", 60),
        "max_history_records": getattr(settings, "MAX_HISTORY_RECORDS", 10000),
        "cors_origins": getattr(settings, "CORS_ORIGINS", "*"),
        "log_level": getattr(settings, "LOG_LEVEL", "INFO"),
        "enable_notifications": getattr(settings, "ENABLE_NOTIFICATIONS", True),
        "auto_backup_enabled": getattr(settings, "AUTO_BACKUP_ENABLED", False),
        "session_timeout_minutes": getattr(settings, "SESSION_TIMEOUT_MINUTES", 30),
        "services": {
            "audit": container.audit is not None,
            "backup": container.backup is not None,
            "webhooks": container.webhooks is not None,
            "integrity": container.integrity is not None,
            "notifications": container.notifications is not None,
            "templates": container.templates is not None,
            "auth": container.auth is not None,
            "scheduler": container.scheduler is not None,
        },
    }


@router.get("/system/environment")
async def system_environment(request: Request, container: ServiceContainer = Depends(get_container)):
    import platform
    import sys
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
    }


@router.get('/api-summary')
async def api_summary(request: Request):
    routes = []
    for route in request.app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({'path': route.path, 'methods': list(route.methods), 'name': route.name})
    return {'total_endpoints': len(routes), 'endpoints': sorted(routes, key=lambda x: x['path'])}
