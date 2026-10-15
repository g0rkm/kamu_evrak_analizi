# PROJE PLANI: Kamu Evrak ve Yazışma Süreçleri İçin Akıllı Agent Destek Sistemi

## 1. PROJE ÖZETİ
TEKNOFEST Yapay Zeka Dil Ajanları Yarışması kapsamında, kamu kurumlarına gelen evrakların
otomatik sınıflandırılması, içerik analizi yapılması, resmî yazı taslağı oluşturulması ve
ilgili birime yönlendirilmesi işlemlerini gerçekleştiren çok ajanlı bir yapay zeka sistemi.

## 2. TEKNİK MİMARİ

### 2.1 Genel Mimari
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Vanilla HTML/CSS/JS (Tailwind CSS)
- **LLM Backend**: OpenAI-uyumlu API (yerel proxy veya herhangi bir LLM)
- **OCR**: Tesseract + PyMuPDF
- **Mimari Desen**: Multi-Agent Orchestration (Orkestratör deseni)

### 2.2 Agent Mimarisi (OOP)
```
BaseAgent (Soyut Temel Sınıf)
├── OCRAgent          → Evrak okuma ve metin çıkarma
├── ClassifierAgent   → Evrak türü sınıflandırma
├── AnalyzerAgent     → İçerik analizi ve bilgi çıkarma
├── LegislationAgent  → Mevzuat eşleştirme
├── SummaryAgent      → Özet oluşturma
├── DraftAgent        → Resmî yazı taslağı üretme
├── RoutingAgent      → Birim yönlendirme
└── OrchestratorAgent → Tüm agentları koordine etme
```

### 2.3 Veri Modelleri (Pydantic)
- **Document**: Yüklenen evrakın ham verisi (dosya adı, metin, metadata)
- **ClassificationResult**: Evrak türü, güven skoru
- **AnalysisResult**: Çıkarılan bilgiler, eksik alanlar, anahtar kelimeler
- **LegislationMatch**: Eşleşen mevzuat listesi
- **DocumentSummary**: Özet metni
- **DraftResponse**: Yazı taslağı, yazı türü, üslup bilgisi
- **RoutingDecision**: Hedef birim, gerekçe, öncelik seviyesi
- **PipelineResult**: Tüm agent çıktılarını birleştiren uçtan uca sonuç

## 3. KLASÖR YAPISI
```
kamu_evrak_analizi/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI uygulama giriş noktası
│   ├── config.py                   # Yapılandırma (LLM endpoint, model adı vb.)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── document.py             # Document, UploadedFile modelleri
│   │   ├── analysis.py             # Analiz sonuç modelleri
│   │   └── draft.py                # Taslak ve yönlendirme modelleri
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py           # BaseAgent soyut sınıfı
│   │   ├── ocr_agent.py            # OCR / metin çıkarma
│   │   ├── classifier_agent.py     # Evrak sınıflandırma
│   │   ├── analyzer_agent.py       # İçerik analizi
│   │   ├── legislation_agent.py    # Mevzuat eşleştirme
│   │   ├── summary_agent.py        # Özet üretme
│   │   ├── draft_agent.py          # Yazı taslağı oluşturma
│   │   ├── routing_agent.py        # Birim yönlendirme
│   │   └── orchestrator.py         # Orkestratör agent
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_service.py          # LLM API iletişim servisi
│   │   └── ocr_service.py          # OCR işleme servisi
│   ├── data/
│   │   ├── legislation.json        # Örnek mevzuat veritabanı
│   │   ├── templates.json          # Resmî yazı şablonları
│   │   └── sample_documents/       # Test evrakları
│   └── api/
│       ├── __init__.py
│       └── routes.py               # API endpoint tanımları
├── frontend/
│   ├── index.html                  # Ana arayüz
│   ├── style.css                   # Stiller
│   └── app.js                      # Frontend mantığı
├── requirements.txt
└── README.md
```

## 4. AİDER ÇAĞRI PLANI (Maksimum Verimlilik — ~7 çağrı)

### Çağrı 1: Temel Modeller + Config + Base Agent
Dosyalar: config.py, models/document.py, models/analysis.py, models/draft.py, agents/base_agent.py
İçerik: Tüm Pydantic modelleri, yapılandırma sınıfı, BaseAgent ABC

### Çağrı 2: Servisler (LLM + OCR)
Dosyalar: services/llm_service.py, services/ocr_service.py
İçerik: OpenAI-uyumlu LLM client, Tesseract/PyMuPDF OCR wrapper

### Çağrı 3: Görev 1 Agentları (Evrak Analizi)
Dosyalar: agents/ocr_agent.py, agents/classifier_agent.py, agents/analyzer_agent.py, agents/legislation_agent.py, agents/summary_agent.py
İçerik: OCR, sınıflandırma, içerik analizi, mevzuat eşleştirme, özetleme

### Çağrı 4: Görev 2 Agentları + Orkestratör
Dosyalar: agents/draft_agent.py, agents/routing_agent.py, agents/orchestrator.py
İçerik: Yazı taslağı, birim yönlendirme, uçtan uca orkestrasyon

### Çağrı 5: API + Main + Örnek Veri
Dosyalar: api/routes.py, main.py, data/legislation.json, data/templates.json
İçerik: REST API endpointleri, FastAPI app, mevzuat ve şablon verileri

### Çağrı 6: Frontend
Dosyalar: frontend/index.html, frontend/style.css, frontend/app.js
İçerik: Evrak yükleme, analiz sonuç gösterimi, taslak düzenleme arayüzü

### Çağrı 7: Entegrasyon + Test + Requirements
Dosyalar: requirements.txt, düzeltmeler
İçerik: Bağımlılıklar, uçtan uca test, hata düzeltme

## 5. GÖREV DETAYLARI

### Görev 1: Evrak Sınıflandırma ve İçerik Analizi
| Yetenek | Sorumlu Agent |
|---------|---------------|
| Evrakı OCR veya metin olarak okuma | OCRAgent |
| Evrak türünü belirleme | ClassifierAgent |
| Önemli bilgi unsurlarını çıkarma | AnalyzerAgent |
| Eksik bilgileri tespit etme | AnalyzerAgent |
| Mevzuat/yönetmelik önerme | LegislationAgent |
| Kısa özet oluşturma | SummaryAgent |

### Görev 2: Resmî Yazı Taslaklama ve Birim Yönlendirme
| Yetenek | Sorumlu Agent |
|---------|---------------|
| Uygun yazı taslağı oluşturma | DraftAgent |
| Resmî üslup sağlama | DraftAgent |
| Doğru birime yönlendirme | RoutingAgent |
| Süreç bilgilendirmesi | OrchestratorAgent |
| Eksik bilgi talep etme | AnalyzerAgent + DraftAgent |

## 6. EVRAK TÜRLERİ (Sınıflandırma Kategorileri)
- Dilekçe
- Resmi yazı (üst yazı)
- Talep yazısı
- Bilgilendirme yazısı
- Görüş sorma yazısı
- Şikayet dilekçesi
- Kurum içi yazışma
- Genelge / Duyuru
- Rapor
- Tutanak

## 7. KAMU BİRİMLERİ (Yönlendirme Hedefleri)
- Hukuk Müşavirliği
- İnsan Kaynakları Daire Başkanlığı
- Strateji Geliştirme Daire Başkanlığı
- Bilgi Teknolojileri Daire Başkanlığı
- İdari ve Mali İşler Daire Başkanlığı
- Basın ve Halkla İlişkiler Müdürlüğü
- Teftiş Kurulu Başkanlığı
- İlgili Genel Müdürlük (içeriğe göre)
