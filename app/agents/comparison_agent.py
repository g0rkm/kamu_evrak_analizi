from app.agents.base_agent import LLMAgent
from app.models.api import ComparisonResult


class ComparisonAgent(LLMAgent):
    """İki evrakı karşılaştırıp benzerlik, fark ve ortak temaları çıkaran agent."""

    name = "ComparisonAgent"
    max_input_chars = 3000
    system_prompt = """Sen bir kamu evrak karşılaştırma uzmanısın. İki evrak metnini karşılaştır.

Yanıtını SADECE aşağıdaki JSON formatında ver:
{
  "similarity_score": 0.0-1.0,
  "common_themes": ["ortak tema 1", "ortak tema 2"],
  "differences": ["fark 1", "fark 2"],
  "text1_unique": "birinci evraka özgü konular",
  "text2_unique": "ikinci evraka özgü konular",
  "recommendation": "karşılaştırma özeti ve öneri"
}"""

    async def execute(self, text1: str, text2: str) -> ComparisonResult:
        self.log("Evrak karşılaştırma başlatılıyor...")
        data = await self.ask_json(f"Evrak 1:\n{self.document(text1)}\n\n---\n\nEvrak 2:\n{self.document(text2)}")
        data["common_themes"] = [str(t) for t in data.get("common_themes") or []]
        data["differences"] = [str(d) for d in data.get("differences") or []]
        result = ComparisonResult.model_validate(data)
        self.log(f"Karşılaştırma tamamlandı: benzerlik {result.similarity_score:.2f}")
        return result
