from typing import Optional
from pydantic import BaseModel
from .analysis import AnalysisResult

class DraftResponse(BaseModel):
    draft_type: str  # ust_yazi, cevap_yazisi, bilgilendirme, ic_yazisma
    subject: str
    body: str
    formal_greeting: str  # "İlgi:", "Sayın..." vb.
    closing: str
    attachments_note: Optional[str] = None
    tone_check: str  # Üslup uygunluk notu

class RoutingDecision(BaseModel):
    target_unit: str  # Hedef birim adı
    reasoning: str
    priority: str = "normal"  # acil, yuksek, normal, dusuk
    alternative_units: list[str] = []
    requires_action: list[str] = []  # Birimden beklenen eylemler

class PipelineResult(BaseModel):
    document_id: str
    analysis: AnalysisResult
    draft: Optional[DraftResponse] = None
    routing: Optional[RoutingDecision] = None
    processing_time: float = 0.0
    agent_logs: list[str] = []  # Her agent'ın işlem kaydı
    status: str = "completed"
