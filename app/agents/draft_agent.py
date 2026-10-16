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

Taslak resmî üsluba uygun olmalı. "T.C." ile başlayan kurum başlığı, sayı, konu, ilgi, metin gövdesi ve imza bloğu içermeli.
Kişisel verileri (TC kimlik no, IBAN, telefon) taslağa AKTARMA.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{{
  "draft_type": "{codes}",
  "subject": "Konu başlığı",
  "body": "Yazı gövdesi (paragraflar halinde)",
  "formal_greeting": "İlgi: ... veya Sayın ...",
  "closing": "Kapanış metni ve imza bloğu",
  "attachments_note": "Ek bilgisi veya null",
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
