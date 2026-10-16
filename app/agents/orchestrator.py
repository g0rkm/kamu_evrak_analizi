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
    """Tüm agentları koordine eden orkestratör."""
    
    def __init__(self):
        self.llm_service = LLMService()
        super().__init__(name="Orchestrator", llm_service=self.llm_service)
        
        # Alt agentları başlat
        self.ocr_agent = OCRAgent(llm_service=self.llm_service)
        self.classifier = ClassifierAgent(llm_service=self.llm_service)
        self.analyzer = AnalyzerAgent(llm_service=self.llm_service)
        self.legislation = LegislationAgent(llm_service=self.llm_service)
        self.summary = SummaryAgent(llm_service=self.llm_service)
        self.drafter = DraftAgent(llm_service=self.llm_service)
        self.router = RoutingAgent(llm_service=self.llm_service)
        self.reasoner = ReasoningAgent()
    
    async def execute(self, file_path: str) -> PipelineResult:
        """Uçtan uca evrak işleme pipeline'ı çalıştır."""
        start_time = time.time()
        all_logs = []
        
        self.log(f"Pipeline başlatılıyor: {file_path}")
        
        # Adım 1: OCR / Metin Çıkarma
        self.log("Adım 1/7: Metin çıkarma...")
        extracted = await self.ocr_agent.execute(file_path=file_path)
        all_logs.extend(self.ocr_agent.get_logs())
        text = extracted.cleaned_text
        
        if not text.strip():
            self.log("HATA: Evraktan metin çıkarılamadı!")
            return PipelineResult(
                document_id="error",
                analysis=AnalysisResult(
                    classification=ClassificationResult(document_type="bilinmiyor", confidence=0.0, reasoning="Metin çıkarılamadı")
                ),
                status="error",
                processing_time=time.time() - start_time,
                agent_logs=all_logs
            )
        
        # Adım 2: Sınıflandırma
        self.log("Adım 2/7: Evrak sınıflandırma...")
        classification = await self.classifier.execute(text=text)
        all_logs.extend(self.classifier.get_logs())
        
        # Adım 3: İçerik Analizi
        self.log("Adım 3/7: İçerik analizi...")
        try:
            analysis_data = await self.analyzer.execute(text=text)
            all_logs.extend(self.analyzer.get_logs())
        except Exception as e:
            self.log(f"İçerik analizi hatası (varsayılan kullanılıyor): {e}")
            analysis_data = {"entities": [], "missing_fields": [], "keywords": []}
        
        # Adım 4: Mevzuat Eşleştirme
        self.log("Adım 4/7: Mevzuat eşleştirme...")
        try:
            legislation_matches = await self.legislation.execute(text=text, document_type=classification.document_type)
            all_logs.extend(self.legislation.get_logs())
        except Exception as e:
            self.log(f"Mevzuat eşleştirme hatası (varsayılan kullanılıyor): {e}")
            legislation_matches = []
        
        # Adım 5: Özet Oluşturma
        self.log("Adım 5/7: Özet oluşturma...")
        try:
            summary_text = await self.summary.execute(text=text, document_type=classification.document_type)
            all_logs.extend(self.summary.get_logs())
        except Exception as e:
            self.log(f"Özet oluşturma hatası (varsayılan kullanılıyor): {e}")
            summary_text = "Özet oluşturulamadı."
        
        # AnalysisResult birleştir
        analysis = AnalysisResult(
            classification=classification,
            entities=analysis_data["entities"],
            missing_fields=analysis_data["missing_fields"],
            legislation_matches=legislation_matches,
            summary=summary_text,
            keywords=analysis_data["keywords"]
        )
        
        # Adım 6: Yazı Taslağı + Birim Yönlendirme
        self.log("Adım 6/7: Yazı taslağı ve yönlendirme...")
        try:
            draft = await self.drafter.execute(
                text=text,
                document_type=classification.document_type,
                summary=summary_text,
                entities=analysis_data["entities"]
            )
            all_logs.extend(self.drafter.get_logs())
        except Exception as e:
            self.log(f"Taslak oluşturma hatası (varsayılan kullanılıyor): {e}")
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
            self.log(f"Yönlendirme hatası (varsayılan kullanılıyor): {e}")
            routing = None
        
        # Adım 7: Muhakeme ve Doğrulama
        self.log("Adım 7/7: Muhakeme ve doğrulama...")
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
            self.log(f"Muhakeme hatası (varsayılan kullanılıyor): {e}")
            validation = []
            confidence_score = analysis.classification.confidence
        
        processing_time = time.time() - start_time
        self.log(f"Pipeline tamamlandı: {processing_time:.2f} saniye")
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
            confidence_score=confidence_score
        )
    
    async def close(self):
        """Kaynakları temizle."""
        await self.llm_service.close()
