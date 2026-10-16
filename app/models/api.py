"""REST API istek/yanıt şemaları."""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .analysis import clamp_unit
from .draft import PipelineResult
from .review import ReviewState


class TextAnalysisRequest(BaseModel):
    text: str = Field(..., description="Analiz edilecek evrak metni")
    title: Optional[str] = Field(default=None, max_length=200, description="Geçmişte görünecek başlık")


class CompareRequest(BaseModel):
    text1: str
    text2: str


class ComparisonResult(BaseModel):
    similarity_score: float = 0.0
    common_themes: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    text1_unique: str = ""
    text2_unique: str = ""
    recommendation: str = ""

    @field_validator("similarity_score")
    @classmethod
    def _clamp_score(cls, value: float) -> float:
        return clamp_unit(value)


class AnalysisResponse(PipelineResult):
    history_id: Optional[str] = None
    review: ReviewState = Field(default_factory=ReviewState)


class BatchItem(BaseModel):
    filename: str
    status: Literal["completed", "partial", "error"]
    detail: Optional[str] = None
    history_id: Optional[str] = None
    document_type: Optional[str] = None
    confidence_score: Optional[float] = None


class BatchResponse(BaseModel):
    total: int
    results: list[BatchItem]


class HistoryItem(BaseModel):
    id: str
    timestamp: str
    source_name: str = ""
    document_type: str = ""
    confidence_score: float = 0.0
    processing_time: float = 0.0
    status: str = ""
    summary: str = ""
    draft_status: str = "pending"


class HistoryPage(BaseModel):
    total: int
    items: list[HistoryItem]


class HistoryStats(BaseModel):
    total: int = 0
    avg_confidence: float = 0.0
    avg_processing_time: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_draft_status: dict[str, int] = Field(default_factory=dict)


class JobCreated(BaseModel):
    job_id: str


class JobStep(BaseModel):
    key: str
    label: str
    status: str = "pending"
    duration: Optional[float] = None


class JobStatusResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    source_name: str
    steps: list[JobStep]
    result: Optional[dict] = None
    error: Optional[dict] = None
    created_at: str
    updated_at: str


class HealthStatus(BaseModel):
    status: str
    service: str
    version: str
    llm_configured: bool
    llm_model: str
    rag_available: bool
    rag_chunks: int
    total_analyses: int
    avg_confidence: float
    llm_usage: dict = Field(default_factory=dict)
