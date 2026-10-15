from app.agents.base_agent import BaseAgent
from app.models.analysis import ClassificationResult

CLASSIFICATION_SYSTEM_PROMPT = """Sen bir kamu evrak siniflandirma uzmanisin. Verilen evrak metnini analiz ederek turunu belirle.

Evrak turleri:
- dilekce: Vatandas veya kurum tarafindan yazilan dilekce
- resmi_yazi: Kurumlar arasi resmi ust yazi
- talep_yazisi: Bir sey talep eden resmi yazi
- bilgilendirme: Bilgilendirme amacli yazi
- gorus_sorma: Gorus talep eden yazi
- sikayet: Sikayet iceren dilekce veya yazi
- kurum_ici: Kurum ici yazisma/not
- genelge: Genelge veya duyuru
- rapor: Rapor veya degerlendirme belgesi
- tutanak: Toplanti veya olay tutanagi
- yonetmelik: Yonetmelik (duzenleyici islem)
- teblig: Teblig veya resmi tebligi
- kanun: Kanun metni veya kanun degisikligi
- karar: Karar, kurul karari, Cumhurbaskanligi karari
- kararname: Cumhurbaskanligi kararnamesi veya KHK
- ilan: Resmi ilan veya duyuru ilani
- yonerge: Yonerge, usul ve esaslar belgesi
- sozlesme: Sozlesme, protokol veya mutabakat

Yanitini SADECE asagidaki JSON formatinda ver, baska hicbir sey yazma:
{"document_type": "tur_adi", "confidence": 0.0-1.0, "sub_type": "alt_tur_veya_null", "reasoning": "siniflandirma gerekcesi"}"""

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
