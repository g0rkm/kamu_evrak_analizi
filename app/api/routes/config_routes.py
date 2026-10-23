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
            "file_validator": container.file_validator is not None,
            "session_manager": container.session_manager is not None,
            "health_checker": container.health_checker is not None,
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


@router.get('/system/uptime')
async def system_uptime(request: Request):
    import time
    startup = getattr(request.app.state, 'startup_time', time.time())
    uptime = time.time() - startup
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    return {'uptime_seconds': round(uptime, 1), 'uptime_human': f'{hours}sa {minutes}dk'}


@router.get('/system/active-jobs')
async def active_jobs(request: Request):
    count = getattr(request.app.state, 'active_jobs', 0)
    return {'active_jobs': count}


@router.post("/validate-file")
async def validate_file(request: Request, container: ServiceContainer = Depends(get_container)):
    body = await request.json()
    filename = body.get("filename", "")
    file_size = body.get("file_size", 0)
    validator = container.file_validator
    if not validator:
        from app.services.file_validator import FileValidator
        validator = FileValidator()
    result = validator.validate(filename, file_size)
    result["file_type"] = validator.get_file_type_label(filename)
    return result


@router.get("/supported-file-types")
async def supported_file_types(container: ServiceContainer = Depends(get_container)):
    validator = container.file_validator
    if not validator:
        from app.services.file_validator import FileValidator
        validator = FileValidator()
    return {"extensions": sorted(validator.ALLOWED_EXTENSIONS), "max_size_mb": validator.max_file_size_mb}


@router.get("/sessions/stats")
async def session_stats(container: ServiceContainer = Depends(get_container)):
    sm = container.session_manager
    if not sm:
        return {"error": "Session manager not available"}
    return sm.stats()


@router.get("/sessions/active")
async def active_sessions(container: ServiceContainer = Depends(get_container)):
    sm = container.session_manager
    if not sm:
        return {"error": "Session manager not available"}
    sessions = sm.get_active_sessions()
    safe = [{"username": s["username"], "role": s["role"], "created_at": s["created_at"], "last_activity": s["last_activity"]} for s in sessions]
    return {"sessions": safe, "count": len(safe)}


@router.post("/sessions/cleanup")
async def cleanup_sessions(container: ServiceContainer = Depends(get_container)):
    sm = container.session_manager
    if not sm:
        return {"error": "Session manager not available"}
    removed = sm.cleanup_expired()
    return {"removed": removed, "remaining": sm.stats()["total_active"]}


@router.get("/health/comprehensive")
async def comprehensive_health(container: ServiceContainer = Depends(get_container)):
    hc = container.health_checker
    if not hc:
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
    services = {"audit": container.audit, "backup": container.backup, "webhooks": container.webhooks, "integrity": container.integrity, "notifications": container.notifications, "templates": container.templates, "auth": container.auth, "scheduler": container.scheduler, "file_validator": container.file_validator, "session_manager": container.session_manager}
    return hc.check_all(services)


@router.get("/health/directories")
async def check_directories(container: ServiceContainer = Depends(get_container)):
    hc = container.health_checker
    if not hc:
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
    return hc.check_data_directories()
