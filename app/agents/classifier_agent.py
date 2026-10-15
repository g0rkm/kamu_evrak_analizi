from app.agents.base_agent import BaseAgent
from app.models.analysis import ClassificationResult

CLASSIFICATION_SYSTEM_PROMPT = """Sen bir kamu evrak sınıflandırma uzmanısın. Verilen evrak metnini analiz ederek türünü belirle.

Evrak türleri:
- dilekce: Vatandaş veya kurum tarafından yazılan dilekçe
- resmi_yazi: Kurumlar arası resmi üst yazı
- talep_yazisi: Bir şey talep eden resmi yazı
- bilgilendirme: Bilgilendirme amaçlı yazı
- gorus_sorma: Görüş talep eden yazı
- sikayet: Şikayet içeren dilekçe veya yazı
- kurum_ici: Kurum içi yazışma/not
- genelge: Genelge veya duyuru
- rapor: Rapor veya değerlendirme belgesi
- tutanak: Toplantı veya olay tutanağı

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{"document_type": "tur_adi", "confidence": 0.0-1.0, "sub_type": "alt_tur_veya_null", "reasoning": "sınıflandırma gerekçesi"}"""

class ClassifierAgent(BaseAgent):
    """Evrak türü sınıflandırma agentı."""
    
    def __init__(self, llm_service):
        super().__init__(name="ClassifierAgent", llm_service=llm_service)
    
    async def execute(self, text: str) -> ClassificationResult:
        """Evrak metnini sınıflandır."""
        self.log("Evrak sınıflandırma başlatılıyor...")
        data = await self.llm_service.chat_json(
            CLASSIFICATION_SYSTEM_PROMPT,
            f"Aşağıdaki evrak metnini sınıflandır:\n\n{text[:3000]}"
        )
        result = ClassificationResult(**data)
        self.log(f"Sınıflandırma: {result.document_type} (güven: {result.confidence})")
        return result
