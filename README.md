# Kamu Evrak Analizi Sistemi

Kamu kurumlarına gelen evrakların yapay zekâ ile otomatik sınıflandırılması, içerik analizi, mevzuat eşleştirmesi, resmî yazı taslağı oluşturulması ve ilgili birime yönlendirilmesi işlemlerini gerçekleştiren çok ajanlı bir sistemdir.

## Özellikler

- **Evrak Sınıflandırma**: 18 farklı evrak türü (dilekçe, resmî yazı, kanun, yönetmelik, kararname vb.)
- **İçerik Analizi**: Varlık çıkarma (tarih, kurum, kişi, referans no), eksik alan tespiti, anahtar kelime belirleme
- **RAG Destekli Mevzuat Eşleştirme**: TF-IDF tabanlı retrieval ile 956 belgeden 3056 parça üzerinde arama (scikit-learn)
- **PII/KVKK Tespiti**: TC Kimlik (sağlama doğrulamalı), IBAN, telefon, e-posta tespiti ve maskeleme; taslağa kişisel veri sızıntısı kontrolü
- **Human-in-the-Loop**: Taslak (Onayla / Düzenle / Reddet) ve yönlendirme (Onayla / Birimi değiştir) kararları sunucuda kalıcı olarak saklanır
- **Resmî Yazı Taslağı**: Evrak türüne uygun cevap/işlem yazısı; yazdırma ve .txt indirme
- **Birim Yönlendirme**: 8 kamu birimi arasında otomatik yönlendirme ve önceliklendirme
- **Kural Tabanlı Doğrulama**: LLM çıktılarını deterministik kurallarla denetleyen ReasoningAgent (6 kural)
- **Gerçek Zamanlı İlerleme**: Analizler arka plan işi olarak çalışır; arayüz her adımın durumunu canlı gösterir
- **Hata Toleransı**: Bir adım başarısız olursa analiz "kısmi" olarak tamamlanır, hangi adımın neden düştüğü raporlanır
- **OCR Desteği**: PDF ve görüntü dosyalarından Tesseract ile metin çıkarma
- **Analiz Geçmişi**: Arama, türe göre filtreleme, istatistik paneli, JSON dışa aktarma
- **Toplu İşleme ve Karşılaştırma**: Batch analiz API'si, iki evrak arasında benzerlik/fark analizi
- **Çevrimdışı Çalışan Arayüz**: CDN bağımlılığı yok; kurum içi / internetsiz ağlarda da çalışır. Açık/koyu tema, mobil uyumlu, klavye ve ekran okuyucu erişilebilirliği
- **Prompt Injection Koruması**: Evrak metni etiketler arasına alınır
- **LLM Yanıt Önbelleği**: SHA-256 hash tabanlı önbellek
- **Rate Limiting**: IP tabanlı istek sınırlama
- **Request ID İzleme**: Her API yanıtında X-Request-ID
- **Docker Desteği**: Tek komutla production dağıtımı

## Mimari

```
                 ┌────────────────────── app/api/routes ──────────────────────┐
  Tarayıcı ───▶  │ analysis · jobs · history · system   (FastAPI router'ları) │
                 └───────────────┬────────────────────────────────────────────┘
                                 ▼
                     ServiceContainer (app/container.py)
          ┌──────────────┬───────┴───────┬───────────────┬──────────────┐
   AnalysisService   JobManager   HistoryRepository  UploadStorage   LLMService / RAGService / OCRService
          │
          ▼
   OrchestratorAgent ── her çalıştırma için yeni örnek, PipelineObserver ile ilerleme bildirir
```

**Agent hiyerarşisi**

```
BaseAgent (soyut)
├── OCRAgent              → Metin çıkarma (OCRService: PdfExtractor / ImageExtractor / PlainTextExtractor)
├── ReasoningAgent        → ValidationRule zinciri (deterministik, LLM yok)
├── OrchestratorAgent     → Pipeline koordinasyonu
└── LLMAgent (soyut)      → system prompt + ask_json/ask_text + toleranslı ayrıştırma
    ├── ClassifierAgent   ├── AnalyzerAgent   ├── LegislationAgent (RAG)
    ├── SummaryAgent      ├── DraftAgent      ├── RoutingAgent
    └── ComparisonAgent
```

**Pipeline** (aynı satırdakiler paralel çalışır):

```
Metin çıkarma → Sınıflandırma ‖ İçerik analizi → Mevzuat ‖ Özet → Taslak ‖ Yönlendirme → Muhakeme ve doğrulama
```

**Tek kaynak sözlük**: Evrak türleri, birimler, taslak türleri ve öncelikler `app/core/taxonomy.py` içinde tanımlıdır. LLM prompt'ları, doğrulama kuralları ve arayüz etiketleri (`/api/meta`) buradan üretilir; yeni bir evrak türü eklemek için tek bir kayıt yeterlidir.

## Kurulum

### Gereksinimler

- Python 3.11+
- Tesseract OCR (`tesseract` komutunun PATH'te olması ve `tur` dil paketi)
- Gemini API anahtarı (veya OpenAI uyumlu herhangi bir LLM uç noktası)

### Adımlar

```bash
git clone https://github.com/<kullanici>/kamu_evrak_analizi.git
cd kamu_evrak_analizi

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env      # LLM_API_KEY değerini kendi anahtarınızla değiştirin

python -m app.main        # veya: uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Tarayıcıda `http://127.0.0.1:8080` adresini açın. Tüm ayarlar `.env.example` dosyasında açıklamalı olarak listelenmiştir.

## Kullanım

1. **Analiz** sayfasında dosya yükleyin (PDF, PNG, JPG, TIFF, BMP, TXT, MD) veya metni yapıştırın — denemek için "Örnek evrak" düğmesini kullanabilirsiniz
2. "Analiz et" deyin (metin kutusunda `Ctrl + Enter`); adımların ilerleyişi canlı gösterilir
3. Sonuç sekmeleri:
   - **Genel Bakış**: Özet, sınıflandırma gerekçesi, dikkat gerektiren noktalar
   - **İçerik**: Çıkarılan bilgiler ve eksik alanlar
   - **Mevzuat**: İlişkili mevzuat ve ilgi skorları
   - **Yazı Taslağı**: Resmî yazı önizlemesi; onayla / düzenle / reddet, kopyala, indir, yazdır
   - **Yönlendirme**: Hedef birim, öncelik, beklenen eylemler; onayla veya birimi değiştir
   - **Doğrulama**: Genel güven skoru, KVKK bulguları, muhakeme ajanının düzeltmeleri
   - **İşlem Kaydı**: Adım süreleri ve agent kayıtları
4. **Geçmiş** sayfasında önceki analizleri arayın, açın veya silin; **Karşılaştır** ile iki evrakı kıyaslayın

## API

| Uç nokta | Yöntem | Açıklama |
|----------|--------|----------|
| `/api/jobs/text` | POST | Metin analizini arka planda başlatır → `{job_id}` |
| `/api/jobs/file` | POST | Dosya analizini arka planda başlatır (multipart) → `{job_id}` |
| `/api/jobs/{id}` | GET | İş durumu, adım ilerlemesi ve tamamlanınca sonuç |
| `/api/analyze` | POST | Dosya yükleyerek senkron analiz (multipart/form-data) |
| `/api/analyze-text` | POST | Metin göndererek senkron analiz (`{text, title?}`) |
| `/api/analyze-batch` | POST | Toplu dosya analizi (maks. 10) |
| `/api/compare` | POST | İki evrak metnini karşılaştırma (`{text1, text2}`) |
| `/api/history` | GET | Geçmiş listesi (`q`, `document_type`, `limit`, `offset`) |
| `/api/history/stats` | GET | İstatistikler |
| `/api/history/{id}` | GET / DELETE | Kaydı getir / sil |
| `/api/history/{id}/review` | PATCH | Memur kararını kaydet (taslak ve yönlendirme) |
| `/api/export/{id}` | GET | Analiz sonucunu JSON olarak indir |
| `/api/mask-pii` | POST | Metindeki kişisel verileri maskele |
| `/api/meta` | GET | Arayüz sözlüğü ve girdi sınırları |
| `/api/health` | GET | Sağlık kontrolü (LLM yapılandırması, RAG durumu) |

Hatalar her zaman `{"detail": "<Türkçe mesaj>", "code": "<makine kodu>"}` biçimindedir (ör. `llm_unavailable`, `unsupported_file_type`, `text_extraction_failed`). Etkileşimli dokümantasyon: `http://127.0.0.1:8080/docs`

## Proje Yapısı

```
kamu_evrak_analizi/
├── app/
│   ├── main.py                 # create_app() fabrikası, güvenlik başlıkları, statik dosyalar
│   ├── config.py               # Ayarlar (pydantic-settings)
│   ├── container.py            # Servislerin kurulduğu bağımlılık container'ı
│   ├── core/
│   │   ├── taxonomy.py         # Evrak türleri, birimler, öncelikler (tek kaynak)
│   │   ├── exceptions.py       # AppError hiyerarşisi
│   │   └── logging.py
│   ├── agents/                 # BaseAgent / LLMAgent ve tüm ajanlar
│   │   ├── orchestrator.py     # Paralel aşamalı pipeline
│   │   ├── reasoning_agent.py
│   │   └── validation_rules.py # ValidationRule alt sınıfları
│   ├── services/               # LLM, OCR, RAG, PII, geçmiş, upload, iş yöneticisi, analiz servisi
│   ├── models/                 # Pydantic modelleri (alan + API şemaları)
│   ├── api/                    # Router'lar, bağımlılıklar, hata işleyicileri
│   └── data/                   # Mevzuat metadata ve şablonlar
├── frontend/
│   ├── index.html
│   └── assets/
│       ├── css/app.css         # Tasarım sistemi (açık/koyu tema)
│       └── js/                 # ES modülleri: core/ (api, dom, ui, vocabulary, icons) + views/
├── scripts/                    # scraper.py, build_index.py, evaluate_f1.py
├── tests/                      # pytest — sahte LLM ile uçtan uca testler
├── requirements.txt / requirements-dev.txt
└── .env.example
```

## Testler

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Testler gerçek LLM'e istek atmaz; `tests/conftest.py` içindeki sahte LLM ile pipeline, API, hata senaryoları (LLM erişilemez, kısmi başarısızlık), dosya doğrulama, path traversal koruması, memur kararları ve iş ilerlemesi doğrulanır.

## Güvenlik ve KVKK

- Yüklenen dosyalar rastgele adla saklanır ve varsayılan olarak analizden sonra silinir (`KEEP_UPLOADS`)
- Kayıt kimlikleri doğrulanır; dizin dışına erişim (path traversal) engellenir
- LLM çıktısı arayüzde hiçbir zaman HTML olarak yorumlanmaz (XSS koruması)
- CORS varsayılan olarak kapalıdır; gerekiyorsa `CORS_ORIGINS` ile açıkça izin verilir
- Yanıtlara `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` başlıkları eklenir

## Veri Toplama (Opsiyonel)

```bash
pip install playwright
playwright install chromium
python scripts/scraper.py        # app/data/scraped/documents.json
python scripts/build_index.py    # app/data/rag/ (RAG indeksi)
```

## Teknolojiler

- **Backend**: FastAPI, Pydantic v2, httpx
- **Frontend**: Bağımlılıksız vanilla JS (ES modülleri), özel CSS tasarım sistemi
- **LLM**: Gemini API (OpenAI uyumlu uç nokta, retry ve Retry-After desteği)
- **RAG**: scikit-learn TF-IDF, kosinüs benzerliği
- **OCR**: Tesseract, PyMuPDF, Pillow
- **Scraping**: Playwright (Chromium)

## Lisans

Bu proje eğitim ve araştırma amaçlıdır.
