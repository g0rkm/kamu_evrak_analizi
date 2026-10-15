from datetime import datetime
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field

class DocumentMetadata(BaseModel):
    filename: str
    file_type: str  # "pdf", "image", "text"
    file_size: int
    upload_time: datetime
    page_count: int = 1

class ExtractedText(BaseModel):
    raw_text: str
    cleaned_text: str
    language: str = "tr"
    confidence: float = 0.0  # OCR confidence

class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    metadata: DocumentMetadata
    extracted_text: Optional[ExtractedText] = None
    status: str = "uploaded"  # uploaded, processing, completed, error
