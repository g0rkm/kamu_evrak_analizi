import asyncio

from app.agents.base_agent import BaseAgent
from app.models.document import ExtractedText
from app.services.ocr_service import OCRService


class OCRAgent(BaseAgent):
    """Evrak okuma ve metin çıkarma agentı."""

    name = "OCRAgent"

    def __init__(self, ocr_service: OCRService | None = None) -> None:
        super().__init__()
        self.ocr_service = ocr_service or OCRService()

    async def execute(self, file_path: str) -> ExtractedText:
        self.log("Metin çıkarma başlatılıyor...")
        # OCR CPU yoğun ve senkron; olay döngüsünü kilitlememesi için iş parçacığında çalışır.
        result = await asyncio.to_thread(self.ocr_service.extract, file_path)
        self.log(f"Metin çıkarıldı: {len(result.cleaned_text)} karakter, güven: {result.confidence}")
        return result
