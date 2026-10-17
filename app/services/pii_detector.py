"""Kişisel veri (KVKK) tespiti."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence


def is_valid_tc_kimlik(value: str) -> bool:
    """TC Kimlik numarası sağlama (checksum) doğrulaması."""
    if len(value) != 11 or not value.isdigit() or value[0] == "0":
        return False
    digits = [int(d) for d in value]
    check1 = (sum(digits[0:9:2]) * 7 - sum(digits[1:8:2])) % 10
    check2 = sum(digits[0:10]) % 10
    return check1 == digits[9] and check2 == digits[10]


@dataclass(frozen=True)
class PIIPattern:
    code: str
    label: str
    regex: re.Pattern
    severity: str
    validator: Callable[[str], bool] | None = None


@dataclass(frozen=True)
class PIIFinding:
    type: str
    label: str
    masked_value: str
    severity: str


DEFAULT_PATTERNS: tuple[PIIPattern, ...] = (
    PIIPattern("tc_kimlik", "TC Kimlik Numarası", re.compile(r"\b[1-9]\d{10}\b"), "warning",
               validator=lambda v: is_valid_tc_kimlik(re.sub(r"\s", "", v))),
    PIIPattern("iban", "IBAN", re.compile(r"\bTR\s?\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\b"), "warning"),
    PIIPattern("telefon", "Telefon Numarası", re.compile(r"\b(?:\+90|0)\s?[5]\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b"), "info"),
    PIIPattern("sabit_tel", "Sabit Telefon", re.compile(r"\b(?:\+90|0)\s?[2-4]\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b"), "info"),
    PIIPattern("eposta", "E-posta Adresi", re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"), "info"),
    PIIPattern("plaka", "Araç Plakası", re.compile(r"\b\d{2}\s?[A-Z]{1,3}\s?\d{2,4}\b"), "info"),
    PIIPattern("pasaport", "Pasaport Numarası", re.compile(r"\b[A-Z]\s?\d{2}\s?\d{3}\s?\d{3}\b"), "warning"),
    PIIPattern("vergi_no", "Vergi Numarası", re.compile(r"\bV\.?D\.?\s*:?\s*\d{10}\b"), "info"),
    PIIPattern("sgk_no", "SGK Sicil Numarası", re.compile(r"\b\d{7,9}[-/]\d{2,4}\b"), "info"),
)


class PIIDetector:
    def __init__(self, patterns: Sequence[PIIPattern] = DEFAULT_PATTERNS) -> None:
        self.patterns = tuple(patterns)

    def detect(self, text: str) -> list[PIIFinding]:
        findings: list[PIIFinding] = []
        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                value = match.group()
                if pattern.validator and not pattern.validator(value):
                    continue
                findings.append(PIIFinding(pattern.code, pattern.label, self.mask(value), pattern.severity))
        return findings

    @staticmethod
    def mask(value: str) -> str:
        return f"{value[:3]}***{value[-2:]}" if len(value) > 5 else "***"

    def mask_text(self, text: str) -> str:
        """Metindeki tüm kişisel verileri maskelenmiş halleriyle değiştirir."""
        result = text
        for pattern in self.patterns:
            def _replacer(m: re.Match, p: PIIPattern = pattern) -> str:
                value = m.group()
                if p.validator and not p.validator(value):
                    return value
                return self.mask(value)
            result = pattern.regex.sub(_replacer, result)
        return result
