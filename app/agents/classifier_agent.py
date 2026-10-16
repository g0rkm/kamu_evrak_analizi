from app.agents.base_agent import LLMAgent
from app.core.taxonomy import DOCUMENT_TYPES, UNKNOWN_DOCUMENT_TYPE
from app.models.analysis import ClassificationResult


def _build_prompt() -> str:
    type_lines = "\n".join(f"- {t.code}: {t.description}" for t in DOCUMENT_TYPES)
    return f"""Sen bir kamu evrak sınıflandırma uzmanısın. Verilen evrak metnini analiz ederek türünü belirle.

Evrak türleri:
{type_lines}

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{{"document_type": "tur_kodu", "confidence": 0.0-1.0, "sub_type": "alt_tur_veya_null", "reasoning": "sınıflandırma gerekçesi"}}"""


class ClassifierAgent(LLMAgent):
    """Evrak türü sınıflandırma agentı."""

    name = "ClassifierAgent"
    system_prompt = _build_prompt()
    max_input_chars = 3000

    async def execute(self, text: str) -> ClassificationResult:
        self.log("Evrak sınıflandırma başlatılıyor...")
        data = await self.ask_json(f"Aşağıdaki evrak metnini sınıflandır:\n\n{self.truncate(text)}")

        raw_type = str(data.get("document_type") or "")
        code = DOCUMENT_TYPES.resolve(raw_type)
        if code is None:
            self.log(f"Tanımsız tür döndü ('{raw_type}'), 'bilinmiyor' olarak işaretlendi")
            if not data.get("sub_type"):
                data["sub_type"] = raw_type or None
            code = UNKNOWN_DOCUMENT_TYPE
        data["document_type"] = code

        result = ClassificationResult.model_validate(data)
        self.log(f"Sınıflandırma: {result.document_type} (güven: {result.confidence})")
        return result
