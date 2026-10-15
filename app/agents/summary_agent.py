from app.agents.base_agent import BaseAgent

SUMMARY_SYSTEM_PROMPT = """Sen bir kamu evrak özetleme uzmanısın. Verilen evrak metninin kısa ve öz bir özetini oluştur.

Kurallar:
- Özet en fazla 3-4 cümle olmalı
- Resmi ve nesnel bir dil kullan
- Evrakın amacını, konusunu ve varsa talep/isteği belirt
- Tarihleri ve önemli referansları koru

Yanıtını düz metin olarak ver, JSON formatında DEĞİL."""

class SummaryAgent(BaseAgent):
    """Evrak özetleme agentı."""
    
    def __init__(self, llm_service):
        super().__init__(name="SummaryAgent", llm_service=llm_service)
    
    async def execute(self, text: str, document_type: str = "") -> str:
        """Evrak metninin özetini oluştur."""
        self.log("Özet oluşturma başlatılıyor...")
        user_msg = f"Evrak türü: {document_type}\n\nEvrak metni:\n{text[:4000]}"
        summary = await self._call_llm(SUMMARY_SYSTEM_PROMPT, user_msg)
        self.log(f"Özet oluşturuldu: {len(summary)} karakter")
        return summary.strip()
