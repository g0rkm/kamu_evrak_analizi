import time
from app.agents.base_agent import BaseAgent
from app.agents.ocr_agent import OCRAgent
from app.agents.classifier_agent import ClassifierAgent
from app.agents.analyzer_agent import AnalyzerAgent
from app.agents.legislation_agent import LegislationAgent
from app.agents.summary_agent import SummaryAgent
from app.agents.draft_agent import DraftAgent
from app.agents.routing_agent import RoutingAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.services.llm_service import LLMService
from app.models.analysis import AnalysisResult, ClassificationResult, LegislationMatch, MissingField
from app.models.draft import PipelineResult, ValidationEntry, DraftResponse, RoutingDecision


class OrchestratorAgent(BaseAgent):
    """Tum agentlari koordine eden orkestrator."""

    def __init__(self):
        self.llm_service = LLMService()
        super().__init__(name="Orchestrator", llm_service=self.llm_service)

        self.ocr_agent = OCRAgent(llm_service=self.llm_service)
        self.classifier = ClassifierAgent(llm_service=self.llm_service)
        self.analyzer = AnalyzerAgent(llm_service=self.llm_service)
        self.legislation = LegislationAgent(llm_service=self.llm_service)
        self.summary = SummaryAgent(llm_service=self.llm_service)
        self.drafter = DraftAgent(llm_service=self.llm_service)
        self.router = RoutingAgent(llm_service=self.llm_service)
        self.reasoner = ReasoningAgent()

    def _timed_step(self, step_name, agent_name, t0):
        """Adim suresini hesapla ve dict dondur."""
        return {"step": step_name, "agent": agent_name, "duration": round(time.time() - t0, 2)}

    async def execute(self, file_path: str) -> PipelineResult:
        """Uctan uca evrak isleme pipeline'i calistir."""
        start_time = time.time()
        all_logs = []
        step_timings = []

        self.log(f"Pipeline baslatiliyor: {file_path}")

        # Adim 1: OCR / Metin Cikarma
        self.log("Adim 1/7: Metin cikarma...")
        t0 = time.time()
        extracted = await self.ocr_agent.execute(file_path=file_path)
        step_timings.append(self._timed_step("Metin Cikarma", "OCRAgent", t0))
        all_logs.extend(self.ocr_agent.get_logs())
        text = extracted.cleaned_text

        if not text.strip():
            self.log("HATA: Evraktan metin cikarilamadi!")
            return PipelineResult(
                document_id="error",
                analysis=AnalysisResult(
                    classification=ClassificationResult(document_type="bilinmiyor", confidence=0.0, reasoning="Metin cikarilamadi")
                ),
                status="error",
                processing_time=time.time() - start_time,
                agent_logs=all_logs,
                step_timings=step_timings
            )

        # Adim 2: Siniflandirma
        self.log("Adim 2/7: Evrak siniflandirma...")
        t0 = time.time()
        classification = await self.classifier.execute(text=text)
        step_timings.append(self._timed_step("Siniflandirma", "ClassifierAgent", t0))
        all_logs.extend(self.classifier.get_logs())

        # Adim 3: Icerik Analizi
        self.log("Adim 3/7: Icerik analizi...")
        t0 = time.time()
        try:
            analysis_data = await self.analyzer.execute(text=text)
            all_logs.extend(self.analyzer.get_logs())
        except Exception as e:
            self.log(f"Icerik analizi hatasi (varsayilan kullaniliyor): {e}")
            analysis_data = {"entities": [], "missing_fields": [], "keywords": []}
        step_timings.append(self._timed_step("Icerik Analizi", "AnalyzerAgent", t0))

        # Adim 4: Mevzuat Eslestirme
        self.log("Adim 4/7: Mevzuat eslestirme...")
        t0 = time.time()
        try:
            legislation_matches = await self.legislation.execute(text=text, document_type=classification.document_type, keywords=analysis_data.get("keywords", []))
            all_logs.extend(self.legislation.get_logs())
        except Exception as e:
            self.log(f"Mevzuat eslestirme hatasi (varsayilan kullaniliyor): {e}")
            legislation_matches = []
        step_timings.append(self._timed_step("Mevzuat Eslestirme", "LegislationAgent", t0))

        # Adim 5: Ozet Olusturma
        self.log("Adim 5/7: Ozet olusturma...")
        t0 = time.time()
        try:
            summary_text = await self.summary.execute(text=text, document_type=classification.document_type)
            all_logs.extend(self.summary.get_logs())
        except Exception as e:
            self.log(f"Ozet olusturma hatasi (varsayilan kullaniliyor): {e}")
            summary_text = "Ozet olusturulamadi."
        step_timings.append(self._timed_step("Ozet Olusturma", "SummaryAgent", t0))

        # AnalysisResult birlestir
        analysis = AnalysisResult(
            classification=classification,
            entities=analysis_data["entities"],
            missing_fields=analysis_data["missing_fields"],
            legislation_matches=legislation_matches,
            summary=summary_text,
            keywords=analysis_data["keywords"]
        )

        # Adim 6: Yazi Taslagi + Birim Yonlendirme
        self.log("Adim 6/7: Yazi taslagi ve yonlendirme...")
        t0 = time.time()
        try:
            draft = await self.drafter.execute(
                text=text,
                document_type=classification.document_type,
                summary=summary_text,
                entities=analysis_data["entities"]
            )
            all_logs.extend(self.drafter.get_logs())
        except Exception as e:
            self.log(f"Taslak olusturma hatasi (varsayilan kullaniliyor): {e}")
            draft = None

        try:
            routing = await self.router.execute(
                text=text,
                document_type=classification.document_type,
                summary=summary_text,
                keywords=analysis_data["keywords"]
            )
            all_logs.extend(self.router.get_logs())
        except Exception as e:
            self.log(f"Yonlendirme hatasi (varsayilan kullaniliyor): {e}")
            routing = None
        step_timings.append(self._timed_step("Taslak & Yonlendirme", "DraftAgent+RoutingAgent", t0))

        # Adim 7: Muhakeme ve Dogrulama
        self.log("Adim 7/7: Muhakeme ve dogrulama...")
        t0 = time.time()
        try:
            reasoning_result = await self.reasoner.execute(
                text=text,
                analysis=analysis,
                draft=draft,
                routing=routing
            )
            all_logs.extend(self.reasoner.get_logs())
            analysis = reasoning_result["analysis"]
            draft = reasoning_result["draft"]
            routing = reasoning_result["routing"]
            validation = reasoning_result["validation"]
            confidence_score = reasoning_result["confidence_score"]
        except Exception as e:
            self.log(f"Muhakeme hatasi (varsayilan kullaniliyor): {e}")
            validation = []
            confidence_score = analysis.classification.confidence
        step_timings.append(self._timed_step("Muhakeme & Dogrulama", "ReasoningAgent", t0))

        processing_time = time.time() - start_time
        self.log(f"Pipeline tamamlandi: {processing_time:.2f} saniye")
        all_logs.extend(self.get_logs())

        return PipelineResult(
            document_id=file_path,
            analysis=analysis,
            draft=draft,
            routing=routing,
            processing_time=processing_time,
            agent_logs=all_logs,
            status="completed",
            validation=validation,
            confidence_score=confidence_score,
            step_timings=step_timings
        )

    async def close(self):
        """Kaynaklari temizle."""
        await self.llm_service.close()
