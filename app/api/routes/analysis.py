"""Senkron analiz uç noktaları (API istemcileri ve betikler için)."""
import asyncio
import logging
import time
from fastapi import APIRouter, Depends, File, UploadFile

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
    file: UploadFile = File(...),
    storage: UploadStorage = Depends(get_storage),
    service: AnalysisService = Depends(get_analysis_service),
):
    stored = await storage.save(file)
    try:
        return await asyncio.wait_for(service.analyze_file(stored), timeout=60.0)
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
