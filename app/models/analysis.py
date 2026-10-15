from typing import Optional
from pydantic import BaseModel

class ClassificationResult(BaseModel):
    document_type: str  # dilekçe, resmi_yazi, talep_yazisi, bilgilendirme, gorus_sorma, sikayet, kurum_ici, genelge, rapor, tutanak, yonetmelik, teblig, kanun, karar, kararname, ilan, yonerge, sozlesme
    confidence: float
    sub_type: Optional[str] = None
    reasoning: str  # Sınıflandırma gerekçesi

class ExtractedEntity(BaseModel):
    entity_type: str  # tarih, kurum, kisi, konu, referans_no
    value: str
    position: Optional[str] = None  # Metinde nerede bulundu

class MissingField(BaseModel):
    field_name: str
    description: str
    is_critical: bool = False

class LegislationMatch(BaseModel):
    legislation_name: str
    article: Optional[str] = None
    relevance_score: float
    summary: str

class AnalysisResult(BaseModel):
    classification: ClassificationResult
    entities: list[ExtractedEntity] = []
    missing_fields: list[MissingField] = []
    legislation_matches: list[LegislationMatch] = []
    summary: str = ""
    keywords: list[str] = []
