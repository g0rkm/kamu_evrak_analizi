import os
import pymupdf  # PyMuPDF - fitz yerine pymupdf olarak import et
import pytesseract
from PIL import Image
from io import BytesIO
from app.config import get_settings
from app.models.document import ExtractedText

class OCRService:
    """PDF ve görüntü dosyalarından metin çıkarma servisi."""
    
    def __init__(self):
        settings = get_settings()
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    
    def extract_from_pdf(self, file_path: str) -> ExtractedText:
        """PDF dosyasından metin çıkar. Önce doğrudan metin, başarısızsa OCR."""
        doc = pymupdf.open(file_path)
        text_parts = []
        ocr_used = False
        
        for page in doc:
            text = page.get_text()
            if text.strip():
                text_parts.append(text)
            else:
                # Sayfa metin içermiyor, OCR dene
                ocr_used = True
                pix = page.get_pixmap(dpi=300)
                img = Image.open(BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(img, lang="tur")
                text_parts.append(ocr_text)
        
        doc.close()
        raw_text = "\n\n".join(text_parts)
        cleaned = self._clean_text(raw_text)
        
        return ExtractedText(
            raw_text=raw_text,
            cleaned_text=cleaned,
            language="tr",
            confidence=0.85 if not ocr_used else 0.65
        )
    
    def extract_from_image(self, file_path: str) -> ExtractedText:
        """Görüntü dosyasından OCR ile metin çıkar."""
        img = Image.open(file_path)
        raw_text = pytesseract.image_to_string(img, lang="tur")
        cleaned = self._clean_text(raw_text)
        
        return ExtractedText(
            raw_text=raw_text,
            cleaned_text=cleaned,
            language="tr",
            confidence=0.65
        )
    
    def extract_from_text_file(self, file_path: str) -> ExtractedText:
        """Düz metin dosyasından içerik oku."""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        
        return ExtractedText(
            raw_text=raw_text,
            cleaned_text=self._clean_text(raw_text),
            language="tr",
            confidence=1.0
        )
    
    def extract(self, file_path: str) -> ExtractedText:
        """Dosya türüne göre otomatik metin çıkar."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self.extract_from_pdf(file_path)
        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            return self.extract_from_image(file_path)
        elif ext in (".txt", ".md"):
            return self.extract_from_text_file(file_path)
        else:
            raise ValueError(f"Desteklenmeyen dosya türü: {ext}")
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Metni temizle: fazla boşlukları kaldır, satır sonlarını düzenle."""
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()
