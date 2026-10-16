"""Uçtan uca evrak işleme pipeline'ı.

Aşamalar (birbirinden bağımsız adımlar aynı aşamada paralel çalışır):

    1. Metin çıkarma
    2. Sınıflandırma  ‖ İçerik analizi
    3. Mevzuat        ‖ Özet
    4. Yazı taslağı   ‖ Birim yönlendirme
    5. Muhakeme ve doğrulama

Zorunlu olmayan bir adım başarısız olursa varsayılan değer kullanılır, sonuç
`partial` olarak işaretlenir ve hata `warnings` listesine yazılır.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Literal, TypeVar

from app.agents.analyzer_agent import AnalyzerAgent
from app.agents.base_agent import BaseAgent
from app.agents.classifier_agent import ClassifierAgent
from app.agents.draft_agent import DraftAgent
from app.agents.legislation_agent import LegislationAgent
from app.agents.ocr_agent import OCRAgent
from app.agents.reasoning_agent import ReasoningAgent, ReasoningOutcome
from app.agents.routing_agent import RoutingAgent
from app.agents.summary_agent import SummaryAgent
from app.core.exceptions import AppError, LLMError, TextExtractionError
from app.models.analysis import AnalysisResult, ClassificationResult, ContentAnalysis
from app.models.draft import PipelineResult, StepTiming
from app.services.legislation_catalog import LegislationCatalog
from app.services.llm_service import LLMService
from app.services.ocr_service import OCRService
from app.services.rag_service import RAGService

T = TypeVar("T")


@dataclass(frozen=True)
class PipelineStep:
    key: str
    label: str
    agent: str


EXTRACT = PipelineStep("extract", "Metin Çıkarma", "OCRAgent")
CLASSIFY = PipelineStep("classify", "Sınıflandırma", "ClassifierAgent")
ANALYZE = PipelineStep("analyze", "İçerik Analizi", "AnalyzerAgent")
LEGISLATION = PipelineStep("legislation", "Mevzuat Eşleştirme", "LegislationAgent")
SUMMARY = PipelineStep("summary", "Özet", "SummaryAgent")
DRAFT = PipelineStep("draft", "Yazı Taslağı", "DraftAgent")
ROUTING = PipelineStep("routing", "Birim Yönlendirme", "RoutingAgent")
REASONING = PipelineStep("reasoning", "Muhakeme ve Doğrulama", "ReasoningAgent")

PIPELINE_STEPS: tuple[PipelineStep, ...] = (EXTRACT, CLASSIFY, ANALYZE, LEGISLATION, SUMMARY, DRAFT, ROUTING, REASONING)


class PipelineObserver:
    """Adım ilerlemesini dinlemek isteyen sınıflar için temel (varsayılanı no-op)."""

    def on_step_started(self, step_key: str) -> None:
        pass

    def on_step_finished(self, timing: StepTiming) -> None:
        pass


@dataclass(frozen=True)
class DocumentInput:
    kind: Literal["file", "text"]
    source_name: str
    file_path: Path | None = None
    text: str | None = None

    @classmethod
    def from_file(cls, path: str | Path, source_name: str | None = None) -> DocumentInput:
        path = Path(path)
        return cls(kind="file", source_name=source_name or path.name, file_path=path)

    @classmethod
    def from_text(cls, text: str, source_name: str = "Metin girişi") -> DocumentInput:
        return cls(kind="text", source_name=source_name, text=text)


_REQUIRED = object()


class OrchestratorAgent(BaseAgent):
    """Tüm agentları koordine eden orkestratör. Her çalıştırma için yeni örnek oluşturulur."""

    name = "Orchestrator"

    def __init__(
        self,
        llm_service: LLMService | None = None,
        rag_service: RAGService | None = None,
        legislation_catalog: LegislationCatalog | None = None,
        ocr_service: OCRService | None = None,
        observer: PipelineObserver | None = None,
    ) -> None:
        super().__init__()
        self._owns_llm = llm_service is None
        self.llm_service = llm_service or LLMService()
        self.observer = observer or PipelineObserver()

        self.ocr_agent = OCRAgent(ocr_service)
        self.classifier = ClassifierAgent(self.llm_service)
        self.analyzer = AnalyzerAgent(self.llm_service)
        self.legislation = LegislationAgent(self.llm_service, rag_service, legislation_catalog)
        self.summarizer = SummaryAgent(self.llm_service)
        self.drafter = DraftAgent(self.llm_service)
        self.router = RoutingAgent(self.llm_service)
        self.reasoner = ReasoningAgent()

        self._logs: list[str] = []
        self._timings: list[StepTiming] = []
        self._warnings: list[str] = []
        self._errors: dict[str, Exception] = {}

    async def execute(self, file_path: str) -> PipelineResult:
        """Geriye dönük uyumluluk: dosya yolundan pipeline çalıştırır."""
        return await self.run(DocumentInput.from_file(file_path))

    async def run(self, document: DocumentInput) -> PipelineResult:
        started = time.perf_counter()
        self.log(f"Pipeline başlatılıyor: {document.source_name}")
        self._logs.extend(self.get_logs())
        self.clear_logs()

        text = await self._step(EXTRACT, self.ocr_agent, lambda: self._extract_text(document), _REQUIRED)
        if not text.strip():
            raise TextExtractionError()

        classification, content = await asyncio.gather(
            self._step(CLASSIFY, self.classifier, lambda: self.classifier.execute(text),
                       ClassificationResult.unknown("Yapay zekâ sınıflandırması yapılamadı.")),
            self._step(ANALYZE, self.analyzer, lambda: self.analyzer.execute(text), ContentAnalysis()),
        )
        self._raise_if_llm_down(CLASSIFY, ANALYZE)
        doc_type = classification.document_type

        legislation_matches, summary = await asyncio.gather(
            self._step(LEGISLATION, self.legislation,
                       lambda: self.legislation.execute(text, doc_type, content.keywords), []),
            self._step(SUMMARY, self.summarizer, lambda: self.summarizer.execute(text, doc_type), ""),
        )

        draft, routing = await asyncio.gather(
            self._step(DRAFT, self.drafter,
                       lambda: self.drafter.execute(text, doc_type, summary, content.entities), None),
            self._step(ROUTING, self.router,
                       lambda: self.router.execute(text, doc_type, summary, content.keywords), None),
        )

        analysis = AnalysisResult(
            classification=classification,
            entities=content.entities,
            missing_fields=content.missing_fields,
            legislation_matches=legislation_matches,
            summary=summary,
            keywords=content.keywords,
        )
        fallback = ReasoningOutcome(
            analysis=analysis, draft=draft, routing=routing, confidence_score=classification.confidence
        )
        outcome = await self._step(
            REASONING, self.reasoner, lambda: self.reasoner.execute(text, analysis, draft, routing), fallback
        )

        processing_time = round(time.perf_counter() - started, 2)
        self.log(f"Pipeline tamamlandı: {processing_time:.2f} saniye")
        self._logs.extend(self.get_logs())

        return PipelineResult(
            source_name=document.source_name,
            input_kind=document.kind,
            analysis=outcome.analysis,
            draft=outcome.draft,
            routing=outcome.routing,
            processing_time=processing_time,
            # Paralel adımların kayıtlarını zamana göre sırala (stabil sıralama, aynı saniyede ekleme sırası korunur)
            agent_logs=sorted(self._logs, key=lambda entry: entry[:10]),
            step_timings=self._timings,
            status="partial" if self._errors else "completed",
            warnings=self._warnings,
            validation=outcome.validation,
            confidence_score=outcome.confidence_score,
        )

    async def close(self) -> None:
        if self._owns_llm:
            await self.llm_service.close()

    # ── İç yardımcılar ───────────────────────────────────

    async def _extract_text(self, document: DocumentInput) -> str:
        if document.kind == "text":
            self.ocr_agent.log("Metin doğrudan girildi, OCR atlandı")
            return document.text or ""
        extracted = await self.ocr_agent.execute(str(document.file_path))
        return extracted.cleaned_text

    async def _step(self, step: PipelineStep, agent: BaseAgent, action: Callable[[], Awaitable[T]], fallback: T) -> T:
        """Bir adımı çalıştırır, süresini ölçer, hatada varsayılan değere düşer."""
        self.observer.on_step_started(step.key)
        started = time.perf_counter()
        status, error_message = "completed", None
        try:
            result = await action()
        except Exception as exc:
            if fallback is _REQUIRED:
                self._record(step, started, "failed", self._describe(exc), agent)
                raise
            self._errors[step.key] = exc
            error_message = self._describe(exc)
            self._warnings.append(f"{step.label}: {error_message}")
            self.log(f"{step.label} başarısız, varsayılan değer kullanılıyor: {error_message}")
            result, status = fallback, "failed"
        self._record(step, started, status, error_message, agent)
        return result

    def _record(self, step: PipelineStep, started: float, status: str, error: str | None, agent: BaseAgent) -> None:
        timing = StepTiming(
            step=step.key, label=step.label, agent=step.agent,
            duration=round(time.perf_counter() - started, 2), status=status, error=error,
        )
        self._timings.append(timing)
        self._logs.extend(agent.get_logs())
        agent.clear_logs()
        self.observer.on_step_finished(timing)

    def _raise_if_llm_down(self, *steps: PipelineStep) -> None:
        """Bağımsız iki LLM adımı da LLM hatasıyla düştüyse servis erişilemezdir; devam etmenin anlamı yok."""
        errors = [self._errors.get(s.key) for s in steps]
        if all(isinstance(e, LLMError) for e in errors):
            raise errors[0]

    @staticmethod
    def _describe(exc: Exception) -> str:
        if isinstance(exc, AppError):
            return exc.message
        return (str(exc) or exc.__class__.__name__)[:200]
