"""Analiz kullanım senaryolarını (use case) koordine eden uygulama servisi."""
from __future__ import annotations

from app.agents.comparison_agent import ComparisonAgent
from app.agents.orchestrator import DocumentInput, OrchestratorAgent, PipelineObserver
from app.config import Settings
from app.core.exceptions import InvalidInputError
from app.models.api import ComparisonResult
from app.models.review import ReviewState
from app.services.history_repository import HistoryRepository
from app.services.legislation_catalog import LegislationCatalog
from app.services.llm_service import LLMService
from app.services.ocr_service import OCRService
from app.services.rag_service import RAGService
from app.services.upload_storage import StoredFile, UploadStorage


class AnalysisService:
    def __init__(
        self,
        settings: Settings,
        llm: LLMService,
        rag: RAGService,
        legislation: LegislationCatalog,
        ocr: OCRService,
        history: HistoryRepository,
        storage: UploadStorage,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.rag = rag
        self.legislation = legislation
        self.ocr = ocr
        self.history = history
        self.storage = storage

    def validate_text(self, text: str, field_name: str = "Metin") -> str:
        text = (text or "").strip()
        # Null byte ve kontrol karakterlerini temizle (tab ve newline hariç)
        text = "".join(ch for ch in text if ch in ("\t", "\n", "\r") or (ord(ch) >= 32))
        if len(text) < self.settings.MIN_TEXT_CHARS:
            raise InvalidInputError(f"{field_name} en az {self.settings.MIN_TEXT_CHARS} karakter olmalıdır.")
        if len(text) > self.settings.MAX_TEXT_CHARS:
            raise InvalidInputError(f"{field_name} en fazla {self.settings.MAX_TEXT_CHARS:,} karakter olabilir.".replace(",", "."))
        return text

    async def analyze_text(self, text: str, title: str | None = None, observer: PipelineObserver | None = None) -> dict:
        text = self.validate_text(text)
        source_name = (title or "").strip() or self.default_title(text)
        return await self._run(DocumentInput.from_text(text, source_name), observer)

    async def analyze_file(self, stored: StoredFile, observer: PipelineObserver | None = None) -> dict:
        try:
            return await self._run(DocumentInput.from_file(stored.path, stored.original_name), observer)
        finally:
            self.storage.release(stored)

    async def compare(self, text1: str, text2: str) -> ComparisonResult:
        text1 = self.validate_text(text1, "Birinci metin")
        text2 = self.validate_text(text2, "İkinci metin")
        return await ComparisonAgent(self.llm).execute(text1, text2)

    async def _run(self, document: DocumentInput, observer: PipelineObserver | None) -> dict:
        orchestrator = OrchestratorAgent(
            llm_service=self.llm,
            rag_service=self.rag,
            legislation_catalog=self.legislation,
            ocr_service=self.ocr,
            observer=observer,
        )
        result = await orchestrator.run(document)
        payload = result.model_dump(mode="json")
        payload["history_id"] = self.history.save(payload)
        payload["review"] = ReviewState().model_dump(mode="json")
        return payload

    @staticmethod
    def default_title(text: str) -> str:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "Metin girişi")
        return first_line[:80]
