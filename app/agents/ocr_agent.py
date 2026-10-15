from app.agents.base_agent import BaseAgent
from app.services.ocr_service import OCRService
from app.models.document import Document, ExtractedText

class OCRAgent(BaseAgent):
    """Evrak okuma ve metin çıkarma agentı."""
    
    def __init__(self, llm_service=None):
        super().__init__(name="OCRAgent", llm_service=llm_service)
        self.ocr_service = OCRService()
    
    async def execute(self, file_path: str, file_type: str = "auto") -> ExtractedText:
        """Verilen dosyadan metin çıkar."""
        self.log(f"Metin çıkarma başlatılıyor: {file_path}")
        try:
            result = self.ocr_service.extract(file_path)
            self.log(f"Metin çıkarıldı: {len(result.cleaned_text)} karakter, güven: {result.confidence}")
            return result
        except Exception as e:
            self.log(f"Metin çıkarma hatası: {str(e)}")
            raise
