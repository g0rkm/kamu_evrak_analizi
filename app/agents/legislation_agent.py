import json
import os
from app.agents.base_agent import BaseAgent
from app.models.analysis import LegislationMatch
from app.services.rag_service import RAGService

LEGISLATION_SYSTEM_PROMPT = """Sen bir kamu hukuku ve mevzuat uzmanisin. Verilen evrak metnine ve ilgili mevzuat parcalarina bakarak mevzuat eslestirmesi yap.

Asagida evrakla ilgili olabilecek mevzuat parcalari verilmistir:
__RAG_CONTEXT__

Ayrica mevzuat metadata veritabani:
__LEGISLATION_DB__

Yanitini SADECE asagidaki JSON formatinda ver:
{
  "matches": [
    {"legislation_name": "mevzuat adi", "article": "madde numarasi veya null", "relevance_score": 0.0-1.0, "summary": "ilgi aciklamasi"}
  ]
}

En fazla 5 ilgili mevzuat dondur, relevance_score'a gore sirala."""


class LegislationAgent(BaseAgent):
    """Mevzuat eslestirme agenti - RAG destekli."""

    def __init__(self, llm_service):
        super().__init__(name="LegislationAgent", llm_service=llm_service)
        self.rag_service = RAGService()
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

    def _build_query(self, text: str, document_type: str, keywords: list[str]) -> str:
        """Evrak metninden RAG arama sorgusu olustur."""
        parts = []
        if document_type:
            parts.append(document_type)
        if keywords:
            parts.append(" ".join(keywords[:10]))
        parts.append(text[:500])
        return " ".join(parts)

    def _format_rag_context(self, rag_results: list[dict]) -> str:
        """RAG sonuclarini LLM prompt'una uygun formata cevir."""
        if not rag_results:
            return "Ilgili mevzuat parcasi bulunamadi."
        lines = []
        for i, r in enumerate(rag_results, 1):
            lines.append(f"--- Mevzuat Parcasi {i} (skor: {r['score']:.2f}) ---")
            lines.append(f"Kaynak: {r['title']} ({r['type']})")
            lines.append(r["text"][:1200])
            lines.append("")
        return "\n".join(lines)

    async def execute(self, text: str, document_type: str = "", keywords: list[str] = None) -> list[LegislationMatch]:
        """Evrak metni icin ilgili mevzuatlari bul (RAG destekli)."""
        if keywords is None:
            keywords = []
        self.log("Mevzuat eslestirme baslatiliyor...")

        # RAG ile ilgili mevzuat parcalarini bul
        if self.rag_service.available:
            query = self._build_query(text, document_type, keywords)
            queries = [query]
            if keywords:
                queries.append(" ".join(keywords[:5]))
            rag_results = self.rag_service.search_multi(queries, top_k=8)
            self.log(f"RAG: {len(rag_results)} ilgili parca bulundu")
        else:
            rag_results = []
            self.log("RAG indeksi mevcut degil, sadece metadata kullaniliyor")

        rag_context = self._format_rag_context(rag_results)

        system = LEGISLATION_SYSTEM_PROMPT.replace("__RAG_CONTEXT__", rag_context)
        system = system.replace("__LEGISLATION_DB__", self.legislation_db)

        user_msg = f"Evrak turu: {document_type}\n\nEvrak metni:\n{text[:3000]}"
        data = await self.llm_service.chat_json(system, user_msg)

        matches = [LegislationMatch(**m) for m in data.get("matches", [])]
        self.log(f"Mevzuat eslestirme tamamlandi: {len(matches)} esleme")
        return matches
