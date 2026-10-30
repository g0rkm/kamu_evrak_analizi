"""Dosyalardan metin çıkarma servisi (strateji deseni).

Her dosya türü için bir `TextExtractor` alt sınıfı vardır; `OCRService` uzantıya
göre uygun çıkarıcıyı seçen bir cephedir (facade).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import ClassVar, Sequence

import pymupdf
import pytesseract
from PIL import Image, UnidentifiedImageError

from app.config import Settings, get_settings
from app.core.exceptions import TextExtractionError, UnsupportedFileTypeError
from app.models.document import ExtractedText


class TextCleaner:
    @staticmethod
    def clean(text: str) -> str:
        """Fazla boşlukları kaldırır, satır sonlarını düzenler."""
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return "\n".join(line.strip() for line in text.split("\n")).strip()


class TesseractEngine:
    """pytesseract üzerinde ince bir sarmalayıcı; kurulum hatalarını anlaşılır kılar."""

    def __init__(self, command: str, language: str) -> None:
        pytesseract.pytesseract.tesseract_cmd = command
        self.language = language

    def image_to_text(self, image: Image.Image) -> str:
        try:
            return pytesseract.image_to_string(image, lang=self.language)
        except pytesseract.TesseractNotFoundError as exc:
            raise TextExtractionError(
                "Görüntüden metin okumak için sunucuda Tesseract OCR kurulu olmalıdır."
            ) from exc
        except pytesseract.TesseractError as exc:
            raise TextExtractionError(f"OCR işlemi başarısız oldu: {exc}") from exc


class TextExtractor(ABC):
    extensions: ClassVar[frozenset[str]] = frozenset()

    def supports(self, extension: str) -> bool:
        return extension in self.extensions

    @abstractmethod
    def extract(self, path: Path) -> ExtractedText:
        ...

    @staticmethod
    def _result(raw_text: str, confidence: float) -> ExtractedText:
        return ExtractedText(raw_text=raw_text, cleaned_text=TextCleaner.clean(raw_text), language="tr", confidence=confidence)


class PlainTextExtractor(TextExtractor):
    extensions = frozenset({".txt", ".md"})
    _ENCODINGS = ("utf-8-sig", "cp1254", "latin-1")

    def extract(self, path: Path) -> ExtractedText:
        data = path.read_bytes()
        for encoding in self._ENCODINGS:
            try:
                return self._result(data.decode(encoding), confidence=1.0)
            except UnicodeDecodeError:
                continue
        raise TextExtractionError("Metin dosyasının karakter kodlaması çözülemedi.")


class DocxExtractor(TextExtractor):
    extensions = frozenset({".doc", ".docx"})

    def extract(self, path: Path) -> ExtractedText:
        try:
            import docx
        except ImportError as exc:
            raise TextExtractionError("DOCX desteği için python-docx paketi gereklidir.") from exc
        try:
            document = docx.Document(path)
            parts = [p.text for p in document.paragraphs if p.text.strip()]
            raw_text = "\n\n".join(parts)
        except Exception as exc:
            raise TextExtractionError("Word dosyası açılamadı veya bozuk.") from exc
        if not raw_text.strip():
            raise TextExtractionError("Word dosyasında okunabilir metin bulunamadı.")
        return self._result(raw_text, confidence=0.95)


class ImageExtractor(TextExtractor):
    extensions = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"})

    def __init__(self, engine: TesseractEngine) -> None:
        self.engine = engine

    def extract(self, path: Path) -> ExtractedText:
        try:
            with Image.open(path) as image:
                raw_text = self.engine.image_to_text(image)
        except UnidentifiedImageError as exc:
            raise TextExtractionError("Görüntü dosyası okunamadı veya bozuk.") from exc
        return self._result(raw_text, confidence=0.65)


class PdfExtractor(TextExtractor):
    """Önce gömülü metni okur; metin içermeyen (taranmış) sayfalarda OCR'a düşer."""

    extensions = frozenset({".pdf"})
    OCR_DPI = 300

    def __init__(self, engine: TesseractEngine) -> None:
        self.engine = engine

    def extract(self, path: Path) -> ExtractedText:
        try:
            document = pymupdf.open(path)
        except Exception as exc:  # pymupdf bozuk dosyada farklı hata türleri fırlatabilir
            raise TextExtractionError("PDF dosyası açılamadı veya bozuk.") from exc

        parts: list[str] = []
        ocr_used = False
        with document:
            for page in document:
                text = page.get_text()
                if text.strip():
                    parts.append(text)
                    continue
                ocr_used = True
                pixmap = page.get_pixmap(dpi=self.OCR_DPI)
                with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                    parts.append(self.engine.image_to_text(image))

        return self._result("\n\n".join(parts), confidence=0.65 if ocr_used else 0.85)


class OCRService:
    """Uzantıya göre uygun çıkarıcıyı seçen cephe."""

    def __init__(self, settings: Settings | None = None, extractors: Sequence[TextExtractor] | None = None) -> None:
        if extractors is None:
            settings = settings or get_settings()
            engine = TesseractEngine(settings.TESSERACT_CMD, settings.OCR_LANGUAGE)
            extractors = (PdfExtractor(engine), ImageExtractor(engine), DocxExtractor(), PlainTextExtractor())
        self.extractors = tuple(extractors)

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset().union(*(e.extensions for e in self.extractors))

    def extract(self, file_path: str | Path) -> ExtractedText:
        path = Path(file_path)
        extension = path.suffix.lower()
        for extractor in self.extractors:
            if extractor.supports(extension):
                return extractor.extract(path)
        raise UnsupportedFileTypeError(f"Desteklenmeyen dosya türü: {extension or 'uzantısız'}")
