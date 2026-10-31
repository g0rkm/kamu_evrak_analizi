from app.agents.base_agent import LLMAgent
from app.core.taxonomy import DOCUMENT_TYPES, UNKNOWN_DOCUMENT_TYPE
from app.models.analysis import ClassificationResult


def _build_prompt() -> str:
    type_lines = "\n".join(f"- {t.code}: {t.description}" for t in DOCUMENT_TYPES)
    return f"""Sen bir kamu evrak sınıflandırma uzmanısın. Verilen evrak metnini analiz ederek türünü belirle.

Evrak türleri:
{type_lines}

ÖNEMLİ AYIRT EDİCİ KURALLAR:

1. DİLEKÇE vs RESMİ YAZI:
   - "Dilekçe" bir vatandaşın veya kişinin kuruma hitaben yazdığı başvurudur. "Rica ederim", "Arz ederim", "Saygılarımla", "başvurumun" gibi ifadeler içerir. Genellikle "T.C. ... BAŞKANLIĞINA" veya "... MÜDÜRLÜĞÜNE" gibi hitap ile başlar.
   - "Resmî yazı" ise bir kurumun başka bir kuruma yazdığı yazıdır. "Sayı:", "Konu:", "İlgi:" gibi resmî üst yazı unsurları içerir ve genellikle kurum başlıklı kâğıttadır.

2. KARARNAME vs YÖNETMELİK:
   - "Kararname" Cumhurbaşkanlığı veya Bakanlar Kurulu tarafından çıkarılan üst düzey düzenleyici işlemdir. "Cumhurbaşkanlığı Kararnamesi", "KHK", "Kanun Hükmünde Kararname" ifadeleri içerir.
   - "Yönetmelik" ise kurumların çıkardığı alt düzey düzenleyici işlemdir. "Yönetmelik" kelimesini başlığında taşır, "madde", "hüküm", "yürürlük" gibi mevzuat dilini kullanır.

3. GENELGE: "Genelge" kelimesi başlıkta veya metin içinde açıkça geçmelidir. "Tüm birimlere", "tüm personele" ifadeleri ipucudur.

4. KANUN vs DİĞER MEVZUAT: "Kanun" veya "Kanunu" başlıkta geçmelidir. Sadece kanuna atıf yapılması (ör. "4982 sayılı Kanun kapsamında") evrakı kanun yapmaz.

5. SPESİFİKLİK KURALI: Mümkün olan en spesifik türü seç. Örneğin, bir evrak hem "resmi_yazi" hem de "genelge" olabilir, ancak genelge daha spesifiktir.

6. GÜVENİLİRLİK (confidence) KURALLARI:
   - Başlıkta evrak türü açıkça belirtilmişse: 0.85-0.95
   - Metin içeriğinden güçlü ipuçları varsa: 0.70-0.85
   - Belirsiz veya birden fazla türe uyabilecek içerik: 0.40-0.65
   - Çok kısa veya bozuk metin: 0.20-0.40

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{{"document_type": "tur_kodu", "confidence": 0.0-1.0, "sub_type": "alt_tur_veya_null", "reasoning": "sınıflandırma gerekçesi"}}"""


class ClassifierAgent(LLMAgent):
    """Evrak türü sınıflandırma agentı."""

    name = "ClassifierAgent"
    system_prompt = _build_prompt()
    max_input_chars = 3000

    async def execute(self, text: str) -> ClassificationResult:
        self.log("Evrak sınıflandırma başlatılıyor...")
        data = await self.ask_json(f"Aşağıdaki evrak metnini sınıflandır:\n\n{self.document(text)}")

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
