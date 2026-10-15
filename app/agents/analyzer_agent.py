from app.agents.base_agent import BaseAgent
from app.models.analysis import ExtractedEntity, MissingField

ANALYSIS_SYSTEM_PROMPT = """Sen bir kamu evrak analiz uzmanısın. Verilen evrak metnindeki önemli bilgileri çıkar ve eksik bilgileri tespit et.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{
  "entities": [
    {"entity_type": "tarih/kurum/kisi/konu/referans_no/adres/telefon", "value": "değer", "position": "metindeki konum açıklaması"}
  ],
  "missing_fields": [
    {"field_name": "alan_adi", "description": "açıklama", "is_critical": true/false}
  ],
  "keywords": ["anahtar", "kelimeler"]
}

Olası eksik alanlar: tarih, sayı/referans numarası, imza, gönderen kurum, alıcı kurum, konu başlığı, ek bilgisi."""

class AnalyzerAgent(BaseAgent):
    """İçerik analizi ve bilgi çıkarma agentı."""
    
    def __init__(self, llm_service):
        super().__init__(name="AnalyzerAgent", llm_service=llm_service)
    
    async def execute(self, text: str) -> dict:
        """Evrak metnini analiz et: entity çıkar, eksik alanları bul."""
        self.log("İçerik analizi başlatılıyor...")
        data = await self.llm_service.chat_json(
            ANALYSIS_SYSTEM_PROMPT,
            f"Aşağıdaki evrak metnini analiz et:\n\n{text[:4000]}"
        )
        entities = [ExtractedEntity(**e) for e in data.get("entities", [])]
        missing = [MissingField(**m) for m in data.get("missing_fields", [])]
        keywords = data.get("keywords", [])
        self.log(f"Analiz tamamlandı: {len(entities)} varlık, {len(missing)} eksik alan")
        return {"entities": entities, "missing_fields": missing, "keywords": keywords}
