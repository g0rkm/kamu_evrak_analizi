from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.taxonomy import UNKNOWN_DOCUMENT_TYPE


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def none_if_blank(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "-"}:
        return None
    return value


class ClassificationResult(BaseModel):
    document_type: str  # app.core.taxonomy.DOCUMENT_TYPES kodlarından biri
    confidence: float = 0.0
    sub_type: Optional[str] = None
    reasoning: str = ""  # Sınıflandırma gerekçesi

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return clamp_unit(value)

    @field_validator("sub_type", mode="before")
    @classmethod
    def _blank_sub_type(cls, value: Any) -> Any:
        return none_if_blank(value)

    @classmethod
    def unknown(cls, reasoning: str) -> "ClassificationResult":
        return cls(document_type=UNKNOWN_DOCUMENT_TYPE, confidence=0.0, reasoning=reasoning)


class ExtractedEntity(BaseModel):
    entity_type: str  # tarih, kurum, kisi, konu, referans_no, adres, telefon
    value: str
    position: Optional[str] = None  # Metinde nerede bulundu

    @field_validator("value", mode="before")
    @classmethod
    def _stringify(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("position", mode="before")
    @classmethod
    def _blank_position(cls, value: Any) -> Any:
        return none_if_blank(value)


class MissingField(BaseModel):
    field_name: str
    description: str = ""
    is_critical: bool = False


class LegislationMatch(BaseModel):
    legislation_name: str
    article: Optional[str] = None
    relevance_score: float = 0.0
    summary: str = ""

    @field_validator("relevance_score")
    @classmethod
    def _clamp_score(cls, value: float) -> float:
        return clamp_unit(value)

    @field_validator("article", mode="before")
    @classmethod
    def _stringify_article(cls, value: Any) -> Any:
        value = none_if_blank(value)
        return None if value is None else str(value)


class ContentAnalysis(BaseModel):
    """AnalyzerAgent çıktısı."""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    missing_fields: list[MissingField] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    classification: ClassificationResult
    entities: list[ExtractedEntity] = Field(default_factory=list)
    missing_fields: list[MissingField] = Field(default_factory=list)
    legislation_matches: list[LegislationMatch] = Field(default_factory=list)
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)
