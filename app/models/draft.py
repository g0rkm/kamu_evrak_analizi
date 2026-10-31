from datetime import datetime, timezone
import re
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from .analysis import AnalysisResult, none_if_blank

Severity = Literal["info", "warning", "correction"]
StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]
PipelineStatus = Literal["completed", "partial", "error"]


class DraftResponse(BaseModel):
    draft_type: str = "ust_yazi"  # app.core.taxonomy.DRAFT_TYPES kodlarından biri
    subject: str = ""
    body: str = ""
    formal_greeting: str = ""  # "İlgi:", "Sayın..." vb.
    closing: str = ""
    attachments_note: Optional[str] = None
    tone_check: str = ""  # Üslup uygunluk notu
    rendered_text: str = ""  # Şablonla üretilmiş tam resmî yazı metni

    @field_validator("attachments_note", mode="before")
    @classmethod
    def _blank_attachments(cls, value):
        cleaned = none_if_blank(value)
        if isinstance(cleaned, str):
            cleaned = re.sub(r"^\s*ek(ler)?\s*:\s*", "", cleaned, flags=re.IGNORECASE).strip()
            if not cleaned:
                return None
        return cleaned


class RoutingDecision(BaseModel):
    target_unit: str  # Hedef birim adı
    reasoning: str = ""
    priority: str = "normal"  # acil, yuksek, normal, dusuk
    alternative_units: list[str] = Field(default_factory=list)
    requires_action: list[str] = Field(default_factory=list)  # Birimden beklenen eylemler


class ValidationEntry(BaseModel):
    field: str
    original_value: str
    corrected_value: Optional[str] = None
    rule: str
    severity: Severity = "info"
    message: str = ""  # Kullanıcıya gösterilecek açıklama


class StepTiming(BaseModel):
    step: str  # Adım anahtarı (extract, classify, ...)
    label: str = ""
    agent: str = ""
    duration: float = 0.0
    status: StepStatus = "completed"
    error: Optional[str] = None


class PipelineResult(BaseModel):
    document_id: str = Field(default_factory=lambda: uuid4().hex)
    source_name: str = ""
    input_kind: Literal["file", "text"] = "text"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysis: AnalysisResult
    draft: Optional[DraftResponse] = None
    routing: Optional[RoutingDecision] = None
    processing_time: float = 0.0
    agent_logs: list[str] = Field(default_factory=list)
    step_timings: list[StepTiming] = Field(default_factory=list)
    status: PipelineStatus = "completed"
    warnings: list[str] = Field(default_factory=list)  # Başarısız/atlanan adımlar
    validation: list[ValidationEntry] = Field(default_factory=list)  # Muhakeme ajanı çıktısı
    confidence_score: float = 0.0  # Genel güven skoru (0-1)
