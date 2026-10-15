import json
import os
from app.agents.base_agent import BaseAgent
from app.models.analysis import LegislationMatch

LEGISLATION_SYSTEM_PROMPT = """Sen bir kamu hukuku ve mevzuat uzmanısın. Verilen evrak metnine ve mevzuat veritabanına bakarak ilgili mevzuatları eşleştir.

Mevzuat veritabanı:
__LEGISLATION_DB__

Yanıtını SADECE aşağıdaki JSON formatında ver:
{
  "matches": [
    {"legislation_name": "mevzuat adı", "article": "madde numarası veya null", "relevance_score": 0.0-1.0, "summary": "ilgi açıklaması"}
  ]
}

En fazla 5 ilgili mevzuat döndür, relevance_score'a göre sırala."""

class LegislationAgent(BaseAgent):
    """Mevzuat eşleştirme agentı."""
    
    def __init__(self, llm_service):
        super().__init__(name="LegislationAgent", llm_service=llm_service)
        self.legislation_db = self._load_legislation()
    
    def _load_legislation(self) -> str:
        db_path = os.path.join(os.path.dirname(__file__), "..", "data", "legislation.json")
        db_path = os.path.normpath(db_path)
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except (FileNotFoundError, json.JSONDecodeError):
            return "[]"
    
    async def execute(self, text: str, document_type: str = "") -> list[LegislationMatch]:
        """Evrak metni için ilgili mevzuatları bul."""
        self.log("Mevzuat eşleştirme başlatılıyor...")
        system = LEGISLATION_SYSTEM_PROMPT.replace("__LEGISLATION_DB__", self.legislation_db)
        user_msg = f"Evrak türü: {document_type}\n\nEvrak metni:\n{text[:3000]}"
        data = await self.llm_service.chat_json(system, user_msg)
        matches = [LegislationMatch(**m) for m in data.get("matches", [])]
        self.log(f"Mevzuat eşleştirme tamamlandı: {len(matches)} eşleşme")
        return matches
