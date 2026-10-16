from app.agents.base_agent import LLMAgent


class SummaryAgent(LLMAgent):
    """Evrak özetleme agentı."""

    name = "SummaryAgent"
    system_prompt = """Sen bir kamu evrak özetleme uzmanısın. Verilen evrak metninin kısa ve öz bir özetini oluştur.

Kurallar:
- Özet en fazla 3-4 cümle olmalı
- Resmi ve nesnel bir dil kullan
- Evrakın amacını, konusunu ve varsa talep/isteği belirt
- Tarihleri ve önemli referansları koru

Yanıtını düz metin olarak ver, JSON formatında DEĞİL."""

    async def execute(self, text: str, document_type: str = "") -> str:
        self.log("Özet oluşturma başlatılıyor...")
        summary = await self.ask_text(f"Evrak türü: {document_type}\n\nEvrak metni:\n{self.document(text)}")
        self.log(f"Özet oluşturuldu: {len(summary)} karakter")
        return summary
