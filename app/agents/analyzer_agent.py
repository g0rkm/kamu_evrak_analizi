from app.agents.base_agent import LLMAgent
from app.models.analysis import ContentAnalysis, ExtractedEntity, MissingField


class AnalyzerAgent(LLMAgent):
    """İçerik analizi ve bilgi çıkarma agentı."""

    name = "AnalyzerAgent"
    system_prompt = """Sen bir kamu evrak analiz uzmanısın. Verilen evrak metnindeki önemli bilgileri çıkar ve eksik bilgileri tespit et.

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

    async def execute(self, text: str) -> ContentAnalysis:
        self.log("İçerik analizi başlatılıyor...")
        data = await self.ask_json(f"Aşağıdaki evrak metnini analiz et:\n\n{self.truncate(text)}")

        result = ContentAnalysis(
            entities=self.parse_items(ExtractedEntity, data.get("entities")),
            missing_fields=self.parse_items(MissingField, data.get("missing_fields")),
            keywords=[str(k).strip() for k in data.get("keywords") or [] if str(k).strip()],
        )
        self.log(f"Analiz tamamlandı: {len(result.entities)} varlık, {len(result.missing_fields)} eksik alan")
        return result
