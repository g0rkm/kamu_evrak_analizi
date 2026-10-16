# Kamu Evrak Analizi Sistemi

Kamu kurumlarına gelen evrakların yapay zeka ile otomatik sınıflandırılması, içerik analizi, mevzuat eşleştirmesi, resmî yazı taslağı oluşturulması ve ilgili birime yönlendirilmesi işlemlerini gerçekleştiren çok ajanlı bir sistemdir.

## Özellikler

- **Evrak Sınıflandırma**: 18 farklı evrak türü (dilekçe, resmi yazı, kanun, yönetmelik, kararname vb.)
- **İçerik Analizi**: Varlık çıkarma (tarih, kurum, kişi, referans no), eksik alan tespiti, anahtar kelime belirleme
- **RAG Destekli Mevzuat Eşleştirme**: TF-IDF tabanlı retrieval sistemi ile 956 belgeden 3056 chunk üzerinde arama (scikit-learn)
- **PII/KVKK Tespiti**: TC Kimlik (Luhn checksum doğrulamalı), IBAN, telefon, e-posta otomatik tespiti ve maskeleme
- **Human-in-the-Loop**: Taslak yazı ve yönlendirme kararları için Onayla/Düzenle/Reddet mekanizması
- **Yazı Taslağı**: Evrak türüne uygun resmî cevap/işlem yazısı taslağı
- **Birim Yönlendirme**: 8 kamu birimi arasında otomatik yönlendirme ve önceliklendirme
- **Kural Tabanlı Doğrulama**: LLM çıktılarını deterministik kurallarla kontrol eden ReasoningAgent (6 kural)
- **OCR Desteği**: PDF ve görüntü dosyalarından Tesseract ile metin çıkarma
- **Analiz Geçmişi**: JSON tabanlı sonuç depolama, geçmiş listeleme ve istatistik paneli
- **Toplu İşleme**: Birden fazla evrak için batch analiz API'si
- **Evrak Karşılaştırma**: İki evrak arasındaki benzerlik ve fark analizi
- **Pipeline Süre Ölçümü**: Her agent adımı için detaylı zamanlama ve görselleştirme
- **LLM Retry Mekanizması**: Rate limit ve timeout durumlarında exponential backoff ile otomatik yeniden deneme
- **JSON Dışa Aktarma**: Analiz sonuçlarını JSON olarak indirme

## Mimari

```
BaseAgent (Soyut Temel Sınıf)
├── OCRAgent           → Metin çıkarma (PDF, görüntü, düz metin)
├── ClassifierAgent    → Evrak türü sınıflandırma (LLM)
├── AnalyzerAgent      → İçerik analizi ve bilgi çıkarma (LLM)
├── LegislationAgent   → Mevzuat eşleştirme (LLM)
├── SummaryAgent       → Özet oluşturma (LLM)
├── DraftAgent         → Resmî yazı taslağı üretme (LLM)
├── RoutingAgent       → Birim yönlendirme (LLM)
├── ReasoningAgent     → Kural tabanlı doğrulama (deterministik, LLM yok)
└── OrchestratorAgent  → 7 adımlı pipeline koordinasyonu
```

**Pipeline**: OCR → Sınıflandırma → İçerik Analizi → Mevzuat → Özet → Taslak + Yönlendirme → Doğrulama

## Kurulum

### Gereksinimler

- Python 3.11+
- Tesseract OCR (`tesseract` komutunun PATH'te olması gerekir)
- Gemini API anahtarı (veya OpenAI-uyumlu herhangi bir LLM endpoint)

### Adımlar

```bash
# Repoyu klonla
git clone https://github.com/<kullanici>/kamu_evrak_analizi.git
cd kamu_evrak_analizi

# Sanal ortam oluştur
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasında LLM_API_KEY değerini kendi API anahtarınla değiştir

# Sunucuyu başlat
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Tarayıcıda `http://127.0.0.1:8080` adresini aç.

## Kullanım

1. Sol panelden dosya yükle (PDF, PNG, JPG, TXT) veya metin gir
2. "Analiz Et" butonuna tıkla
3. Sağ paneldeki sekmelerden sonuçları incele:
   - **Sınıflandırma & Özet**: Evrak türü, güven skoru, gerekçe
   - **İçerik Analizi**: Çıkarılan varlıklar, eksik alanlar, anahtar kelimeler
   - **Mevzuat**: İlişkili mevzuat eşleşmeleri
   - **Yazı Taslağı**: Resmî cevap yazısı taslağı
   - **Yönlendirme**: Hedef birim, öncelik, eylem planı
   - **Doğrulama**: Genel güven skoru, kural tabanlı doğrulama sonuçları
   - **Agent Logları**: Pipeline işlem kayıtları

## API

| Endpoint | Yöntem | Açıklama |
|----------|--------|----------|
| `/api/analyze` | POST | Dosya yükleyerek analiz (multipart/form-data) |
| `/api/analyze-text` | POST | Metin göndererek analiz (JSON body) |
| `/api/analyze-batch` | POST | Toplu dosya analizi (multipart/form-data, maks. 10) |
| `/api/compare` | POST | İki evrak metni karşılaştırma (JSON body) |
| `/api/history` | GET | Analiz geçmişi listesi |
| `/api/history/stats` | GET | Analiz istatistikleri |
| `/api/history/{id}` | GET | Belirli bir analiz kaydı |
| `/api/export/{id}` | GET | Analiz sonucunu JSON olarak indir |
| `/api/health` | GET | Sistem sağlık kontrolü (RAG durumu, istatistikler) |

API dokümantasyonu: `http://127.0.0.1:8080/docs`

## Proje Yapısı

```
kamu_evrak_analizi/
├── app/
│   ├── main.py                  # FastAPI uygulama giriş noktası
│   ├── config.py                # Yapılandırma (pydantic-settings)
│   ├── agents/                  # 9 ajan modülü
│   ├── models/                  # Pydantic veri modelleri
│   ├── services/                # LLM, OCR, RAG ve geçmiş servisleri
│   ├── api/                     # REST API route'ları
│   └── data/                    # Mevzuat DB ve şablonlar
├── frontend/                    # HTML/CSS/JS arayüz
├── scripts/
│   ├── scraper.py               # Resmi Gazete ve mevzuat scraper
│   ├── build_index.py           # RAG TF-IDF indeks oluşturma
│   └── evaluate_f1.py           # Sınıflandırma F1 değerlendirme
├── requirements.txt
├── .env.example
└── README.md
```

## Veri Toplama (Opsiyonel)

Resmi Gazete ve mevzuat.gov.tr'den veri toplamak için:

```bash
pip install playwright
playwright install chromium
python scripts/scraper.py
```

Scraper çıktısı `app/data/scraped/documents.json` dosyasına kaydedilir (gitignore'da, repo boyutunu şişirmemek için).

## Teknolojiler

- **Backend**: FastAPI, Pydantic, httpx
- **Frontend**: Vanilla JS, Tailwind CSS, Font Awesome
- **LLM**: Gemini API (OpenAI-uyumlu endpoint, retry mekanizmalı)
- **RAG**: scikit-learn TF-IDF, cosine similarity
- **OCR**: Tesseract, PyMuPDF, Pillow
- **Scraping**: Playwright (Chromium)

## Lisans

Bu proje eğitim ve araştırma amaçlıdır.
