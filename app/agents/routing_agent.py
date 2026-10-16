from app.agents.base_agent import LLMAgent
from app.core.taxonomy import DEFAULT_PRIORITY, ORG_UNITS, PRIORITIES
from app.models.draft import RoutingDecision


def _build_prompt() -> str:
    unit_lines = "\n".join(f"- {u.label}: {u.description}" for u in ORG_UNITS)
    priorities = "/".join(PRIORITIES.codes())
    return f"""Sen bir kamu kurumu evrak yönlendirme uzmanısın. Verilen evrak bilgilerine göre evrakın hangi birime yönlendirilmesi gerektiğine karar ver.

Mevcut birimler:
{unit_lines}

Öncelik seviyeleri: {", ".join(PRIORITIES.codes())}

Yanıtını SADECE aşağıdaki JSON formatında ver (birim adlarını listedeki gibi aynen yaz):
{{
  "target_unit": "birim adı",
  "reasoning": "yönlendirme gerekçesi",
  "priority": "{priorities}",
  "alternative_units": ["alternatif birim 1"],
  "requires_action": ["birimden beklenen eylem 1", "eylem 2"]
}}"""


class RoutingAgent(LLMAgent):
    """Birim yönlendirme agentı."""

    name = "RoutingAgent"
    system_prompt = _build_prompt()
    max_input_chars = 2000

    @staticmethod
    def canonical_unit(name: str) -> str:
        code = ORG_UNITS.resolve(name)
        return ORG_UNITS.label(code) if code else name.strip()

    async def execute(
        self, text: str, document_type: str, summary: str, keywords: list[str] | None = None
    ) -> RoutingDecision:
        self.log("Birim yönlendirme başlatılıyor...")
        user_msg = f"""Evrak türü: {document_type}
Evrak özeti: {summary or 'Belirtilmemiş'}
Anahtar kelimeler: {", ".join(keywords) if keywords else "Belirtilmemiş"}

Evrak metni:
{self.document(text)}

Bu evrakın hangi birime yönlendirilmesi gerektiğine karar ver."""

        data = await self.ask_json(user_msg)
        data["target_unit"] = self.canonical_unit(str(data.get("target_unit") or ""))
        data["priority"] = PRIORITIES.resolve(str(data.get("priority") or "")) or DEFAULT_PRIORITY
        data["alternative_units"] = [self.canonical_unit(str(u)) for u in data.get("alternative_units") or []]
        data["requires_action"] = [str(a) for a in data.get("requires_action") or []]

        result = RoutingDecision.model_validate(data)
        self.log(f"Yönlendirme: {result.target_unit} (öncelik: {result.priority})")
        return result
