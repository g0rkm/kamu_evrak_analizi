import asyncio

from app.agents.base_agent import LLMAgent
from app.models.analysis import LegislationMatch
from app.services.legislation_catalog import LegislationCatalog
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService, RetrievedChunk

LEGISLATION_SYSTEM_PROMPT = """Sen bir kamu hukuku ve mevzuat uzmanısın. Verilen evrak metnine ve ilgili mevzuat parçalarına bakarak mevzuat eşleştirmesi yap.

Aşağıda evrakla ilgili olabilecek mevzuat parçaları verilmiştir:
__RAG_CONTEXT__

Ayrıca mevzuat metadata veritabanı:
__LEGISLATION_DB__

Yanıtını SADECE aşağıdaki JSON formatında ver:
{
  "matches": [
    {"legislation_name": "mevzuat adı", "article": "madde numarası veya null", "relevance_score": 0.0-1.0, "summary": "ilgi açıklaması"}
  ]
}

En fazla 5 ilgili mevzuat döndür, relevance_score'a göre sırala."""


class LegislationAgent(LLMAgent):
    """Mevzuat eşleştirme agentı — RAG destekli."""

    name = "LegislationAgent"
    max_input_chars = 3000
    MAX_MATCHES = 5
    RAG_TOP_K = 8
    RAG_SNIPPET_CHARS = 1200

    def __init__(
        self,
        llm_service: LLMService,
        rag_service: RAGService | None = None,
        catalog: LegislationCatalog | None = None,
    ) -> None:
        super().__init__(llm_service)
        self.rag_service = rag_service or RAGService.shared()
        self.catalog = catalog or LegislationCatalog.load()
        self._rag_context = ""

    def build_system_prompt(self) -> str:
        return (LEGISLATION_SYSTEM_PROMPT
                .replace("__RAG_CONTEXT__", self._rag_context)
                .replace("__LEGISLATION_DB__", self.catalog.to_prompt()))

    @staticmethod
    def build_queries(text: str, document_type: str, keywords: list[str]) -> list[str]:
        parts = [document_type] if document_type else []
        if keywords:
            parts.append(" ".join(keywords[:10]))
        parts.append(text[:500])
        queries = [" ".join(parts)]
        if keywords:
            queries.append(" ".join(keywords[:5]))
        return queries

    def format_rag_context(self, hits: list[RetrievedChunk]) -> str:
        if not hits:
            return "İlgili mevzuat parçası bulunamadı."
        blocks = [
            f"--- Mevzuat Parçası {i} (skor: {hit.score:.2f}) ---\n"
            f"Kaynak: {hit.title} ({hit.type})\n"
            f"{hit.text[: self.RAG_SNIPPET_CHARS]}\n"
            for i, hit in enumerate(hits, 1)
        ]
        return "\n".join(blocks)

    async def execute(self, text: str, document_type: str = "", keywords: list[str] | None = None) -> list[LegislationMatch]:
        keywords = keywords or []
        self.log("Mevzuat eşleştirme başlatılıyor...")

        if self.rag_service.available:
            queries = self.build_queries(text, document_type, keywords)
            hits = await asyncio.to_thread(self.rag_service.search_multi, queries, self.RAG_TOP_K)
            self.log(f"RAG: {len(hits)} ilgili parça bulundu")
        else:
            hits = []
            self.log("RAG indeksi mevcut değil, yalnızca metadata kullanılıyor")
        self._rag_context = self.format_rag_context(hits)

        data = await self.ask_json(f"Evrak türü: {document_type}\n\nEvrak metni:\n{self.truncate(text)}")
        matches = self.parse_items(LegislationMatch, data.get("matches"))
        matches.sort(key=lambda m: m.relevance_score, reverse=True)
        matches = matches[: self.MAX_MATCHES]
        self.log(f"Mevzuat eşleştirme tamamlandı: {len(matches)} eşleşme")
        return matches
