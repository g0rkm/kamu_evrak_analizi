"""ReasoningAgent'ın uyguladığı deterministik doğrulama kuralları.

Her kural `ValidationRule` alt sınıfıdır ve ortak bir `ReasoningContext`
üzerinde çalışır: gerekirse agent çıktısını düzeltir, her durumda bulgusunu
`ValidationEntry` olarak kaydeder. Yeni kural eklemek için bir alt sınıf yazıp
`default_rules()` listesine eklemek yeterlidir.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from app.core.taxonomy import (
    DEFAULT_PRIORITY, DOCUMENT_TYPES, DRAFT_TYPES, ORG_UNITS, PRIORITIES, URGENT_KEYWORDS,
)
from app.models.analysis import AnalysisResult, MissingField
from app.models.draft import DraftResponse, RoutingDecision, ValidationEntry
from app.services.pii_detector import PIIDetector


@dataclass
class ReasoningContext:
    text: str
    analysis: AnalysisResult
    draft: DraftResponse | None = None
    routing: RoutingDecision | None = None
    validation: list[ValidationEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.text_lower = self.text.lower()

    @property
    def document_type(self) -> str:
        return self.analysis.classification.document_type

    def add(self, entry: ValidationEntry) -> None:
        self.validation.append(entry)

    def note(self, message: str) -> None:
        self.notes.append(message)


class KeywordMatcher:
    """Taksonomideki anahtar kelimelerle metin üzerinde sayım yapar."""

    def __init__(self, min_hits: int = 2) -> None:
        self.min_hits = min_hits

    @staticmethod
    def count(text_lower: str, keywords: tuple[str, ...]) -> int:
        return sum(1 for kw in keywords if kw in text_lower)

    def document_type_hits(self, text_lower: str, code: str) -> int:
        doc_type = DOCUMENT_TYPES.get(code)
        return self.count(text_lower, doc_type.keywords) if doc_type else 0

    def best_document_type(self, text_lower: str) -> str | None:
        best, best_hits = None, 0
        for doc_type in DOCUMENT_TYPES:
            hits = self.count(text_lower, doc_type.keywords)
            if hits > best_hits:
                best, best_hits = doc_type.code, hits
        return best if best_hits >= self.min_hits else None

    def unit_hits(self, text_lower: str, unit_name: str) -> int:
        code = ORG_UNITS.resolve(unit_name)
        unit = ORG_UNITS.get(code) if code else None
        return self.count(text_lower, unit.keywords) if unit else 0

    def best_unit(self, text_lower: str) -> str | None:
        best, best_hits = None, 0
        for unit in ORG_UNITS:
            hits = self.count(text_lower, unit.keywords)
            if hits > best_hits:
                best, best_hits = unit.label, hits
        return best if best_hits >= self.min_hits else None


class ValidationRule(ABC):
    code: ClassVar[str]
    title: ClassVar[str]

    @abstractmethod
    def apply(self, ctx: ReasoningContext) -> None:
        ...


class ClassificationConsistencyRule(ValidationRule):
    code = "keyword_classification"
    title = "Sınıflandırma tutarlılığı"

    def __init__(self, matcher: KeywordMatcher) -> None:
        self.matcher = matcher

    def apply(self, ctx: ReasoningContext) -> None:
        detected = self.matcher.best_document_type(ctx.text_lower)
        current = ctx.document_type
        if not detected or detected == current:
            return

        detected_label = DOCUMENT_TYPES.label(detected)
        if self.matcher.document_type_hits(ctx.text_lower, detected) > self.matcher.document_type_hits(ctx.text_lower, current):
            old = ctx.analysis.classification
            ctx.analysis.classification = old.model_copy(update={
                "document_type": detected,
                "confidence": min(old.confidence, 0.7),
                "reasoning": f"Muhakeme düzeltmesi: Anahtar kelime analizi '{detected_label}' türünü destekliyor "
                             f"(yapay zekâ önerisi: {DOCUMENT_TYPES.label(current)}).",
            })
            ctx.add(ValidationEntry(
                field="classification.document_type", original_value=current, corrected_value=detected,
                rule=self.code, severity="correction",
                message=f"Metindeki anahtar kelimeler '{detected_label}' türünü daha güçlü destekliyor; sınıflandırma düzeltildi.",
            ))
            ctx.note(f"Sınıflandırma düzeltildi: {current} -> {detected}")
        else:
            ctx.add(ValidationEntry(
                field="classification.document_type", original_value=current,
                rule=self.code, severity="info",
                message=f"Anahtar kelimeler '{detected_label}' türüne de işaret ediyor; yapay zekâ sınıflandırması korundu.",
            ))


class DraftTypeConsistencyRule(ValidationRule):
    code = "draft_type_consistency"
    title = "Taslak türü uygunluğu"

    def apply(self, ctx: ReasoningContext) -> None:
        if not ctx.draft:
            return
        doc_type = DOCUMENT_TYPES.get(ctx.document_type)
        valid = doc_type.draft_types if doc_type else ()
        original = ctx.draft.draft_type
        if not valid or original in valid:
            return

        corrected = valid[0]
        ctx.draft = ctx.draft.model_copy(update={
            "draft_type": corrected,
            "tone_check": f"Taslak türü '{DRAFT_TYPES.label(original)}' yerine '{DRAFT_TYPES.label(corrected)}' "
                          f"olarak düzeltildi (evrak türü: {DOCUMENT_TYPES.label(ctx.document_type)}).",
        })
        ctx.add(ValidationEntry(
            field="draft.draft_type", original_value=original, corrected_value=corrected,
            rule=self.code, severity="correction",
            message=f"'{DOCUMENT_TYPES.label(ctx.document_type)}' için '{DRAFT_TYPES.label(original)}' uygun değil; "
                    f"'{DRAFT_TYPES.label(corrected)}' olarak düzeltildi.",
        ))
        ctx.note(f"Taslak türü düzeltildi: {original} -> {corrected}")


class RoutingConsistencyRule(ValidationRule):
    code = "keyword_routing"
    title = "Yönlendirme tutarlılığı"

    def __init__(self, matcher: KeywordMatcher) -> None:
        self.matcher = matcher

    def apply(self, ctx: ReasoningContext) -> None:
        if not ctx.routing:
            return
        suggested = self.matcher.best_unit(ctx.text_lower)
        current = ctx.routing.target_unit
        if not suggested or suggested == current:
            return
        if self.matcher.unit_hits(ctx.text_lower, suggested) <= self.matcher.unit_hits(ctx.text_lower, current):
            return

        alternatives = [current] + [u for u in ctx.routing.alternative_units if u not in (current, suggested)]
        ctx.routing = ctx.routing.model_copy(update={
            "target_unit": suggested,
            "alternative_units": alternatives,
            "reasoning": f"Muhakeme düzeltmesi: Anahtar kelime analizi '{suggested}' birimini destekliyor "
                         f"(yapay zekâ önerisi: {current}).",
        })
        ctx.add(ValidationEntry(
            field="routing.target_unit", original_value=current, corrected_value=suggested,
            rule=self.code, severity="correction",
            message=f"Metin içeriği '{suggested}' birimiyle daha çok örtüşüyor; önceki öneri alternatiflere taşındı.",
        ))
        ctx.note(f"Yönlendirme düzeltildi: {current} -> {suggested}")


class PriorityRule(ValidationRule):
    code = "priority_rules"
    title = "Öncelik kuralı"

    def apply(self, ctx: ReasoningContext) -> None:
        if not ctx.routing:
            return
        urgent = [kw for kw in URGENT_KEYWORDS if kw in ctx.text_lower]
        doc_type = DOCUMENT_TYPES.get(ctx.document_type)
        expected = "acil" if urgent else (doc_type.default_priority if doc_type else DEFAULT_PRIORITY)
        original = ctx.routing.priority
        if original == expected:
            return

        reason = (f"metinde aciliyet ifadesi var ('{urgent[0]}')" if urgent
                  else f"'{DOCUMENT_TYPES.label(ctx.document_type)}' türü için varsayılan öncelik")
        ctx.routing = ctx.routing.model_copy(update={"priority": expected})
        ctx.add(ValidationEntry(
            field="routing.priority", original_value=original, corrected_value=expected,
            rule=self.code, severity="correction",
            message=f"Öncelik '{PRIORITIES.label(expected)}' olarak ayarlandı: {reason}.",
        ))
        ctx.note(f"Öncelik düzeltildi: {original} -> {expected}")


class RequiredFieldsRule(ValidationRule):
    code = "pattern_missing_field"
    title = "Zorunlu alan kontrolü"

    PATTERNS: ClassVar[dict[str, tuple[str, ...]]] = {
        "tarih": (r"\d{2}[./]\d{2}[./]\d{4}", r"\d{4}[./]\d{2}[./]\d{2}"),
        "sayi": (r"sayı\s*:\s*\S+", r"say[ıi]\s*:\s*\S+"),
        "konu": (r"konu\s*:\s*.+",),
        "imza": (r"arz ederim", r"rica ederim", r"saygılarımla"),
    }
    LABELS: ClassVar[dict[str, str]] = {"tarih": "Tarih", "sayi": "Sayı", "konu": "Konu", "imza": "İmza / kapanış"}
    CRITICAL: ClassVar[frozenset[str]] = frozenset({"tarih", "sayi"})

    def apply(self, ctx: ReasoningContext) -> None:
        for name, patterns in self.PATTERNS.items():
            if any(re.search(p, ctx.text_lower) for p in patterns):
                continue
            if any(mf.field_name == name for mf in ctx.analysis.missing_fields):
                continue
            ctx.analysis.missing_fields.append(MissingField(
                field_name=name,
                description=f"Kural tabanlı kontrol: '{name}' alanı metinde tespit edilemedi",
                is_critical=name in self.CRITICAL,
            ))
            ctx.add(ValidationEntry(
                field=f"missing_fields.{name}", original_value="not_detected",
                rule=self.code, severity="warning",
                message=f"'{self.LABELS[name]}' alanı metinde bulunamadı.",
            ))


class PersonalDataRule(ValidationRule):
    code = "pii_detection"
    title = "Kişisel veri (KVKK) tespiti"
    LEAK_CODE = "draft_pii_leak"

    def __init__(self, detector: PIIDetector) -> None:
        self.detector = detector

    def apply(self, ctx: ReasoningContext) -> None:
        for finding in self.detector.detect(ctx.text):
            ctx.add(ValidationEntry(
                field=f"pii.{finding.type}", original_value=finding.masked_value,
                rule=self.code, severity=finding.severity,
                message=f"Evrakta {finding.label} tespit edildi.",
            ))
        if ctx.draft and ctx.draft.body:
            for finding in self.detector.detect(ctx.draft.body):
                ctx.add(ValidationEntry(
                    field=f"draft_pii_leak.{finding.type}", original_value=finding.masked_value,
                    rule=self.LEAK_CODE, severity="warning",
                    message=f"Taslak yazıya {finding.label} sızmış; göndermeden önce çıkarın.",
                ))


def default_rules(detector: PIIDetector | None = None) -> list[ValidationRule]:
    matcher = KeywordMatcher()
    return [
        ClassificationConsistencyRule(matcher),
        DraftTypeConsistencyRule(),
        RoutingConsistencyRule(matcher),
        PriorityRule(),
        RequiredFieldsRule(),
        PersonalDataRule(detector or PIIDetector()),
    ]
