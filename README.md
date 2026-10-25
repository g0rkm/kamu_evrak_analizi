# Kamu Evrak Analizi Sistemi

Kamu kurumlarına gelen evrakların **%100 yerel yapay zekâ (Local LLM — Gemma 4 12B)** ile otomatik sınıflandırılması, içerik analizi, mevzuat eşleştirmesi, resmî yazı taslağı oluşturulması ve ilgili birime yönlendirilmesi işlemlerini gerçekleştiren çok ajanlı (multi-agent) bir sistemdir.

## Özellikler

- **%100 Yerel Yapay Zekâ (Local LLM — Gemma 4 12B)**: Ollama (`gemma4:12b`) üzerinde tamamen kurum içi / çevrimdışı çalışır; hiçbir evrak verisi bulut API'lerine gönderilmez
- **Evrak Sınıflandırma**: 18 farklı evrak türü (dilekçe, resmî yazı, kanun, yönetmelik, kararname, tebliğ, genelge vb. — **Macro F1: 0.935**)
- **İçerik Analizi**: Varlık çıkarma (tarih, kurum, kişi, referans no), eksik alan tespiti, anahtar kelime belirleme
- **RAG Destekli Mevzuat Eşleştirme**: TF-IDF tabanlı retrieval ile 956 belgeden 3056 parça üzerinde yerel arama (scikit-learn)
- **PII/KVKK Tespiti**: TC Kimlik (sağlama doğrulamalı), IBAN, telefon, e-posta tespiti ve maskeleme; taslağa kişisel veri sızıntısı kontrolü
- **Human-in-the-Loop**: Taslak (Onayla / Düzenle / Reddet) ve yönlendirme (Onayla / Birimi değiştir) kararları sunucuda kalıcı olarak saklanır
- **Resmî Yazı Taslağı**: Evrak türüne uygun cevap/işlem yazısı; yazdırma ve `.txt` indirme
- **Birim Yönlendirme**: 8 kamu birimi arasında otomatik yönlendirme ve önceliklendirme
- **Kural Tabanlı Doğrulama**: LLM çıktılarını deterministik kurallarla denetleyen `ReasoningAgent` (6 kural)
- **Gerçek Zamanlı İlerleme**: Analizler arka plan işi olarak çalışır; arayüz her adımın durumunu canlı gösterir
- **Hata Toleransı**: Bir adım başarısız olursa analiz "kısmi" olarak tamamlanır, hangi adımın neden düştüğü raporlanır
- **OCR Desteği**: PDF ve görüntü dosyalarından PyMuPDF ve Tesseract (`tur`) ile yerel metin çıkarma
- **Analiz Geçmişi**: Arama, türe göre filtreleme, istatistik paneli, JSON dışa aktarma/içe aktarma
- **Toplu İşleme ve Karşılaştırma**: Batch analiz API'si, iki evrak arasında benzerlik/fark analizi
- **Çevrimdışı Çalışan Arayüz**: CDN bağımlılığı yok; kurum içi / internetsiz ağlarda da çalışır. Açık/koyu tema, mobil uyumlu, klavye ve ekran okuyucu erişilebilirliği
- **Prompt Injection Koruması**: Evrak metni `<evrak>` etiketleri arasına alınır ve iç etiketler etkisizleştirilir
- **LLM Yanıt Önbelleği ve GPU Kuyruk Koruması**: SHA-256 hash tabanlı önbellek, yerel GPU için eşzamanlı istek semaforu (`LLM_MAX_CONCURRENT_REQUESTS`), JSON modu (`response_format`) ve otomatik düşünme bloğu (`strip_thinking`) temizliği
- **Rate Limiting & Request ID İzleme**: IP tabanlı istek sınırlama ve her API yanıtında `X-Request-ID`
- **Docker Desteği**: Tek komutla production dağıtımı (`host.docker.internal` üzerinden ana makinedeki Ollama'ya bağlanabilir)

## Mimari

```
                 ┌────────────────────── app/api/routes ──────────────────────┐
  Tarayıcı ───▶  │ analysis · jobs · history · system   (FastAPI router'ları) │
                 └───────────────┬────────────────────────────────────────────┘
                                 ▼
                     ServiceContainer (app/container.py)
          ┌──────────────┬───────┴───────┬───────────────┬──────────────┐
   AnalysisService   JobManager   HistoryRepository  UploadStorage   LLMService (gemma4:12b) / RAGService / OCRService
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
└── LLMAgent (soyut)      → system prompt + ask_json/ask_text + Gemma 4 / Ollama yerel LLM entegrasyonu
    ├── ClassifierAgent   ├── AnalyzerAgent   ├── LegislationAgent (RAG)
    ├── SummaryAgent      ├── DraftAgent      ├── RoutingAgent
    └── ComparisonAgent
```

**Pipeline** (aynı satırdakiler paralel çalışır):

```
Metin çıkarma → Sınıflandırma ‖ İçerik analizi → Mevzuat ‖ Özet → Taslak ‖ Yönlendirme → Muhakeme ve doğrulama
```

**Tek kaynak sözlük**: Evrak türleri, birimler, taslak türleri ve öncelikler `app/core/taxonomy.py` içinde tanımlıdır. LLM prompt'ları, doğrulama kuralları ve arayüz etiketleri (`/api/meta`) buradan üretilir; yeni bir evrak türü eklemek için tek bir kayıt yeterlidir.

## Performans ve Sınıflandırma Başarımı (F1 Benchmark)

### 1. Sınıflandırma Doğruluğu (`gemma4:12b`)

Resmî Gazete ve Mevzuat Bilgi Sistemi'nden toplanan gerçek kamu evrakları üzerinde (`scripts/evaluate_f1.py`, `seed=42`, 54 belge, 6 ana mevzuat/evrak kategorisi) yerel **`gemma4:12b` (Q4_K_M)** modeliyle yapılan değerlendirme sonuçları:

| Evrak Türü | Precision (Kesinlik) | Recall (Duyarlılık) | F1 Skoru | Doğru / Toplam (TP / Destek) |
|------------|---------------------:|--------------------:|---------:|-----------------------------:|
| **Genelge** (`genelge`) | 1.000 | 1.000 | **1.000** | 6 / 6 |
| **Tebliğ** (`teblig`) | 1.000 | 1.000 | **1.000** | 10 / 10 |
| **Yönetmelik** (`yonetmelik`) | 1.000 | 1.000 | **1.000** | 10 / 10 |
| **Kanun** (`kanun`) | 0.900 | 0.900 | **0.900** | 9 / 10 |
| **Karar** (`karar`) | 1.000 | 0.800 | **0.889** | 8 / 10 |
| **Kararname** (`kararname`) | 0.778 | 0.875 | **0.824** | 7 / 8 |
| **Macro Ortalama (Macro F1)** | **0.946** | **0.929** | **0.935** | **50 / 54** |
| **Genel Doğruluk (Micro F1 / Accuracy)** | **0.926** | **0.926** | **0.926** | **%92.6** |

F1 ölçümünü tekrar çalıştırmak için:

```bash
python scripts/evaluate_f1.py
```

### 2. Yerel Donanım Hız ve VRAM Performansı

**Test Sistemi:** NVIDIA GeForce RTX 5070 (12GB GDDR7 VRAM) · AMD Ryzen 7 7700X · 16GB DDR5 RAM · Ollama `v0.40.8` (`gemma4:12b`, `%100 GPU`, `reasoning_effort="none"`):

| Pipeline Aşaması | Çalışma Şekli | Süre (sn) |
|------------------|---------------:|----------:|
| **1. Metin Çıkarma (`OCRAgent`)** | Tekil | `0.00 sn` *(PDF/OCR için ~0.3–1.2 sn)* |
| **2. Sınıflandırma (`ClassifierAgent`) ‖ İçerik Analizi (`AnalyzerAgent`)** | Paralel (2 ajan) | `5.48 sn` *(4.36 sn / 5.48 sn)* |
| **3. Mevzuat Eşleştirme (`LegislationAgent` + RAG) ‖ Özet (`SummaryAgent`)** | Paralel (2 ajan) | `5.62 sn` *(5.62 sn / 1.32 sn)* |
| **4. Resmî Yazı Taslağı (`DraftAgent`) ‖ Birim Yönlendirme (`RoutingAgent`)** | Paralel (2 ajan) | `4.99 sn` *(4.99 sn / 1.79 sn)* |
| **5. Muhakeme ve Doğrulama (`ReasoningAgent`)** | Deterministik | `0.00 sn` |
| **Toplam Uçtan Uca Evrak Analizi (6 LLM Çağrısı)** | **Tam Pipeline** | **`16.10 sn`** |

- **VRAM Tüketimi**: ~10.2 GB / 12.2 GB (%100 GPU belleğinde, sistem RAM'ine taşma yok)
- **Tekil Sınıflandırma Hızı**: Evrak başına ortalama **~1.3 saniye**

## Kurulum

### Gereksinimler

- Python 3.11+
- Tesseract OCR (`tesseract` komutunun PATH'te olması ve `tur` dil paketi)
- [Ollama](https://ollama.com/) (`gemma4:12b` yerel modeli — 12GB VRAM'li GPU önerilir) veya OpenAI uyumlu herhangi bir LLM uç noktası

### Adımlar

```bash
git clone https://github.com/<kullanici>/kamu_evrak_analizi.git
cd kamu_evrak_analizi
git checkout Develop

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

ollama pull gemma4:12b    # Yerel Gemma 4 12B modelini indirin (~7.7 GB)
cp .env.example .env      # Varsayılan olarak yerel Ollama (gemma4:12b) yapılandırılmıştır

python -m app.main        # veya: uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Tarayıcıda `http://127.0.0.1:8080` adresini açın.

### Yerel LLM (`.env`) Ayarları

```env
LLM_API_BASE=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=gemma4:12b
LLM_NUM_CTX=16384
LLM_KEEP_ALIVE=30m
LLM_MAX_CONCURRENT_REQUESTS=2
```

Tüm ayarlar `.env.example` dosyasında açıklamalı olarak listelenmiştir.

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
| `/api/health/llm` | GET | Yerel/uzak LLM sunucusu canlı bağlantı kontrolü |

Hatalar her zaman `{"detail": "<Türkçe mesaj>", "code": "<makine kodu>"}` biçimindedir (ör. `llm_unavailable`, `unsupported_file_type`, `text_extraction_failed`). Etkileşimli dokümantasyon: `http://127.0.0.1:8080/docs`

## Proje Yapısı

```
kamu_evrak_analizi/
├── app/
│   ├── main.py                 # create_app() fabrikası, güvenlik başlıkları, statik dosyalar
│   ├── config.py               # Ayarlar (pydantic-settings, varsayılan: Ollama gemma4:12b)
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
├── tests/                      # pytest — sahte LLM ile uçtan uca testler (479 test)
├── requirements.txt / requirements-dev.txt
└── .env.example
```

## Testler

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Testler gerçek LLM'e istek atmaz; `tests/conftest.py` içindeki sahte LLM ile pipeline, API, hata senaryoları (LLM erişilemez, kısmi başarısızlık), dosya doğrulama, path traversal koruması, memur kararları, yerel LLM düşünme bloğu temizliği ve iş ilerlemesi doğrulanır.

## Güvenlik ve KVKK

- **Tam Veri Mahremiyeti**: Yerel LLM (`gemma4:12b`) kullanımı sayesinde evrak içerikleri kurum dışına çıkmaz
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
- **LLM**: Yerel LLM — Ollama `gemma4:12b` (OpenAI uyumlu `/v1/chat/completions`, 16K bağlam penceresi, `reasoning_effort="none"`, JSON mod ve düşünme bloğu temizleme desteği)
- **RAG**: scikit-learn TF-IDF, kosinüs benzerliği
- **OCR**: Tesseract (`tur`), PyMuPDF, Pillow
- **Scraping**: Playwright (Chromium)

## Lisans

Bu proje eğitim ve araştırma amaçlıdır.
