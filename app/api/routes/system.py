import shutil
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import __version__
from app.agents.orchestrator import PIPELINE_STEPS
from app.api.dependencies import get_container
from app.container import ServiceContainer
from app.core.taxonomy import DOCUMENT_TYPES, DRAFT_TYPES, ORG_UNITS, PRIORITIES, UNKNOWN_DOCUMENT_TYPE
from app.models.api import HealthStatus
from app.services.pii_detector import PIIDetector
from app.services.upload_storage import ALLOWED_EXTENSIONS

router = APIRouter(tags=["sistem"])
_start_time = time.monotonic()


@router.get("/health", response_model=HealthStatus, summary="Sistem sağlık kontrolü")
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
    elif disk_free_mb is not None and disk_free_mb < 50:
        status = "warning"

    return HealthStatus(
        status=status,
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
    )


@router.get("/ready", summary="Hazırlık kontrolü (readiness probe)")
async def readiness_check(container: ServiceContainer = Depends(get_container)):
    checks = {
        "llm_configured": container.llm.is_configured,
        "history_writable": container.settings.history_path.exists(),
    }
    all_ok = all(checks.values())
    return {"ready": all_ok, "checks": checks}


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


@router.get("/stats/llm", summary="LLM kullanım istatistikleri")
async def llm_stats(container: ServiceContainer = Depends(get_container)):
    return container.llm.get_usage_stats()


@router.get("/system-info", summary="Sistem yapılandırma bilgileri (yönetici)")
async def system_info(container: ServiceContainer = Depends(get_container)):
    import platform
    settings = container.settings
    return {
        "version": __version__,
        "python_version": platform.python_version(),
        "settings": {
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT,
            "llm_model": settings.LLM_MODEL,
            "llm_timeout": settings.LLM_TIMEOUT_SECONDS,
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
        },
    }
