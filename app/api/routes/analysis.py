"""Senkron analiz uç noktaları (API istemcileri ve betikler için)."""
import asyncio
import hashlib
import json
import logging
import time
from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies import get_analysis_service, get_container, get_storage
from app.container import ServiceContainer
from app.core.exceptions import AppError, InvalidInputError, PipelineTimeoutError
from app.models.api import (
    AnalysisResponse, BatchItem, BatchResponse, CompareRequest, ComparisonResult, TextAnalysisRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.upload_storage import UploadStorage

router = APIRouter(tags=["analiz"])
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalysisResponse, summary="Dosya yükleyerek analiz et")
async def analyze_document(
    request: Request,
    file: UploadFile = File(...),
    storage: UploadStorage = Depends(get_storage),
    service: AnalysisService = Depends(get_analysis_service),
    container: ServiceContainer = Depends(get_container),
):
    stored = await storage.save(file)
    try:
        # Dosya içeriğini okuyup content_hash hesapla ve deduplication kontrolü yap
        content = getattr(stored, "content", None)
        if content is None:
            # Eğer stored objesinde content doğrudan yoksa dosya yolundan okumayı deneyebiliriz ya da okunduğunu varsayabiliriz
            # Ancak standart akışta stored üzerinden ilerlenir. Güvenli okuma için:
            if hasattr(stored, "read_bytes"):
                content_bytes = await stored.read_bytes()
            elif hasattr(stored, "path") and stored.path:
                with open(stored.path, "rb") as f:
                    content_bytes = f.read()
            else:
                content_bytes = b""
            content_hash = hashlib.sha256(content_bytes).hexdigest()
        else:
            if isinstance(content, str):
                content_bytes = content.encode()
            else:
                content_bytes = content
            content_hash = hashlib.sha256(content_bytes).hexdigest()

        dedup_key = container.llm._cache.deduplicate_key(content_hash)
        if dedup_key:
            cached = container.llm._cache.get(dedup_key)
            if cached:
                return cached

        result = await asyncio.wait_for(service.analyze_file(stored), timeout=float(container.settings.ANALYSIS_TIMEOUT))
        
        # Başarılı sonuç sonrası cache/dedup kaydı
        if result:
            result_hash = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
            container.llm._cache.set_dedup(content_hash, 'llm:' + content_hash)
            
        audit = getattr(request.app.state.container, 'audit', None)
        if audit:
            audit.log('analyze', record_id=result.get('id', ''), details={'file_name': file.filename, 'document_type': result.get('classification', {}).get('document_type', '')})

        return result
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("Analiz pipeline süresi aşıldı (dosya: %s)", getattr(stored, "filename", "bilinmiyor"))
        raise PipelineTimeoutError()


@router.post("/analyze-text", response_model=AnalysisResponse, summary="Düz metin olarak analiz et")
async def analyze_text(body: TextAnalysisRequest, service: AnalysisService = Depends(get_analysis_service)):
    return await service.analyze_text(body.text, body.title)


@router.post("/analyze-batch", response_model=BatchResponse, summary="Birden çok dosyayı sırayla analiz et")
async def analyze_batch(
    files: list[UploadFile] = File(...),
    container: ServiceContainer = Depends(get_container),
):
    limit = container.settings.MAX_BATCH_FILES
    if len(files) > limit:
        raise InvalidInputError(f"Tek seferde en fazla {limit} dosya yüklenebilir.")

    batch_logger = logging.getLogger("api.batch")
    batch_logger.info("Toplu analiz başlatıldı: %d dosya (limit: %d)", len(files), limit)

    results: list[BatchItem] = []
    for upload in files:
        name = container.storage.display_name(upload.filename)
        try:
            stored = await container.storage.save(upload)
            payload = await container.analysis.analyze_file(stored)
        except AppError as exc:
            results.append(BatchItem(filename=name, status="error", detail=exc.message))
            continue
        results.append(BatchItem(
            filename=name,
            status=payload["status"],
            history_id=payload["history_id"],
            document_type=payload["analysis"]["classification"]["document_type"],
            confidence_score=payload["confidence_score"],
        ))
    return BatchResponse(total=len(results), results=results)


@router.post("/compare", response_model=ComparisonResult, summary="İki evrak metnini karşılaştır")
async def compare_documents(body: CompareRequest, service: AnalysisService = Depends(get_analysis_service)):
    return await service.compare(body.text1, body.text2)
