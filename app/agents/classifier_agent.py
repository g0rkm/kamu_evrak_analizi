from app.agents.base_agent import LLMAgent
from app.core.taxonomy import DOCUMENT_TYPES, UNKNOWN_DOCUMENT_TYPE
from app.models.analysis import ClassificationResult


def _build_prompt() -> str:
    type_lines = "\n".join(f"- {t.code}: {t.description}" for t in DOCUMENT_TYPES)
    return f"""Sen bir kamu evrak sınıflandırma uzmanısın. Verilen evrak metnini analiz ederek türünü belirle.

Evrak türleri:
{type_lines}

SINIFLANDIRMA ADIMLARI (sırayla uygula):

ADIM 1 — BAŞLIĞI OKU: Evrakın ilk 3-5 satırındaki başlığı veya üst bilgiyi incele. Evrak türü genellikle burada açıkça belirtilir (örn. "DİLEKÇE", "TUTANAK", "YÖNETMELİK", "GENELGE", "RAPOR"). Başlıkta tür açıkça yazıyorsa o türü seç.

ADIM 2 — YAPISAL UNSURLARI TARA:
- Dilekçe: Bir kişinin kuruma hitabı ("...BAŞKANLIĞINA"), birinci tekil şahıs ("başvurumun", "talebimin"), vatandaş dilekçe kalıpları ("Arz ederim", "Rica ederim", "Saygılarımla"), Ad Soyad + Tarih + İmza bloğu altta
- Resmî yazı: Kurumdan kuruma yazı, "Sayı:", "Konu:", "İlgi:" üst yazı başlıkları, resmî kapanış ("Bilgilerinize arz/rica ederim")
- Kararname: "Cumhurbaşkanlığı Kararnamesi", "KHK", "Kanun Hükmünde Kararname" ifadeleri, madde yapısı, Resmî Gazete yayımı
- Yönetmelik: Başlıkta "YÖNETMELİK" kelimesi, "BİRİNCİ BÖLÜM", "Amaç, Kapsam, Dayanak", maddeler, geçici maddeler, yürürlük-yürütme
- Kanun: Başlıkta "KANUN" veya "KANUNU", TBMM'de kabul, kanun numarası
- Karar: "KARAR", "Kurul Kararı", tek bir konuda alınan karar, atama kararı
- Genelge: "GENELGE" başlığı, "Tüm birimlere/personele duyurulur"
- Tutanak: "TUTANAK" başlığı, tarih/yer/katılımcılar, gündem maddeleri, kararlar
- Rapor: "RAPOR" başlığı, amaç-bulgular-sonuç yapısı
- Sözleşme: "SÖZLEŞME" veya "PROTOKOL" başlığı, taraflar, maddeler
- Tebliğ: "TEBLİĞ" başlığı, usul ve esaslar

ADIM 3 — BAĞLAM AYIRT EDİCİLERİ:
- Dilekçe HER ZAMAN bir kişinin (vatandaş, memur, öğrenci vb.) kuruma yaptığı BİREYSEL başvurudur. "Arz ederim" kalıbı tek başına yeterli değil — yazanın birey olması gerekir.
- Resmî yazı bir KURUMUN başka bir kuruma yazdığı resmi yazıdır.
- Bir evrakta başka mevzuata ATIF yapılması onu o tür yapmaz. Örneğin "4982 sayılı Kanun kapsamında" yazan bir dilekçe, kanun değil dilekçedir.
- Cumhurbaşkanlığı Kararnamesi ≠ Karar. Kararname düzenleyici (normatif) bir işlemdir, karar bireysel bir işlemdir.

GÜVENİLİRLİK (confidence) KURALLARI:
- Başlıkta evrak türü açıkça yazıyorsa: 0.85-0.95
- Yapısal unsurlardan güçlü eşleşme varsa: 0.70-0.85
- Birden fazla türe uyabilecek: 0.50-0.65
- Çok kısa, bozuk veya belirsiz metin: 0.25-0.45

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{{"document_type": "tur_kodu", "confidence": 0.0-1.0, "sub_type": "alt_tur_veya_null", "reasoning": "kısa sınıflandırma gerekçesi"}}"""


class ClassifierAgent(LLMAgent):
    """Evrak türü sınıflandırma agentı."""

    name = "ClassifierAgent"
    system_prompt = _build_prompt()
    max_input_chars = 5000

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
