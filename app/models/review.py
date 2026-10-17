"""İnsan onayı (human-in-the-loop) kayıtları."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

DraftReviewStatus = Literal["pending", "approved", "edited", "rejected"]
RoutingReviewStatus = Literal["pending", "approved", "changed"]


class ReviewState(BaseModel):
    draft_status: DraftReviewStatus = "pending"
    draft_body: Optional[str] = None  # Memurun düzenlediği metin
    reject_reason: Optional[str] = None
    routing_status: RoutingReviewStatus = "pending"
    routing_unit: Optional[str] = None  # Memurun seçtiği birim
    updated_at: Optional[datetime] = None
    audit_log: list[dict] = Field(default_factory=list)
    notes: str = ""


class ReviewUpdate(BaseModel):
    draft_status: Optional[DraftReviewStatus] = None
    draft_body: Optional[str] = Field(default=None, max_length=50_000)
    reject_reason: Optional[str] = Field(default=None, max_length=1_000)
    routing_status: Optional[RoutingReviewStatus] = None
    routing_unit: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)
