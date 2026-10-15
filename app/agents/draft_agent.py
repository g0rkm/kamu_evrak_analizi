from app.agents.base_agent import BaseAgent
from app.models.draft import DraftResponse

DRAFT_SYSTEM_PROMPT = """Sen bir kamu yazışma uzmanısın. Verilen evrak analiz sonuçlarına dayanarak uygun bir resmî yazı taslağı oluştur.

Yazı türleri:
- ust_yazi: Kurumlar arası resmi üst yazı
- cevap_yazisi: Gelen yazıya cevap
- bilgilendirme: Bilgilendirme yazısı
- ic_yazisma: Kurum içi yazışma

Taslak resmî üsluba uygun olmalı. "T.C." ile başlayan kurum başlığı, sayı, konu, ilgi, metin gövdesi ve imza bloğu içermeli.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{
  "draft_type": "ust_yazi/cevap_yazisi/bilgilendirme/ic_yazisma",
  "subject": "Konu başlığı",
  "body": "Yazı gövdesi (paragraflar halinde)",
  "formal_greeting": "İlgi: ... veya Sayın ...",
  "closing": "Kapanış metni ve imza bloğu",
  "attachments_note": "Ek bilgisi veya null",
  "tone_check": "Üslup değerlendirmesi"
}"""

class DraftAgent(BaseAgent):
    """Resmî yazı taslağı oluşturma agentı."""
    
    def __init__(self, llm_service):
        super().__init__(name="DraftAgent", llm_service=llm_service)
    
    async def execute(self, text: str, document_type: str, summary: str, entities: list = None) -> DraftResponse:
        """Analiz sonuçlarına göre resmî yazı taslağı oluştur."""
        self.log("Yazı taslağı oluşturma başlatılıyor...")
        
        entity_info = ""
        if entities:
            entity_parts = [f"- {e.entity_type}: {e.value}" for e in entities]
            entity_info = "\n".join(entity_parts)
        
        user_msg = f"""Evrak türü: {document_type}
Evrak özeti: {summary}
Çıkarılan bilgiler:
{entity_info}

Orijinal evrak metni:
{text[:3000]}

Bu evraka uygun bir resmî cevap/işlem yazısı taslağı oluştur."""
        
        data = await self.llm_service.chat_json(DRAFT_SYSTEM_PROMPT, user_msg)
        result = DraftResponse(**data)
        self.log(f"Taslak oluşturuldu: {result.draft_type} - {result.subject}")
        return result
