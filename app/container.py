"""Uygulama ömrü boyunca paylaşılan servislerin kurulduğu bağımlılık container'ı."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.services.analysis_service import AnalysisService
from app.services.history_repository import HistoryRepository
from app.services.job_manager import JobManager
from app.services.legislation_catalog import LegislationCatalog
from app.services.llm_service import LLMService
from app.services.ocr_service import OCRService
from app.services.rag_service import RAGService
from app.services.upload_storage import UploadStorage


@dataclass
class ServiceContainer:
    settings: Settings
    llm: LLMService
    rag: RAGService
    legislation: LegislationCatalog
    ocr: OCRService
    history: HistoryRepository
    storage: UploadStorage
    analysis: AnalysisService
    jobs: JobManager
    integrity: Any = None
    notifications: Any = None
    templates: Any = None
    auth: Any = None
    scheduler: Any = None

    @classmethod
    def build(cls, settings: Settings) -> ServiceContainer:
        llm = LLMService(settings)
        rag = RAGService(settings.rag_index_path, settings.RAG_TOP_K)
        legislation = LegislationCatalog.load()
        ocr = OCRService(settings)
        history = HistoryRepository(settings.history_path)
        storage = UploadStorage(settings.upload_path, settings.max_file_bytes, settings.KEEP_UPLOADS)
        analysis = AnalysisService(settings, llm, rag, legislation, ocr, history, storage)
        jobs = JobManager(settings.MAX_CONCURRENT_JOBS, settings.JOB_TTL_SECONDS)
        return cls(settings, llm, rag, legislation, ocr, history, storage, analysis, jobs)

    async def aclose(self) -> None:
        await self.jobs.shutdown()
        await self.llm.close()
