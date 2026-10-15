from app.agents.base_agent import BaseAgent
from app.models.draft import RoutingDecision

ROUTING_SYSTEM_PROMPT = """Sen bir kamu kurumu evrak yönlendirme uzmanısın. Verilen evrak bilgilerine göre evrakın hangi birime yönlendirilmesi gerektiğine karar ver.

Mevcut birimler:
- Hukuk Müşavirliği: Hukuki konular, davalar, sözleşmeler, mevzuat yorumu
- İnsan Kaynakları Daire Başkanlığı: Personel işlemleri, atama, izin, özlük
- Strateji Geliştirme Daire Başkanlığı: Bütçe, planlama, performans, istatistik
- Bilgi Teknolojileri Daire Başkanlığı: IT altyapı, yazılım, siber güvenlik
- İdari ve Mali İşler Daire Başkanlığı: Satın alma, ihale, lojistik, taşınır
- Basın ve Halkla İlişkiler Müdürlüğü: Medya, CİMER, halkla ilişkiler
- Teftiş Kurulu Başkanlığı: Denetim, soruşturma, teftiş
- Genel Müdürlük (ilgili): Kurumun ana faaliyet alanına göre

Öncelik seviyeleri: acil, yuksek, normal, dusuk

Yanıtını SADECE aşağıdaki JSON formatında ver:
{
  "target_unit": "birim adı",
  "reasoning": "yönlendirme gerekçesi",
  "priority": "acil/yuksek/normal/dusuk",
  "alternative_units": ["alternatif birim 1"],
  "requires_action": ["birimden beklenen eylem 1", "eylem 2"]
}"""

class RoutingAgent(BaseAgent):
    """Birim yönlendirme agentı."""
    
    def __init__(self, llm_service):
        super().__init__(name="RoutingAgent", llm_service=llm_service)
    
    async def execute(self, text: str, document_type: str, summary: str, keywords: list = None) -> RoutingDecision:
        """Evrakı uygun birime yönlendir."""
        self.log("Birim yönlendirme başlatılıyor...")
        kw_str = ", ".join(keywords) if keywords else "Belirtilmemiş"
        user_msg = f"""Evrak türü: {document_type}
Evrak özeti: {summary}
Anahtar kelimeler: {kw_str}

Evrak metni:
{text[:2000]}

Bu evrakın hangi birime yönlendirilmesi gerektiğine karar ver."""
        
        data = await self.llm_service.chat_json(ROUTING_SYSTEM_PROMPT, user_msg)
        result = RoutingDecision(**data)
        self.log(f"Yönlendirme: {result.target_unit} (öncelik: {result.priority})")
        return result
