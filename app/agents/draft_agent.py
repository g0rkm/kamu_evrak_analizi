from app.agents.base_agent import LLMAgent
from app.core.taxonomy import DRAFT_TYPES
from app.models.analysis import ExtractedEntity
from app.models.draft import DraftResponse


def _build_prompt() -> str:
    type_lines = "\n".join(f"- {d.code}: {d.description}" for d in DRAFT_TYPES)
    codes = "/".join(DRAFT_TYPES.codes())
    return f"""Sen bir kamu yazışma uzmanısın. Verilen evrak analiz sonuçlarına dayanarak uygun bir resmî yazı taslağı oluştur.

Yazı türleri:
{type_lines}

Taslak resmî üsluba uygun olmalı. Kişisel verileri (TC kimlik no, IBAN, telefon) taslağa AKTARMA.

ÖNEMLİ KURALLAR:
- "body" alanı YALNIZCA yazının gövde paragraflarını içerir. İçine selamlama ("İlgi:", "Sayın..."), kapanış kalıbı ("...arz ederim", "...rica ederim", "Gereğini..."), imza bloğu veya "Ek:" satırı YAZMA — bunları şablon otomatik ekler. Aksi halde çift kapanış / çift ek oluşur.
- formal_greeting: Yalnızca İlgi referansının İÇERİĞİ (ör. "29.06.2012 tarihli ve 2012/26 sayılı Genelge"). Başına "İlgi:" YAZMA. İlgi yoksa boş string.
- attachments_note: Yalnızca EK ADI (ör. "2012/26 Sayılı Genelge Örneği"). Başına "Ek:" YAZMA. Ek yoksa null.
- subject: Kısa konu başlığı.
- closing: Doldurulabilir ama son metinde kullanılmaz (kapanış şablondan gelir).

Yanıtını SADECE aşağıdaki JSON formatında ver:
{{
  "draft_type": "{codes}",
  "subject": "Konu başlığı",
  "body": "Yazı gövdesi (YALNIZCA paragraflar, kapanış/imza yok)",
  "formal_greeting": "İlgi referansının içeriği (İlgi: eki olmadan) veya boş string",
  "closing": "Kapanış kalıbı",
  "attachments_note": "Yalnızca ek adı (Ek: eki olmadan) veya null",
  "tone_check": "Üslup değerlendirmesi"
}}"""


class DraftAgent(LLMAgent):
    """Resmî yazı taslağı oluşturma agentı."""

    name = "DraftAgent"
    system_prompt = _build_prompt()
    max_input_chars = 3000

    async def execute(
        self, text: str, document_type: str, summary: str, entities: list[ExtractedEntity] | None = None
    ) -> DraftResponse:
        self.log("Yazı taslağı oluşturma başlatılıyor...")
        entity_info = "\n".join(f"- {e.entity_type}: {e.value}" for e in entities or [])
        user_msg = f"""Evrak türü: {document_type}
Evrak özeti: {summary or 'Belirtilmemiş'}
Çıkarılan bilgiler:
{entity_info or '- Yok'}

Orijinal evrak metni:
{self.document(text)}

Bu evraka uygun bir resmî cevap/işlem yazısı taslağı oluştur."""

        data = await self.ask_json(user_msg)
        data["draft_type"] = DRAFT_TYPES.resolve(str(data.get("draft_type") or "")) or "ust_yazi"
        result = DraftResponse.model_validate(data)
        self.log(f"Taslak oluşturuldu: {result.draft_type} - {result.subject}")
        return result
