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
            "metrics": container.metrics is not None,
            "log_service": container.log_service is not None,
            "export_service": container.export_service is not None,
            "maintenance": container.maintenance is not None,
            "error_tracker": container.error_tracker is not None,
            "correlation": container.correlation is not None,
            "sanitizer": container.sanitizer is not None,
            "request_validator": container.request_validator is not None,
            "health_monitor": container.health_monitor is not None,
            "performance_profiler": container.performance_profiler is not None,
            "webhook_retry": container.webhook_retry is not None,
            "backup_verifier": container.backup_verifier is not None,
            "data_encryption": container.data_encryption is not None,
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


@router.get("/system/health-check")
async def comprehensive_health(container: ServiceContainer = Depends(get_container)):
    hc = container.health_checker
    if not hc:
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
    services = {"audit": container.audit, "backup": container.backup, "webhooks": container.webhooks, "integrity": container.integrity, "notifications": container.notifications, "templates": container.templates, "auth": container.auth, "scheduler": container.scheduler, "file_validator": container.file_validator, "session_manager": container.session_manager}
    return hc.check_all(services)


@router.get("/system/directories")
async def check_directories(container: ServiceContainer = Depends(get_container)):
    hc = container.health_checker
    if not hc:
        from app.services.health_checker import HealthChecker
        hc = HealthChecker()
    return hc.check_data_directories()


@router.get("/system/cache-stats")
async def cache_stats(container: ServiceContainer = Depends(get_container)):
    if not container.cache:
        return {"error": "Cache service not available"}
    return container.cache.stats()


@router.post("/system/cache-clear")
async def clear_cache(container: ServiceContainer = Depends(get_container)):
    if not container.cache:
        return {"error": "Cache service not available"}
    container.cache.clear()
    return {"status": "cleared"}


@router.get("/system/retry-stats")
async def retry_stats(container: ServiceContainer = Depends(get_container)):
    if not container.retry:
        return {"error": "Retry service not available"}
    return container.retry.stats()


@router.get("/metrics/summary")
async def metrics_summary(container: ServiceContainer = Depends(get_container)):
    if not container.metrics:
        return {"error": "Metrics service not available"}
    return container.metrics.get_summary()


@router.get("/metrics/endpoints")
async def metrics_endpoints(container: ServiceContainer = Depends(get_container)):
    if not container.metrics:
        return {"error": "Metrics service not available"}
    return {"endpoints": container.metrics.get_endpoint_stats()}


@router.get("/metrics/top-endpoints")
async def metrics_top(container: ServiceContainer = Depends(get_container)):
    if not container.metrics:
        return {"error": "Metrics service not available"}
    return {"top": container.metrics.get_top_endpoints(10)}


@router.get("/metrics/slowest")
async def metrics_slowest(container: ServiceContainer = Depends(get_container)):
    if not container.metrics:
        return {"error": "Metrics service not available"}
    return {"slowest": container.metrics.get_slowest_endpoints(10)}


@router.get("/metrics/status-distribution")
async def metrics_status(container: ServiceContainer = Depends(get_container)):
    if not container.metrics:
        return {"error": "Metrics service not available"}
    return container.metrics.get_status_distribution()


@router.get("/logs/recent")
async def recent_logs(container: ServiceContainer = Depends(get_container)):
    if not container.log_service:
        return {"error": "Log service not available"}
    limit = 50
    return {"logs": container.log_service.get_recent(limit=limit)}


@router.get("/logs/files")
async def log_files(container: ServiceContainer = Depends(get_container)):
    if not container.log_service:
        return {"error": "Log service not available"}
    return {"files": container.log_service.get_log_files()}


@router.get("/logs/stats")
async def log_stats(container: ServiceContainer = Depends(get_container)):
    if not container.log_service:
        return {"error": "Log service not available"}
    return container.log_service.stats()


@router.post("/logs/cleanup")
async def cleanup_logs(request: Request, container: ServiceContainer = Depends(get_container)):
    if not container.log_service:
        return {"error": "Log service not available"}
    body = await request.json()
    days = body.get("days", 30)
    removed = container.log_service.cleanup_old_logs(days=days)
    return {"removed_files": removed, "retention_days": days}


@router.get("/data-export/summary")
async def export_summary(container: ServiceContainer = Depends(get_container)):
    if not container.export_service:
        return {"error": "Export service not available"}
    records = container.export_service.get_all_records()
    return container.export_service.export_summary(records)


@router.get("/data-export/json")
async def export_json(container: ServiceContainer = Depends(get_container)):
    if not container.export_service:
        return {"error": "Export service not available"}
    records = container.export_service.get_all_records()
    return {"records": records, "count": len(records)}


@router.get("/data-export/csv")
async def export_csv(container: ServiceContainer = Depends(get_container)):
    from fastapi.responses import PlainTextResponse
    if not container.export_service:
        return PlainTextResponse("Export service not available", status_code=500)
    records = container.export_service.get_all_records()
    csv_data = container.export_service.export_csv(records)
    return PlainTextResponse(csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=evrak_export.csv"})


@router.get("/maintenance/status")
async def maintenance_status(container: ServiceContainer = Depends(get_container)):
    if not container.maintenance:
        return {"maintenance_mode": False}
    return container.maintenance.status()


@router.post("/maintenance/enable")
async def enable_maintenance(request: Request, container: ServiceContainer = Depends(get_container)):
    if not container.maintenance:
        return {"error": "Maintenance service not available"}
    body = await request.json()
    reason = body.get("reason", "")
    return container.maintenance.enable(reason=reason)


@router.post("/maintenance/disable")
async def disable_maintenance(container: ServiceContainer = Depends(get_container)):
    if not container.maintenance:
        return {"error": "Maintenance service not available"}
    return container.maintenance.disable()


@router.get("/maintenance/history")
async def maintenance_history(container: ServiceContainer = Depends(get_container)):
    if not container.maintenance:
        return {"history": []}
    return {"history": container.maintenance.get_history()}


@router.get("/errors/summary")
async def error_summary(container: ServiceContainer = Depends(get_container)):
    if not container.error_tracker:
        return {"total_errors": 0, "error_types": {}}
    return container.error_tracker.get_summary()


@router.get("/errors/recent")
async def recent_errors(container: ServiceContainer = Depends(get_container)):
    if not container.error_tracker:
        return {"errors": []}
    return {"errors": container.error_tracker.get_recent()}


@router.get("/errors/top")
async def top_errors(container: ServiceContainer = Depends(get_container)):
    if not container.error_tracker:
        return {"top": []}
    return {"top": container.error_tracker.get_top_errors()}


@router.post("/errors/clear")
async def clear_errors(container: ServiceContainer = Depends(get_container)):
    if not container.error_tracker:
        return {"error": "Error tracker not available"}
    container.error_tracker.clear()
    return {"status": "cleared"}


@router.get("/correlation/stats")
async def correlation_stats(container: ServiceContainer = Depends(get_container)):
    if not container.correlation:
        return {"tracked_requests": 0}
    return container.correlation.stats()


@router.get("/correlation/recent")
async def correlation_recent(container: ServiceContainer = Depends(get_container)):
    if not container.correlation:
        return {"requests": []}
    return {"requests": container.correlation.get_recent()}


@router.get("/system/service-count")
async def service_count(container: ServiceContainer = Depends(get_container)):
    services = {
        "audit": container.audit, "backup": container.backup, "webhooks": container.webhooks,
        "integrity": container.integrity, "notifications": container.notifications,
        "templates": container.templates, "auth": container.auth, "scheduler": container.scheduler,
        "file_validator": container.file_validator, "session_manager": container.session_manager,
        "health_checker": container.health_checker, "cache": container.cache, "retry": container.retry,
        "metrics": container.metrics, "log_service": container.log_service,
        "export_service": container.export_service, "maintenance": container.maintenance,
        "error_tracker": container.error_tracker, "correlation": container.correlation,
        "sanitizer": container.sanitizer, "request_validator": container.request_validator,
        "health_monitor": container.health_monitor,
        "performance_profiler": container.performance_profiler,
        "webhook_retry": container.webhook_retry, "backup_verifier": container.backup_verifier,
        "data_encryption": container.data_encryption
    }
    active = sum(1 for v in services.values() if v is not None)
    return {"total_services": len(services), "active_services": active, "inactive_services": len(services) - active}


@router.get("/system/full-status")
async def full_system_status(request: Request, container: ServiceContainer = Depends(get_container)):
    import time as _time
    startup = getattr(request.app.state, 'startup_time', _time.time())
    uptime = _time.time() - startup
    result = {
        "status": "healthy",
        "version": container.settings.VERSION if hasattr(container.settings, 'VERSION') else "unknown",
        "uptime_seconds": round(uptime, 1),
        "active_jobs": getattr(request.app.state, 'active_jobs', 0),
        "services": {},
        "metrics": None,
        "errors": None
    }
    services = {"audit": container.audit, "backup": container.backup, "cache": container.cache, "metrics": container.metrics, "log_service": container.log_service, "maintenance": container.maintenance, "error_tracker": container.error_tracker, "sanitizer": container.sanitizer, "health_monitor": container.health_monitor}
    result["services"] = {k: v is not None for k, v in services.items()}
    if container.metrics:
        result["metrics"] = container.metrics.get_summary()
    if container.error_tracker:
        result["errors"] = container.error_tracker.get_summary()
    if container.maintenance and container.maintenance.is_active:
        result["status"] = "maintenance"
    return result


@router.get("/system/config-validation")
async def config_validation(container: ServiceContainer = Depends(get_container)):
    if not container.config_validator:
        return {"valid": True, "errors": [], "warnings": []}
    return container.config_validator.validate(container.settings)


@router.post("/sanitize/check")
async def sanitize_check(request: Request, container: ServiceContainer = Depends(get_container)):
    svc = container.sanitizer
    if not svc:
        from app.services.sanitizer import Sanitizer
        svc = Sanitizer()
    body = await request.json()
    text = body.get("text", "")
    return svc.sanitize_input(text)


@router.post("/sanitize/filename")
async def sanitize_filename(request: Request, container: ServiceContainer = Depends(get_container)):
    svc = container.sanitizer
    if not svc:
        from app.services.sanitizer import Sanitizer
        svc = Sanitizer()
    body = await request.json()
    filename = body.get("filename", "")
    return {"original": filename, "sanitized": svc.sanitize_filename(filename)}


@router.post("/sanitize/html")
async def sanitize_html_endpoint(request: Request, container: ServiceContainer = Depends(get_container)):
    svc = container.sanitizer
    if not svc:
        from app.services.sanitizer import Sanitizer
        svc = Sanitizer()
    body = await request.json()
    text = body.get("text", "")
    return {"original_length": len(text), "sanitized": svc.sanitize_html(text)}


@router.post("/validate/text")
async def validate_text_input(request: Request, container: ServiceContainer = Depends(get_container)):
    svc = container.request_validator
    if not svc:
        from app.services.request_validator import RequestValidator
        svc = RequestValidator()
    body = await request.json()
    text = body.get("text")
    return svc.validate_text(text)


@router.post("/validate/pagination")
async def validate_pagination(request: Request, container: ServiceContainer = Depends(get_container)):
    svc = container.request_validator
    if not svc:
        from app.services.request_validator import RequestValidator
        svc = RequestValidator()
    body = await request.json()
    return svc.validate_pagination(body.get("offset", 0), body.get("limit", 20))


@router.post("/validate/ids")
async def validate_ids(request: Request, container: ServiceContainer = Depends(get_container)):
    svc = container.request_validator
    if not svc:
        from app.services.request_validator import RequestValidator
        svc = RequestValidator()
    body = await request.json()
    return svc.validate_ids(body.get("ids", []))


@router.get("/health-monitor/status")
async def health_monitor_status(container: ServiceContainer = Depends(get_container)):
    if not container.health_monitor:
        return {"status": "unavailable"}
    return container.health_monitor.get_status()


@router.post("/health-monitor/run")
async def run_health_checks(container: ServiceContainer = Depends(get_container)):
    if not container.health_monitor:
        return {"error": "Health monitor not available"}
    return container.health_monitor.run_checks()


@router.get("/health-monitor/history")
async def health_monitor_history(container: ServiceContainer = Depends(get_container)):
    if not container.health_monitor:
        return {"history": []}
    return {"history": container.health_monitor.get_history()}


@router.get("/profiler/summary")
async def profiler_summary(container: ServiceContainer = Depends(get_container)):
    if not container.performance_profiler:
        return {"error": "Performance profiler not available"}
    return container.performance_profiler.get_summary()


@router.get("/profiler/slow-requests")
async def profiler_slow_requests(container: ServiceContainer = Depends(get_container)):
    if not container.performance_profiler:
        return {"requests": []}
    return container.performance_profiler.get_slow_requests()


@router.get("/profiler/endpoints")
async def profiler_endpoints(container: ServiceContainer = Depends(get_container)):
    if not container.performance_profiler:
        return {"endpoints": {}}
    return container.performance_profiler.get_endpoint_profile()


@router.post("/profiler/reset")
async def profiler_reset(container: ServiceContainer = Depends(get_container)):
    if not container.performance_profiler:
        return {"error": "Performance profiler not available"}
    container.performance_profiler.reset()
    return {"status": "reset"}


@router.get("/webhooks/retry-stats")
async def webhook_retry_stats(container: ServiceContainer = Depends(get_container)):
    if not container.webhook_retry:
        return {"error": "Webhook retry not available"}
    return container.webhook_retry.get_stats()


@router.get("/webhooks/retry-history")
async def webhook_retry_history(container: ServiceContainer = Depends(get_container)):
    if not container.webhook_retry:
        return {"history": []}
    return {"history": container.webhook_retry.get_history()}


@router.get("/backups/list")
async def list_backups(container: ServiceContainer = Depends(get_container)):
    if not container.backup_verifier:
        return {"backups": []}
    return {"backups": container.backup_verifier.list_backups()}


@router.post("/backups/verify")
async def verify_backup(request: Request, container: ServiceContainer = Depends(get_container)):
    if not container.backup_verifier:
        return {"error": "Backup verifier not available"}
    body = await request.json()
    path = body.get("path", "")
    return container.backup_verifier.verify_backup(path)


@router.get("/backups/verification-history")
async def backup_verification_history(container: ServiceContainer = Depends(get_container)):
    if not container.backup_verifier:
        return {"history": []}
    return {"history": container.backup_verifier.get_verification_history()}


@router.get("/backups/stats")
async def backup_stats(container: ServiceContainer = Depends(get_container)):
    if not container.backup_verifier:
        return {"error": "Backup verifier not available"}
    return container.backup_verifier.stats()


@router.post("/encryption/hash")
async def compute_hash(request: Request, container: ServiceContainer = Depends(get_container)):
    if not container.data_encryption:
        return {"error": "Encryption service not available"}
    body = await request.json()
    data = body.get("data", "")
    algorithm = body.get("algorithm", "sha256")
    return {"hash": container.data_encryption.compute_hash(data, algorithm), "algorithm": algorithm}


@router.post("/encryption/verify-hash")
async def verify_hash(request: Request, container: ServiceContainer = Depends(get_container)):
    if not container.data_encryption:
        return {"error": "Encryption service not available"}
    body = await request.json()
    data = body.get("data", "")
    expected = body.get("hash", "")
    algorithm = body.get("algorithm", "sha256")
    return {"valid": container.data_encryption.verify_hash(data, expected, algorithm)}


@router.get("/encryption/stats")
async def encryption_stats(container: ServiceContainer = Depends(get_container)):
    if not container.data_encryption:
        return {"error": "Encryption service not available"}
    return container.data_encryption.get_stats()
