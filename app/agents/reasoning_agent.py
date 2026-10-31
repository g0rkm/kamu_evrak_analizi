from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.agents.validation_rules import ReasoningContext, ValidationRule, default_rules
from app.models.analysis import AnalysisResult
from app.models.draft import DraftResponse, RoutingDecision, ValidationEntry
from app.services.draft_renderer import render_draft


class ReasoningOutcome(BaseModel):
    analysis: AnalysisResult
    draft: DraftResponse | None = None
    routing: RoutingDecision | None = None
    validation: list[ValidationEntry] = Field(default_factory=list)
    confidence_score: float = 0.0


class ConfidenceCalculator:
    """Sınıflandırma güveninden, düzeltme ve uyarı sayısına göre ceza düşer."""

    CORRECTION_PENALTY = 0.15
    WARNING_PENALTY = 0.05

    def score(self, base_confidence: float, validation: list[ValidationEntry]) -> float:
        corrections = sum(1 for v in validation if v.severity == "correction")
        warnings = sum(1 for v in validation if v.severity == "warning")
        value = base_confidence - corrections * self.CORRECTION_PENALTY - warnings * self.WARNING_PENALTY
        return round(max(0.0, min(1.0, value)), 2)


class ReasoningAgent(BaseAgent):
    """Kural tabanlı muhakeme ajanı. LLM çağırmaz, deterministik çalışır."""

    name = "ReasoningAgent"

    def __init__(
        self,
        rules: Sequence[ValidationRule] | None = None,
        calculator: ConfidenceCalculator | None = None,
    ) -> None:
        super().__init__()
        self.rules = list(rules) if rules is not None else default_rules()
        self.calculator = calculator or ConfidenceCalculator()

    async def execute(
        self,
        text: str,
        analysis: AnalysisResult,
        draft: DraftResponse | None = None,
        routing: RoutingDecision | None = None,
    ) -> ReasoningOutcome:
        """Tüm agent çıktılarını kurallarla doğrular ve gerekiyorsa düzeltir."""
        self.log(f"Muhakeme başlatılıyor ({len(self.rules)} kural)...")
        ctx = ReasoningContext(
            text=text,
            analysis=analysis.model_copy(deep=True),
            draft=draft.model_copy(deep=True) if draft else None,
            routing=routing.model_copy(deep=True) if routing else None,
        )
        for rule in self.rules:
            rule.apply(ctx)
        for note in ctx.notes:
            self.log(note)

        if ctx.draft is not None:
            try:
                ctx.draft.rendered_text = render_draft(ctx.draft, ctx.analysis, ctx.routing)
            except Exception as exc:  # render başarısızsa ham alanlara düşülür
                self.log(f"Taslak render edilemedi: {exc}")

        confidence = self.calculator.score(ctx.analysis.classification.confidence, ctx.validation)
        self.log(f"Muhakeme tamamlandı: {len(ctx.validation)} bulgu, güven: {confidence:.2f}")
        return ReasoningOutcome(
            analysis=ctx.analysis,
            draft=ctx.draft,
            routing=ctx.routing,
            validation=ctx.validation,
            confidence_score=confidence,
        )
