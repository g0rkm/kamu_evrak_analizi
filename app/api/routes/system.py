import shutil
import time

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app import __version__
from app.agents.orchestrator import PIPELINE_STEPS
from app.api.dependencies import get_container, require_admin
from app.container import ServiceContainer
from app.core.metrics import metrics as app_metrics
from app.core.taxonomy import DOCUMENT_TYPES, DRAFT_TYPES, ORG_UNITS, PRIORITIES, UNKNOWN_DOCUMENT_TYPE
from app.models.api import HealthStatus
from app.services.pii_detector import PIIDetector
from app.services.upload_storage import ALLOWED_EXTENSIONS

router = APIRouter(tags=["sistem"])
_start_time = time.monotonic()


def _format_uptime(seconds: float) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours} saat {minutes} dk"
    if minutes > 0:
        return f"{minutes} dk {secs} sn"
    return f"{secs} sn"


@router.get('/version', tags=['Sistem'], summary='API surum bilgisi')
async def api_version():
    from app import __version__
    return {'version': __version__, 'api': 'v1', 'status': 'stable'}


@router.get('/environment', tags=['Sistem'], summary='Ortam bilgisi')
async def environment_info(container: ServiceContainer = Depends(get_container)):
    import sys
    return {
        'environment': container.settings.ENVIRONMENT,
        'python_version': sys.version,
        'debug': container.settings.ENVIRONMENT == 'development',
        'maintenance_mode': container.settings.MAINTENANCE_MODE,
        'rate_limit': {
            'requests': container.settings.RATE_LIMIT_REQUESTS,
            'window': container.settings.RATE_LIMIT_WINDOW
        }
    }


@router.get("/health", summary="Sistem sağlık kontrolü")
async def health_check(container: ServiceContainer = Depends(get_container)):
    stats = container.history.stats()
    try:
        disk = shutil.disk_usage(container.settings.history_path)
        disk_free_mb = round(disk.free / (1024 * 1024), 1)
    except OSError:
        disk_free_mb = None

    status = "ok"
    if not container.llm.is_configured:
        status = "degraded"
    elif disk_free_mb is not None and disk_free_mb < container.settings.DISK_WARNING_THRESHOLD_MB / 2:
        status = "warning"

    warnings = []
    if not container.llm.is_configured:
        warnings.append("LLM API anahtarı yapılandırılmamış.")
    if not container.rag.available:
        warnings.append("RAG mevzuat indeksi yüklenmemiş.")
    if disk_free_mb is not None and disk_free_mb < container.settings.DISK_WARNING_THRESHOLD_MB:
        warnings.append(f"Disk alanı düşük: {disk_free_mb} MB kaldı.")

    result = HealthStatus(
        status=status,
        environment=container.settings.ENVIRONMENT,
        service=container.settings.APP_NAME,
        version=__version__,
        llm_configured=container.llm.is_configured,
        llm_model=container.llm.model,
        rag_available=container.rag.available,
        rag_chunks=container.rag.chunk_count,
        total_analyses=stats["total"],
        avg_confidence=stats["avg_confidence"],
        llm_usage=container.llm.get_usage_stats(),
        uptime_seconds=round(time.monotonic() - _start_time, 1),
        active_jobs=len(container.jobs._tasks),
        disk_free_mb=disk_free_mb,
        warnings=warnings,
    )
    data = result.model_dump()
    data["uptime_human"] = _format_uptime(time.monotonic() - _start_time)
    data["checks"] = {
        "storage": True,
        "llm_configured": container.llm.is_configured,
        "rag_available": container.rag.available,
    }
    return data


@router.get('/health/dependencies', tags=['Sistem'], summary='Bagimliliklarin durumu')
async def check_dependencies(container: ServiceContainer = Depends(get_container)):
    import shutil
    deps = {}
    deps['tesseract'] = shutil.which('tesseract') is not None
    deps['llm_configured'] = container.llm.is_configured
    deps['rag_available'] = container.rag.available
    deps['history_writable'] = container.settings.history_path.exists()
    all_ok = all(deps.values())
    return {'healthy': all_ok, 'dependencies': deps}


@router.get("/ready", summary="Hazırlık kontrolü (readiness probe)")
async def readiness_check(container: ServiceContainer = Depends(get_container)):
    checks = {
        "llm_configured": container.llm.is_configured,
        "history_writable": container.settings.history_path.exists(),
        "circuit_breaker_closed": not container.llm._breaker.is_open,
    }
    all_ok = all(checks.values())
    from fastapi.responses import JSONResponse
    status_code = 200 if all_ok else 503
    return JSONResponse(content={"ready": all_ok, "checks": checks}, status_code=status_code)


@router.get('/startup-checks', tags=['Sistem'], summary='Baslangic kontrolleri')
async def startup_checks(container: ServiceContainer = Depends(get_container)):
    import shutil
    checks = []
    checks.append({
        'name': 'LLM Yapılandırması',
        'status': 'ok' if container.llm.is_configured else 'warning',
        'detail': 'API anahtarı yapılandırılmış' if container.llm.is_configured else 'API anahtarı eksik'
    })
    checks.append({
        'name': 'RAG İndeksi',
        'status': 'ok' if container.rag.available else 'warning',
        'detail': 'Mevzuat indeksi yüklü' if container.rag.available else 'İndeks yüklenmemiş'
    })
    checks.append({
        'name': 'Geçmiş Dizini',
        'status': 'ok' if container.settings.history_path.exists() else 'error',
        'detail': str(container.settings.history_path)
    })
    try:
        disk = shutil.disk_usage(container.settings.history_path)
        disk_ok = disk.free > container.settings.DISK_WARNING_THRESHOLD_MB * 1024 * 1024
        checks.append({
            'name': 'Disk Alanı',
            'status': 'ok' if disk_ok else 'warning',
            'detail': f'{disk.free // (1024*1024)} MB boş'
        })
    except:
        checks.append({
            'name': 'Disk Alanı',
            'status': 'error',
            'detail': 'Okunamadı'
        })
    all_ok = all(c['status'] != 'error' for c in checks)
    return {'healthy': all_ok, 'checks': checks}


@router.get("/meta", summary="Arayüzün kullandığı sözlük ve sınırlar")
async def meta(container: ServiceContainer = Depends(get_container)):
    settings = container.settings
    return {
        "version": __version__,
        "document_types": [{"code": t.code, "label": t.label} for t in DOCUMENT_TYPES]
        + [{"code": UNKNOWN_DOCUMENT_TYPE, "label": "Belirlenemedi"}],
        "units": [{"code": u.code, "label": u.label, "description": u.description} for u in ORG_UNITS],
        "draft_types": [{"code": d.code, "label": d.label} for d in DRAFT_TYPES],
        "priorities": [{"code": p.code, "label": p.label, "rank": p.rank} for p in PRIORITIES],
        "pipeline_steps": [{"key": s.key, "label": s.label} for s in PIPELINE_STEPS],
        "limits": {
            "max_file_mb": settings.MAX_FILE_SIZE_MB,
            "min_text_chars": settings.MIN_TEXT_CHARS,
            "max_text_chars": settings.MAX_TEXT_CHARS,
            "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
            "keep_uploads": settings.KEEP_UPLOADS,
        },
    }


class MaskRequest(BaseModel):
    text: str


class MaskResponse(BaseModel):
    masked_text: str
    pii_count: int


@router.post("/mask-pii", response_model=MaskResponse, summary="Metindeki kişisel verileri maskele")
async def mask_pii(body: MaskRequest):
    detector = PIIDetector()
    findings = detector.detect(body.text)
    masked = detector.mask_text(body.text)
    return MaskResponse(masked_text=masked, pii_count=len(findings))


@router.post('/pii/analyze', tags=['Sistem'], summary='Metin PII analizi')
async def analyze_pii(body: dict, container: ServiceContainer = Depends(get_container)):
    text = body.get('text', '')
    if not text:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('text alani gereklidir.')
    pii = PIIDetector()
    findings = pii.detect(text)
    summary = pii.summary(text)
    masked = pii.mask_text(text)
    return {
        'findings': [{'type': f.type, 'label': f.label, 'start': f.start, 'end': f.end, 'severity': f.severity} for f in findings],
        'summary': summary,
        'masked_text': masked
    }


@router.post('/text/word-count', tags=['Sistem'], summary='Kelime sayimi')
async def word_count(body: dict):
    text = body.get('text', '')
    if not text:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('text alani gereklidir.')
    words = text.split()
    lines = text.count('\n') + 1
    chars = len(text)
    return {
        'word_count': len(words),
        'line_count': lines,
        'char_count': chars,
        'char_count_no_spaces': len(text.replace(' ', ''))
    }


@router.post('/text/extract-dates', tags=['Sistem'], summary='Tarih cikarma')
async def extract_dates(body: dict):
    import re
    text = body.get('text', '')
    if not text:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('text alani gereklidir.')
    patterns = [r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b', r'\b(\d{4})[-](\d{2})[-](\d{2})\b']
    dates = []
    for p in patterns:
        for m in re.finditer(p, text):
            dates.append({'match': m.group(), 'start': m.start(), 'end': m.end()})
    return {'dates': dates, 'count': len(dates)}


@router.post('/text/language-detect', tags=['Sistem'], summary='Dil tespiti')
async def detect_language(body: dict):
    text = body.get('text', '')
    if not text:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('text alani gereklidir.')
    tr_chars = set('çÇğĞıİöÖşŞüÜ')
    has_turkish = any(c in tr_chars for c in text)
    tr_words = ['ve', 'bir', 'bu', 'için', 'ile', 'olan', 'olarak', 'gibi', 'daha', 'ancak']
    words = text.lower().split()
    tr_word_count = sum(1 for w in words if w in tr_words)
    confidence = 0.5
    if has_turkish:
        confidence += 0.3
    if tr_word_count > 2:
        confidence += 0.2
    lang = 'tr' if confidence > 0.6 else 'unknown'
    return {
        'language': lang,
        'confidence': round(min(confidence, 1.0), 2),
        'has_turkish_chars': has_turkish,
        'turkish_word_count': tr_word_count
    }


@router.post('/validate-text', summary='Metin dogrulama')
async def validate_text(body: MaskRequest):
    issues = []
    if len(body.text.strip()) < 10:
        issues.append('Metin çok kısa (minimum 10 karakter).')
    if body.text.count('\n') > 500:
        issues.append('Metin çok fazla satır içeriyor.')
    from app.services.pii_detector import PIIDetector
    detector = PIIDetector()
    findings = detector.detect(body.text)
    if findings:
        issues.append(f'{len(findings)} adet kişisel veri tespit edildi.')
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'char_count': len(body.text),
        'line_count': body.text.count(chr(10)) + 1
    }


@router.get('/stats/summary', tags=['Sistem'], summary='Genel sistem ozeti')
async def system_summary(container: ServiceContainer = Depends(get_container)):
    from app.core.metrics import metrics
    hist_stats = container.history.stats()
    metric_snap = metrics.snapshot()
    return {
        'version': __version__,
        'total_analyses': hist_stats['total'],
        'avg_confidence': hist_stats.get('avg_confidence', 0),
        'favorites_count': hist_stats.get('favorites_count', 0),
        'total_requests': metric_snap['total_requests'],
        'error_rate': metric_snap.get('error_rate', 0),
        'uptime_seconds': metric_snap.get('uptime_seconds', 0),
        'document_types': hist_stats.get('by_type', {})
    }


@router.get('/stats/history-summary', summary='Gecmis ozet istatistikleri')
async def history_summary_stats(container: ServiceContainer = Depends(get_container)):
    stats = container.history.stats()
    page = container.history.list_records(limit=5, offset=0, sort='confidence_desc')
    top_records = [{'id': i['id'], 'source_name': i['source_name'], 'confidence_score': i['confidence_score']} for i in page['items']]
    return {'total': stats['total'], 'favorites_count': stats.get('favorites_count', 0), 'avg_confidence': stats.get('avg_confidence', 0), 'top_confidence': top_records}


@router.get("/stats/llm", summary="LLM kullanım istatistikleri")
async def llm_stats(container: ServiceContainer = Depends(get_container)):
    stats = container.llm.get_usage_stats()
    if stats.get("total_requests", 0) > 0 and stats.get("total_latency_ms", 0) > 0:
        stats["avg_latency_ms"] = round(stats["total_latency_ms"] / stats["total_requests"], 1)
    else:
        stats["avg_latency_ms"] = 0
    return stats


@router.get("/system-info", summary="Sistem yapılandırma bilgileri (yönetici)")
async def system_info(container: ServiceContainer = Depends(get_container)):
    import platform
    settings = container.settings

    warnings_list = []
    if not container.llm.is_configured:
        warnings_list.append("LLM API anahtarı yapılandırılmamış.")
    if not container.rag.available:
        warnings_list.append("RAG mevzuat indeksi yüklenmemiş.")
    try:
        disk = shutil.disk_usage(settings.history_path)
        if disk.free < settings.DISK_WARNING_THRESHOLD_MB * 1024 * 1024:
            warnings_list.append(f"Disk alanı düşük: {disk.free // (1024 * 1024)} MB kaldı.")
    except OSError:
        pass

    return {
        "version": __version__,
        "environment": container.settings.ENVIRONMENT,
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "uptime_human": _format_uptime(time.monotonic() - _start_time),
        "python_version": platform.python_version(),
        "warnings": warnings_list,
        "settings": {
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT,
            "llm_model": settings.LLM_MODEL,
            "llm_timeout": settings.LLM_TIMEOUT_SECONDS,
            "analysis_timeout": settings.ANALYSIS_TIMEOUT,
            "llm_cache_ttl": settings.LLM_CACHE_TTL_SECONDS,
            "pipeline_timeout": settings.PIPELINE_TIMEOUT_SECONDS,
            "max_file_mb": settings.MAX_FILE_SIZE_MB,
            "max_text_chars": settings.MAX_TEXT_CHARS,
            "max_concurrent_jobs": settings.MAX_CONCURRENT_JOBS,
            "rag_available": container.rag.available,
            "keep_uploads": settings.KEEP_UPLOADS,
            "rate_limit_requests": settings.RATE_LIMIT_REQUESTS,
            "rate_limit_window": settings.RATE_LIMIT_WINDOW,
            "csp_report_only": settings.CSP_REPORT_ONLY,
            "max_history_records": settings.MAX_HISTORY_RECORDS,
            "disk_warning_threshold_mb": settings.DISK_WARNING_THRESHOLD_MB,
        },
    }


@router.get("/stats/requests", summary="HTTP istek metrikleri")
async def request_stats():
    data = app_metrics.snapshot()
    data["error_rate"] = app_metrics.error_rate()
    return data


@router.get('/metrics/summary', tags=['Sistem'], summary='Metrik ozeti')
async def metrics_summary():
    from app.core.metrics import metrics
    snap = metrics.snapshot()
    return {
        'total_requests': snap['total_requests'],
        'error_rate': snap.get('error_rate', 0),
        'status_codes': snap.get('by_status', {}),
        'top_endpoints': snap.get('top_endpoints', []),
        'uptime_seconds': round(time.monotonic() - _start_time, 1)
    }


@router.get('/openapi-summary', tags=['Sistem'], summary='API endpoint ozeti')
async def openapi_summary(request: Request):
    from fastapi.openapi.utils import get_openapi
    openapi_schema = request.app.openapi()
    paths = openapi_schema.get('paths', {})
    endpoints = []
    for path, methods in paths.items():
        for method, details in methods.items():
            endpoints.append({
                'path': path,
                'method': method.upper(),
                'summary': details.get('summary', ''),
                'tags': details.get('tags', [])
            })
    return {'total_endpoints': len(endpoints), 'endpoints': endpoints}


@router.get("/health/llm", summary="LLM bağlantı testi")
async def llm_health(container: ServiceContainer = Depends(get_container)):
    if not container.llm.is_configured:
        return {"status": "unconfigured", "message": "LLM API anahtarı yapılandırılmamış."}
    reachable = await container.llm.ping()
    return {
        "status": "ok" if reachable else "unreachable",
        "model": container.llm.model,
        "api_base": container.llm.api_base,
    }


@router.get("/health/detailed", summary="Detaylı sağlık kontrolleri")
async def health_detailed(container: ServiceContainer = Depends(get_container)):
    """Tüm alt sistem sağlık kontrollerini tek yanıtta döndürür."""
    import shutil
    checks = {}
    
    # LLM kontrolü
    checks["llm"] = {
        "configured": container.llm.is_configured,
        "circuit_breaker_closed": not container.llm._breaker.is_open,
    }
    
    # Depolama kontrolü
    try:
        disk = shutil.disk_usage(container.settings.history_path)
        checks["storage"] = {
            "writable": container.settings.history_path.exists(),
            "free_mb": round(disk.free / (1024 * 1024), 1),
            "warning": disk.free < container.settings.DISK_WARNING_THRESHOLD_MB * 1024 * 1024,
        }
    except OSError:
        checks["storage"] = {"writable": False, "free_mb": None, "warning": True}
    
    # RAG kontrolü
    checks["rag"] = {
        "available": container.rag.available,
        "chunks": container.rag.chunk_count,
    }
    
    all_ok = (
        checks["llm"]["configured"]
        and checks["llm"]["circuit_breaker_closed"]
        and checks["storage"]["writable"]
        and not checks["storage"]["warning"]
    )
    
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )


@router.get('/config/allowed-types', tags=['Sistem'], summary='Izin verilen dosya turleri')
async def allowed_file_types(container: ServiceContainer = Depends(get_container)):
    types = [t.strip() for t in container.settings.ALLOWED_FILE_TYPES.split(',')]
    return {'types': types, 'count': len(types)}


@router.get("/config/export", summary="Çalışma zamanı yapılandırma dışa aktarımı", dependencies=[Depends(require_admin)])
async def config_export(container: ServiceContainer = Depends(get_container)):
    """Hassas olmayan yapılandırma değerlerini dışa aktarır (sorun giderme için)."""
    settings = container.settings
    return {
        "app_name": settings.APP_NAME,
        "version": __version__,
        "environment": container.settings.ENVIRONMENT,
        "maintenance_mode": container.settings.MAINTENANCE_MODE,
        "log_level": settings.LOG_LEVEL,
        "log_format": settings.LOG_FORMAT,
        "llm_model": settings.LLM_MODEL,
        "llm_configured": container.llm.is_configured,
        "llm_timeout": settings.LLM_TIMEOUT_SECONDS,
        "llm_max_retries": settings.LLM_MAX_RETRIES,
        "llm_cache_ttl": settings.LLM_CACHE_TTL_SECONDS,
        "llm_token_budget": settings.LLM_TOKEN_BUDGET,
        "pipeline_timeout": settings.PIPELINE_TIMEOUT_SECONDS,
        "max_file_mb": settings.MAX_FILE_SIZE_MB,
        "min_text_chars": settings.MIN_TEXT_CHARS,
        "max_text_chars": settings.MAX_TEXT_CHARS,
        "max_batch_files": settings.MAX_BATCH_FILES,
        "rag_available": container.rag.available,
        "rag_chunks": container.rag.chunk_count,
        "rate_limit": f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_WINDOW}s",
        "csp_report_only": settings.CSP_REPORT_ONLY,
        "keep_uploads": settings.KEEP_UPLOADS,
        "cache_entries": container.llm.get_usage_stats().get("cache_size", 0),
    }


@router.get('/config/validate', tags=['Sistem'], summary='Yapilandirma dogrulama')
async def validate_config(container: ServiceContainer = Depends(get_container), _admin=Depends(require_admin)):
    issues = []
    settings = container.settings
    if not settings.ADMIN_TOKEN:
        issues.append('ADMIN_TOKEN ayarlanmamis')
    if settings.RATE_LIMIT_REQUESTS < 10:
        issues.append('Rate limit cok dusuk')
    if settings.LLM_TIMEOUT_SECONDS < 10:
        issues.append('LLM timeout cok dusuk')
    if settings.MAX_FILE_SIZE_MB > 100:
        issues.append('Dosya boyutu limiti cok yuksek')
    valid = len(issues) == 0
    return {'valid': valid, 'issues': issues, 'checked_fields': 4}


@router.post("/cache/clear", summary="LLM önbelleğini temizle", dependencies=[Depends(require_admin)])
async def clear_cache(container: ServiceContainer = Depends(get_container)):
    """LLM yanıt önbelleğini temizler."""
    stats_before = container.llm.get_usage_stats()
    container.llm._cache.clear()
    return {
        "cleared": True,
        "entries_removed": stats_before.get("cache_size", 0),
    }


@router.post('/cache/stats', tags=['Sistem'], summary='Cache istatistikleri')
async def cache_stats(container: ServiceContainer = Depends(get_container), _admin=Depends(require_admin)):
    cache = container.llm._cache
    info = cache.stats()
    return {'cache_size': info.get('cache_size', 0), 'ttl_seconds': info.get('ttl_seconds', 0)}


@router.post('/logs/query', tags=['Sistem'], summary='Log sorgulama')
async def query_logs(level: str = Query('INFO'), limit: int = Query(50, ge=1, le=500), _admin=Depends(require_admin)):
    import logging
    logger = logging.getLogger()
    handlers = [h for h in logger.handlers if hasattr(h, 'baseFilename')]
    if not handlers:
        return {'logs': [], 'message': 'Dosya log handler bulunamadi'}
    import os
    filepath = handlers[0].baseFilename
    if not os.path.exists(filepath):
        return {'logs': [], 'message': 'Log dosyasi bulunamadi'}
    lines = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if level.upper() in line.upper():
                lines.append(line.strip())
    return {'logs': lines[-limit:], 'total_matched': len(lines), 'level_filter': level}
