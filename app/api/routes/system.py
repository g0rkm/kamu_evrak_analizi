import shutil
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Header
from fastapi.responses import JSONResponse
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
from app.core.exceptions import NotFoundError

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


def verify_admin(request: Request, container: ServiceContainer = Depends(get_container)) -> bool:
    admin_token = container.settings.ADMIN_TOKEN
    if not admin_token:
        return True
    auth = request.headers.get('Authorization', '')
    if auth == f'Bearer {admin_token}':
        return True
    from app.core.exceptions import AuthorizationError
    raise AuthorizationError('Admin yetkisi gerekli')


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


@router.get('/health/comprehensive', tags=['Saglik'], summary='Kapsamli saglik kontrolu')
async def comprehensive_health(request: Request, container: ServiceContainer = Depends(get_container)):
    import time as time_mod
    from app.core.metrics import metrics
    uptime = time_mod.time() - getattr(request.app.state, 'startup_time', time_mod.time())
    snapshot = metrics.snapshot()
    health = metrics.health_summary()
    audit = getattr(container, 'audit', None)
    audit_ok = audit is not None
    backup = getattr(container, 'backup', None)
    backup_ok = backup is not None
    return {
        'status': health['status'],
        'uptime_seconds': round(uptime, 1),
        'metrics': {
            'total_requests': snapshot['total_requests'],
            'error_rate': snapshot['error_rate'],
            'avg_response_time_ms': snapshot['avg_response_time_ms']
        },
        'services': {
            'llm': container.llm is not None,
            'audit_logger': audit_ok,
            'backup_service': backup_ok,
            'rag_available': hasattr(container, 'rag')
        },
        'version': container.settings.ENVIRONMENT
    }


@router.get('/system/capabilities', tags=['Sistem'], summary='Sistem yetenekleri')
async def system_capabilities(request: Request, container: ServiceContainer = Depends(get_container)):
    return {
        'features': {
            'file_analysis': True,
            'pii_detection': True,
            'audit_logging': getattr(container, 'audit', None) is not None,
            'backup': getattr(container, 'backup', None) is not None,
            'rate_limiting': True,
            'soft_delete': True,
            'bulk_operations': True,
            'csv_export': True,
            'json_export': True,
            'timeline_view': True,
            'duplicate_detection': True,
            'content_search': True
        },
        'limits': {
            'max_file_size_mb': container.settings.MAX_FILE_SIZE_MB,
            'max_tags_per_record': container.settings.MAX_TAGS_PER_RECORD,
            'max_note_length': container.settings.MAX_NOTE_LENGTH,
            'rate_limit': f'{container.settings.RATE_LIMIT_REQUESTS}/{container.settings.RATE_LIMIT_WINDOW}s'
        }
    }


@router.get('/system/report', tags=['Sistem'], summary='Tam sistem raporu')
async def system_report(request: Request, container: ServiceContainer = Depends(get_container)):
    import time as time_mod
    from app.core.metrics import metrics
    from app import __version__
    uptime = time_mod.time() - getattr(request.app.state, 'startup_time', time_mod.time())
    snapshot = metrics.snapshot()
    health = metrics.health_summary()
    s = container.settings
    return {
        'version': __version__,
        'environment': s.ENVIRONMENT,
        'uptime_seconds': round(uptime, 1),
        'health': health,
        'metrics': snapshot,
        'configuration': {
            'rate_limit': f'{s.RATE_LIMIT_REQUESTS}/{s.RATE_LIMIT_WINDOW}s',
            'max_file_size_mb': s.MAX_FILE_SIZE_MB,
            'maintenance_mode': s.MAINTENANCE_MODE
        },
        'services': {
            'llm': container.llm is not None,
            'audit': getattr(container, 'audit', None) is not None,
            'backup': getattr(container, 'backup', None) is not None
        }
    }


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
async def startup_checks(container: ServiceContainer = Depends(get_container), request: Request = None):
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
    audit = getattr(request.app.state.container, 'audit', None) if request else None
    checks.append({
        'name': 'audit_logger',
        'status': 'ok' if audit else 'warning',
        'detail': 'Aktif' if audit else 'Yapilandirilmamis'
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
    try:
        disk_root = shutil.disk_usage('/')
        free_mb = disk_root.free // (1024 * 1024)
        disk_ok_root = free_mb > container.settings.DISK_WARNING_THRESHOLD_MB
        checks.append({'name': 'disk_space', 'status': 'ok' if disk_ok_root else 'warning', 'detail': f'{free_mb} MB boş alan'})
    except:
        pass

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


@router.post('/text/summarize-stats', tags=['Sistem'], summary='Metin istatistikleri')
async def text_statistics(body: dict):
    import re
    text = body.get('text', '')
    if not text:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('text alani gereklidir.')
    words = text.split()
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    avg_word_len = round(sum(len(w) for w in words) / len(words), 1) if words else 0
    return {
        'word_count': len(words),
        'sentence_count': len(sentences),
        'paragraph_count': len(paragraphs),
        'avg_word_length': avg_word_len,
        'unique_words': len(set(w.lower() for w in words)),
        'char_count': len(text)
    }


@router.post('/text/analyze', tags=['Metin'], summary='Detayli metin analizi')
async def analyze_text_detailed(request: Request, body: dict):
    from app.services.text_analyzer import TextAnalyzer
    text = body.get('text', '')
    result = TextAnalyzer.analyze(text)
    return result


@router.post('/text/detect-type', tags=['Metin'], summary='Metin turunu tahmin et')
async def detect_text_type(request: Request, body: dict):
    text = body.get('text', '').lower()
    if not text:
        return {'detected_type': 'bilinmiyor', 'confidence': 0}
    type_keywords = {
        'dilekce': ['sayin', 'rica ederim', 'basvuru', 'talep', 'dilekce', 'baskanligina'],
        'rapor': ['rapor', 'sonuc', 'analiz', 'degerlendirme', 'bulgular', 'tespit'],
        'sartname': ['sartname', 'teknik', 'idari', 'madde', 'yeterlilik', 'ihale'],
        'tutanak': ['tutanak', 'karar', 'toplanti', 'gundem', 'oy', 'katilimci'],
        'sozlesme': ['sozlesme', 'taraflar', 'yukumluluk', 'madde', 'suresi', 'taahhut']
    }
    scores = {}
    for doc_type, keywords in type_keywords.items():
        count = sum(1 for kw in keywords if kw in text)
        scores[doc_type] = count / len(keywords)
    best_type = max(scores, key=scores.get) if scores else 'bilinmiyor'
    best_score = scores.get(best_type, 0)
    return {
        'detected_type': best_type if best_score > 0 else 'bilinmiyor',
        'confidence': round(best_score, 3),
        'all_scores': {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)}
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


@router.post('/text/keywords', tags=['Sistem'], summary='Anahtar kelime cikarma')
async def extract_keywords(body: dict):
    import re
    from collections import Counter
    text = body.get('text', '')
    if not text:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('text alani gereklidir.')
    stop_words = {'ve', 'bir', 'bu', 'de', 'da', 'ile', 'için', 'olan', 'gibi', 'daha', 'en', 'her', 'ne', 'ki', 'var', 'o', 'ben', 'sen', 'biz', 'siz', 'onlar', 'ama', 'fakat', 'ancak', 'veya', 'ya', 'hem', 'ise', 'mi', 'mu'}
    words = re.findall(r'\b[a-zçğıöşüA-ZÇĞİÖŞÜ]{3,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    counts = Counter(filtered)
    top_keywords = [{'word': w, 'count': c} for w, c in counts.most_common(20)]
    return {'keywords': top_keywords, 'total_words': len(words), 'unique_words': len(set(filtered))}


@router.post('/text/sanitize', tags=['Sistem'], summary='Metin temizleme')
async def sanitize_text(body: dict):
    import re
    text = body.get('text', '')
    if not text:
        from app.core.exceptions import InvalidInputError
        raise InvalidInputError('text alani gereklidir.')
    sanitized = text
    sanitized = re.sub(r'<[^>]+>', '', sanitized)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', sanitized)
    sanitized = sanitized.strip()
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    sanitized = re.sub(r' {2,}', ' ', sanitized)
    return {
        'original_length': len(text),
        'sanitized_length': len(sanitized),
        'sanitized_text': sanitized,
        'changes_made': len(text) != len(sanitized)
    }


@router.post('/text/compare', tags=['Metin'], summary='Iki metni karsilastir')
async def compare_texts(request: Request, body: dict):
    text1 = body.get('text1', '')
    text2 = body.get('text2', '')
    if not text1 or not text2:
        return {'error': 'text1 ve text2 gerekli'}
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    common = words1 & words2
    all_words = words1 | words2
    jaccard = len(common) / len(all_words) if all_words else 0
    only1 = words1 - words2
    only2 = words2 - words1
    return {
        'similarity_score': round(jaccard, 4),
        'common_words': list(common)[:20],
        'unique_to_text1': list(only1)[:20],
        'unique_to_text2': list(only2)[:20],
        'text1_word_count': len(words1),
        'text2_word_count': len(words2)
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
async def system_info(request: Request, container: ServiceContainer = Depends(get_container)):
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

    import time
    uptime = time.time() - getattr(request.app.state, 'startup_time', time.time())

    return {
        "version": __version__,
        "environment": container.settings.ENVIRONMENT,
        "uptime_seconds": round(uptime, 1),
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
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
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


@router.get('/metrics/errors', tags=['Metrikler'], summary='Hata metrikleri')
async def error_metrics(request: Request, container: ServiceContainer = Depends(get_container)):
    from app.core.metrics import metrics
    snapshot = metrics.snapshot()
    status_dist = metrics.status_code_distribution()
    total_errors = snapshot['total_errors']
    total_req = snapshot['total_requests']
    return {
        'total_errors': total_errors,
        'error_rate': snapshot['error_rate'],
        'client_errors_4xx': status_dist.get('4xx', 0),
        'server_errors_5xx': status_dist.get('5xx', 0),
        'status_distribution': status_dist.get('distribution', {}),
        'total_requests': total_req,
        'health_status': metrics.health_summary()['status']
    }


@router.get('/metrics/endpoints', tags=['Metrikler'], summary='Endpoint bazli metrikler')
async def endpoint_metrics(request: Request, container: ServiceContainer = Depends(get_container)):
    from app.core.metrics import metrics
    snapshot = metrics.snapshot()
    top = snapshot.get('top_endpoints', {})
    result = []
    for ep, count in top.items():
        result.append({
            'endpoint': ep,
            'request_count': count,
            'percentage': round(count / max(snapshot['total_requests'], 1) * 100, 1)
        })
    return {
        'endpoints': result,
        'total_requests': snapshot['total_requests'],
        'avg_response_time_ms': snapshot['avg_response_time_ms']
    }


@router.get('/metrics/status-codes', tags=['Sistem'], summary='HTTP durum kodu dagilimi')
async def status_codes_distribution():
    from app.core.metrics import metrics
    return metrics.status_code_distribution()


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


@router.get('/api-docs-summary', tags=['Sistem'], summary='API dokumantasyon ozeti')
async def api_docs_summary():
    return {
        'documentation': {
            'swagger_ui': '/docs',
            'redoc': '/redoc',
            'openapi_json': '/openapi.json'
        },
        'endpoints_summary': {
            'system': 'Sistem saglik kontrolleri, metrikler, yapilandirma',
            'history': 'Analiz gecmisi, arama, filtreleme, disari aktarma',
            'analysis': 'Belge analizi ve siniflandirma',
            'text': 'Metin isleme: PII tespiti, kelime sayimi, tarih cikarma, dil tespiti'
        }
    }


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
async def health_detailed(request: Request, container: ServiceContainer = Depends(get_container)):
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

    # Audit logger kontrolü
    audit = getattr(request.app.state.container, 'audit', None)
    checks["audit_logger"] = audit is not None
    
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


@router.get('/health/data-integrity', tags=['Saglik'], summary='Veri butunlugu kontrolu')
async def data_integrity_check(request: Request, container: ServiceContainer = Depends(get_container)):
    repo = container.history
    all_records = repo._load_all()
    issues = []
    total = len(all_records)
    for r in all_records:
        rid = r.get('id', '')
        if not rid:
            issues.append({'type': 'missing_id', 'detail': 'ID alani eksik'})
            continue
        if not r.get('file_name'):
            issues.append({'type': 'missing_file_name', 'record_id': rid})
        if not r.get('status'):
            issues.append({'type': 'missing_status', 'record_id': rid})
    return {
        'total_records': total,
        'issues_found': len(issues),
        'issues': issues[:50],
        'status': 'healthy' if not issues else 'issues_detected'
    }


@router.post("/integrity/verify/{record_id}", tags=["Sistem"])
async def verify_record_integrity(record_id: str, request: Request, container: ServiceContainer = Depends(get_container)):
    record = container.history.get(record_id)
    if not record:
        raise NotFoundError(f"Kayit bulunamadi: {record_id}")
    result = container.integrity.verify_record_integrity(record)
    result["record_id"] = record_id
    return result


@router.post("/integrity/verify-all", tags=["Sistem"])
async def verify_all_integrity(request: Request, container: ServiceContainer = Depends(get_container)):
    records = container.history._load_all()
    results = {"total": len(records), "valid": 0, "invalid": 0, "issues": []}
    for record in records:
        if record.get("deleted"):
            continue
        check = container.integrity.verify_record_integrity(record)
        if check["valid"]:
            results["valid"] += 1
        else:
            results["invalid"] += 1
            results["issues"].append({"record_id": record.get("id"), "issues": check["issues"]})
    return results


@router.get('/health/storage', tags=['Saglik'], summary='Depolama durumu')
async def storage_health(request: Request, container: ServiceContainer = Depends(get_container)):
    import shutil
    disk = shutil.disk_usage('/')
    history_dir = Path(container.settings.HISTORY_DIR) if hasattr(container.settings, 'HISTORY_DIR') else container.settings.history_path
    file_count = len(list(history_dir.glob('*.json'))) if history_dir.exists() else 0
    return {
        'disk_free_mb': disk.free // (1024 * 1024),
        'disk_total_mb': disk.total // (1024 * 1024),
        'disk_usage_percent': round(disk.used / disk.total * 100, 1),
        'history_file_count': file_count,
        'warning_threshold_mb': container.settings.DISK_WARNING_THRESHOLD_MB,
        'status': 'ok' if disk.free // (1024 * 1024) > container.settings.DISK_WARNING_THRESHOLD_MB else 'warning'
    }


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
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
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


@router.post("/cache/clear", summary="LLM önbelleğini temizle")
async def clear_cache(container: ServiceContainer = Depends(get_container), admin: bool = Depends(verify_admin)):
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


@router.get('/error-codes', tags=['Sistem'], summary='Hata kodlari listesi')
async def error_codes():
    from app.core.exceptions import AppError
    errors = {
        'invalid_input': {'status': 400, 'description': 'Gecersiz istek parametreleri'},
        'not_found': {'status': 404, 'description': 'Kaynak bulunamadi'},
        'rate_limit_exceeded': {'status': 429, 'description': 'Istek limiti asildi'},
        'token_budget_exceeded': {'status': 429, 'description': 'Token butcesi asildi'},
        'llm_unavailable': {'status': 503, 'description': 'LLM servisi kulanilamiyor'},
        'circuit_breaker_open': {'status': 503, 'description': 'Devre kesici acik'},
        'pipeline_timeout': {'status': 504, 'description': 'Islem zaman asimi'},
        'maintenance_mode': {'status': 503, 'description': 'Bakim modu aktif'},
        'storage_error': {'status': 500, 'description': 'Dosya sistemi hatasi'},
        'configuration_error': {'status': 500, 'description': 'Yapilandirma hatasi'},
        'file_validation_error': {'status': 400, 'description': 'Dosya dogrulama hatasi'},
        'duplicate_record': {'status': 409, 'description': 'Cakisan kayit'}
    }
    return {'error_codes': errors, 'total': len(errors)}


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


@router.get('/audit/logs', tags=['Sistem'], summary='Denetim gunlugu sorgula')
async def query_audit_logs(request: Request, limit: int = 100, action: str = None, record_id: str = None, admin: bool = Depends(verify_admin)):
    audit = getattr(request.app.state.container, 'audit', None)
    if not audit:
        return {'logs': [], 'message': 'Audit logger not configured'}
    logs = audit.get_logs(limit=limit, action=action, record_id=record_id)
    return {'logs': logs, 'total': len(logs)}


@router.get('/audit/stats')
async def audit_stats(request: Request):
    audit = getattr(request.app.state.container, 'audit', None)
    if not audit:
        return {}
    return audit.stats()


@router.get('/cors-info', tags=['Sistem'], summary='CORS yapilandirmasi')
async def cors_info(container: ServiceContainer = Depends(get_container)):
    return {
        'cors_enabled': bool(container.settings.CORS_ORIGINS),
        'allowed_origins': container.settings.CORS_ORIGINS,
        'allowed_methods': ['GET', 'POST', 'PATCH', 'DELETE'],
        'allowed_headers': ['Content-Type']
    }


@router.get('/rate-limit-status', tags=['Sistem'], summary='Rate limit durumu')
async def rate_limit_status(request: Request, container: ServiceContainer = Depends(get_container)):
    from app.core.rate_limit import RateLimiter
    client_ip = request.client.host if request.client else 'unknown'
    settings = container.settings
    
    # RateLimiter middleware erisimi deneniyor
    limiter = getattr(request.app.state, 'rate_limiter', None)
    if not limiter:
        for mw in getattr(request.app, 'user_middleware', []):
            if hasattr(mw, 'cls') and mw.cls == RateLimiter:
                pass

    return {
        'client_ip': client_ip,
        'max_requests': settings.RATE_LIMIT_REQUESTS,
        'window_seconds': settings.RATE_LIMIT_WINDOW,
        'active_clients': 'N/A',
        'your_status': 'Rate limiting aktif',
        'limit_per_minute': round(settings.RATE_LIMIT_REQUESTS / settings.RATE_LIMIT_WINDOW * 60, 1)
    }


@router.get("/rate-limit/info", tags=["Sistem"])
async def rate_limit_info(request: Request, container: ServiceContainer = Depends(get_container)):
    from app.core.rate_limit import get_client_info
    info = get_client_info(request)
    return info


@router.get("/dashboard/summary", tags=["Sistem"])
async def dashboard_summary(request: Request, container: ServiceContainer = Depends(get_container)):
    import time
    records = container.history._load_all()
    active = [r for r in records if not r.get("deleted")]
    deleted = [r for r in records if r.get("deleted")]
    archived = [r for r in active if r.get("archived")]
    favorited = [r for r in active if r.get("favorite")]
    priority_counts = {}
    for r in active:
        p = r.get("priority", "normal")
        priority_counts[p] = priority_counts.get(p, 0) + 1
    uptime = time.time() - getattr(request.app.state, "startup_time", time.time())
    summary = {
        "total_records": len(records),
        "active_records": len(active),
        "deleted_records": len(deleted),
        "archived_records": len(archived),
        "favorited_records": len(favorited),
        "priority_distribution": priority_counts,
        "uptime_seconds": round(uptime, 1),
    }
    if container.notifications:
        summary["unread_notifications"] = container.notifications.unread_count()
    if container.audit:
        stats = container.audit.stats()
        summary["audit_log_count"] = stats.get("total_logs", 0)
    return summary


@router.get('/security-headers', tags=['Sistem'], summary='Guvenlik basliklari kontrol')
async def security_headers_check(request: Request):
    return {
        'headers': {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'Referrer-Policy': 'same-origin',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
        },
        'csp_enabled': True,
        'csrf_protection': True,
        'rate_limiting': True
    }


@router.post('/backup/create', tags=['Yedekleme'], summary='Yedek olustur')
async def create_backup(request: Request, container: ServiceContainer = Depends(get_container), admin: bool = Depends(verify_admin)):
    backup = getattr(container, 'backup', None)
    if not backup:
        return JSONResponse(status_code=503, content={'detail': 'Backup service not configured'})
    result = backup.create_backup()
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('backup_create', details={'file': result.get('backup_file', '')})
    return result


@router.get('/backup/list', tags=['Yedekleme'])
async def list_backups(request: Request, container: ServiceContainer = Depends(get_container)):
    backup = getattr(container, 'backup', None)
    if not backup:
        return {'backups': []}
    return {'backups': backup.list_backups()}


@router.post('/backup/cleanup', tags=['Yedekleme'])
async def cleanup_backups(request: Request, keep: int = 5, container: ServiceContainer = Depends(get_container), admin: bool = Depends(verify_admin)):
    backup = getattr(container, 'backup', None)
    if not backup:
        return {'deleted': 0}
    deleted = backup.delete_old_backups(keep_count=keep)
    return {'deleted': deleted}


@router.post('/webhooks/register', tags=['Webhook'], summary='Webhook kaydet')
async def register_webhook(request: Request, body: dict, container: ServiceContainer = Depends(get_container)):
    wh = getattr(container, 'webhooks', None)
    if not wh:
        return {'error': 'Webhook service not configured'}
    url = body.get('url', '')
    if not url:
        return JSONResponse(status_code=400, content={'detail': 'url gerekli'})
    result = wh.register(url=url, events=body.get('events'), name=body.get('name', ''))
    return result


@router.get('/webhooks/list', tags=['Webhook'])
async def list_webhooks(request: Request, container: ServiceContainer = Depends(get_container)):
    wh = getattr(container, 'webhooks', None)
    if not wh:
        return {'webhooks': []}
    return {'webhooks': wh.list_webhooks()}


@router.get('/webhooks/history', tags=['Webhook'])
async def webhook_history(request: Request, limit: int = 50, container: ServiceContainer = Depends(get_container)):
    wh = getattr(container, 'webhooks', None)
    if not wh:
        return {'history': []}
    return {'history': wh.history(limit=limit)}


@router.post('/maintenance/cleanup-deleted', tags=['Bakim'], summary='Silinen kayitlari kalici olarak temizle')
async def cleanup_deleted(request: Request, days: int = 30, container: ServiceContainer = Depends(get_container), admin: bool = Depends(verify_admin)):
    from datetime import datetime, timedelta
    records = container.history._load_all()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cleaned = 0
    for r in records:
        if r.get('deleted') and r.get('deleted_at', '') < cutoff:
            rid = r.get('id')
            if rid:
                path = container.history.directory / f'{rid}.json'
                if path.exists():
                    path.unlink()
                    cleaned += 1
    audit = getattr(container, 'audit', None)
    if audit:
        audit.log('cleanup_deleted', details={'cleaned': cleaned, 'older_than_days': days})
    return {'cleaned': cleaned, 'older_than_days': days}


@router.post('/maintenance/cleanup-audit', tags=['Bakim'], summary='Eski audit loglarini temizle')
async def cleanup_audit_logs(request: Request, days: int = 90, container: ServiceContainer = Depends(get_container), admin: bool = Depends(verify_admin)):
    audit = getattr(container, 'audit', None)
    if not audit:
        return {'removed': 0}
    removed = audit.clear_old_logs(days=days)
    return {'removed': removed, 'older_than_days': days}


@router.get("/notifications", tags=["Sistem"])
async def get_notifications(request: Request, limit: int = 50, level: str = None, unread_only: bool = False, container: ServiceContainer = Depends(get_container)):
    if not container.notifications:
        return {"notifications": [], "count": 0}
    notifications = container.notifications.get_notifications(limit=limit, level=level, unread_only=unread_only)
    return {"notifications": notifications, "count": len(notifications)}


@router.post("/notifications/mark-read", tags=["Sistem"])
async def mark_notifications_read(request: Request, container: ServiceContainer = Depends(get_container)):
    if not container.notifications:
        return {"marked": 0}
    count = container.notifications.mark_all_read()
    return {"marked": count}


@router.get("/notifications/stats", tags=["Sistem"])
async def notification_stats(request: Request, container: ServiceContainer = Depends(get_container)):
    if not container.notifications:
        return {"total": 0, "unread": 0, "by_level": {}}
    return container.notifications.stats()
