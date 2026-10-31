# Rakip Sistem Analizi ve Kapsamlı Uygulama Planı

**Tarih:** 31 Ekim 2026  
**Analiz Edilen Sistemler:** KACHOW Teknofest-2026, KADIM (teknofest-kadim-kamu-evrak-ajani)  
**Hedef:** Bu sistemlerin en iyi özelliklerini alarak KACHOW seviyesinde veya üzerinde bir sistem oluşturmak

---

## 1. Mevcut Sistemimiz

- **8 Ajan:** OCR, Classifier, Analyzer, Legislation, Summary, Draft, Routing, Reasoning
- **30+ Servis:** LLM, RAG, OCR, History, Upload, Cache, Metrics, Export, EventBus vb.
- **Pipeline:** 8 adımlı paralel orchestrator (metin çıkarma → sınıflandırma ‖ analiz → mevzuat ‖ özet → taslak ‖ yönlendirme → muhakeme)
- **LLM:** Gemma4:12b (Ollama — yerel, on-premise, dış API yok)
- **Frontend:** 15+ view (Vanilla JS)
- **Test:** 478 backend test
- **Güçlü yanımız:** Pipeline altyapısı KADIM'den ileri. Eksik olan: chatbot, HITL, doğrulama derinliği.

---

## 2. Genel Karşılaştırma

| Kriter | KACHOW | KADIM | Biz |
|--------|--------|-------|-----|
| Teknoloji | FastAPI+React+PostgreSQL+Redis+Qdrant+LangGraph | Gradio+vLLM+Python | FastAPI+VanillaJS+Dosya tabanlı |
| LLM | Ollama/Evren API, çoklu profil | Qwen 7B+LoRA ince ayar | Gemma4:12b Ollama |
| Ajan Mimarisi | LangGraph çok-ajan, 6+ alt-graf | 4 ardışık ajan | 8 adımlı orchestrator |
| Chatbot | ✅ Tam karar destek | ❌ Yok | ❌ Yok |
| Taslak Oluşturma | ✅ Briefi→Taslak→Doğrulama→Revizyon | ✅ Yazıcı ajan+post-processing | ⚠️ Temel DraftAgent var |
| HITL | ✅ Checkpoint'li interrupt | ✅ Memur kararı akışın ortasında | ❌ Yok |
| Test | 2995 backend+447 frontend | Belirtilmemiş | 478 backend |
| Veri Seti | 1763 gerçek belge (HuggingFace) | 2444 sentetik belge | Küçük örnek set → **KACHOW veri seti entegre edilecek** |

---

## 3. KACHOW Başarı Anahtarları

1. **LangGraph çok-ajan orkestrasyon** — Her görev ayrı graf, checkpoint'li state machine
2. **Deterministik öncelik** — Intent scoring, alan çıkarımı, PII tespiti kural tabanlı; LLM sadece gerektiğinde
3. **Derin doğrulama zinciri** — yaz→doğrula→onar→LLM judge→insan onayı
4. **Kapsamlı test altyapısı** — 2995 backend + 447 frontend test
5. **İkili çalışma modu** — Kapalı ağ (Ollama) ve sunucu (Evren API)
6. **Kuruma özel adaptif öğrenme** — Geri bildirimden stil profili + LoRA/DPO
7. **Gözlemlenebilirlik** — Prometheus+Grafana+Langfuse+Jaeger
8. **42 ekran görüntüsü** — Profesyonel demo hazırlığı

## 4. KADIM Başarı Anahtarları

1. **Modüler görev ayrımı** — Her ajan tek iş, sorumluluklar açık
2. **Halüsinasyon direnci veriyle öğretildi** — Eğitim setinin %15'inde mevzuat listesi boş
3. **Deterministik birim yönlendirmesi** — 58 konu→11 müdürlük sabit eşleme
4. **Boilerplate madde cezalandırma** — RAG kalitesini artıran pratik teknik
5. **Tamamen kapalı devre** — Hiçbir dış API yok
6. **Post-processing pipeline** — Antet düzeltme, atıf ekleme, imza temizleme

---

## 5. ALINACAK TÜM ÖZELLİKLER — MADDE MADDE

### 5.1 Karar Destek Chatbot Sistemi [YENİ] [KRİTİK] [KACHOW]

En önemli eksik. KACHOW'un tüm sistemi sohbet arayüzü üzerinden çalışıyor.

**Eklenecek bileşenler:**
- `app/services/chat_service.py` — Sohbet oturumu yönetimi, mesaj geçmişi, bağlam penceresi
- `app/services/conversation_store.py` — Konuşma geçmişi kayıt (JSON dosya tabanlı)
- `app/agents/planning_orchestrator.py` — Sohbet mesajını intent'e göre doğru pipeline'a yönlendir
- `app/agents/assistant_agent.py` — Genel soru/yardım yanıtlama
- `app/agents/revision_agent.py` — Var olan taslağı düzenleme
- `app/api/routes/chat.py` — POST /api/chat/message (SSE), GET /api/chat/history, POST /api/chat/new
- `frontend/assets/js/views/chat-view.js` — Sohbet arayüzü

**Sohbet akışı:**
1. Kullanıcı mesaj yazar veya dosya yükler
2. Intent Router niyeti belirler
3. PlanningOrchestrator ilgili pipeline'ı tetikler
4. Her adım SSE ile canlı akış
5. HITL noktalarında InterruptPanel göster
6. Yanıt mesaj olarak sohbet penceresinde

### 5.2 Intent Router — Niyet Yönlendirici [YENİ] [KRİTİK] [KACHOW]

Tamamen deterministik, model çağrısı yok, milisaniyenin altında çalışıyor.

**6 Niyet:**
- `analyze` — "analiz et", "incele", dosya eki → Pipeline başlat
- `draft` — "taslak hazırla", "cevap yaz" → DraftAgent
- `assist` — "ne demek", "madde X ne diyor" → AssistantAgent
- `revise` — "değiştir", "düzelt", "kısalt" → RevisionAgent
- `clarify` — Belirsiz mesaj → Açıklama iste
- `refuse` — Kapsam dışı → Nazikçe reddet

**Puanlama mantığı:**
- Her niyet için kanıt kuralları (anahtar kelimeler, regex, bağlam sinyalleri)
- Karar en yüksek iki intent arasındaki MARJ ile verilir
- Küçük marj (<0.15) → clarify
- Karşı-sinyal: "üst yazı ne demek?" → draft'a negatif, assist'e pozitif

**Dosya:** `app/services/intent_router.py`

### 5.3 İnsan-Döngüde (HITL) Mekanizması [YENİ] [KRİTİK] [KACHOW+KADIM]

Model öneri üretir, memur onaylar. Karar modele bırakılmaz.

**HITL Noktaları:**
1. **Analiz Onayı** — Güven <0.70 → türü düzelt veya onayla
2. **Mevzuat Seçimi** — RAG sonuçlarından taslağa gidecek maddeleri seç (checkbox)
3. **Süreç Durumu** — İncelemede / Tamamlandı / Eksik bilgi / Reddedildi / Yönlendirildi
4. **Yazım Briefi** — "Kim yazıyor?", "Kime?" slot doldurma
5. **Taslak Onayı** — Onayla, düzenle veya yeniden yaz
6. **Gönderim Onayı** — Hedef birimi ve gönderimi onayla

**Dosyalar:** `app/services/interrupt_service.py`, `frontend/assets/js/components/interrupt-panel.js`

### 5.4 Regex Öncelikli Alan Çıkarımı [YENİ] [YÜKSEK] [KACHOW]

Etiketli alanları LLM'den önce regex ile çıkar — kesin sonuç:
- `Sayı:` → belge numarası
- `Tarih:` → tarih (DD.MM.YYYY)
- `Konu:` → konu başlığı
- `İlgi:` → ilgi referansı
- `T.C.` / kurum antetleri → gönderen kurum
- Yapısal işaretler (DAĞITIM YERLERİ, EKLER)

Regex sonuçları LLM çıktısıyla `merge_parsed_over_model()` ile birleştirilir.

**Dosya:** `app/services/field_extractor.py`

### 5.5 Yapısal Sinyal Tespiti [YENİ] [YÜKSEK] [KACHOW]

Belgedeki yapısal işaretleri tespit edip prompt'a olgu olarak enjekte et:
- "DAĞITIM YERLERİ" → resmî yazı sinyali
- "Arz ederim" + bireysel imza → dilekçe sinyali
- "BİRİNCİ BÖLÜM" + "Amaç, Kapsam" → yönetmelik sinyali
- "KARAR" + kurul bilgisi → karar sinyali

**Dosya:** `app/services/structural_detector.py`

### 5.6 İki Katmanlı Cascade [İYİLEŞTİRME] [YÜKSEK] [KACHOW]

Gemma4:12b'yi iki profilde kullan:
- **Hızlı profil:** Düşük temperature (0.1), kısa max_tokens
- **Kalite profil:** Normal temperature — zorunlu alan eksikse yükselt
- İki sonuç alan-seviyesinde birleştirilir

### 5.7 Deterministik Birim Yönlendirmesi [YENİ] [YÜKSEK] [KADIM]

JSON dosyasında konu→birim eşleme tablosu:
- ClassifierAgent'ın `primary_topic` alanıyla eşle
- Eşleşme varsa → deterministik (model gerekmez)
- Yoksa → mevcut RoutingAgent'a fallback

**Dosyalar:** `data/topic_unit_map.json`, `app/services/deterministic_router.py`

### 5.8 Düz (Flat) Pydantic Şema [İYİLEŞTİRME] [YÜKSEK] [KACHOW]

12B ve altı modeller iç içe JSON'da bozuk çıktı üretir:
- Tüm çıkarım alanlarını tek seviye düz şemaya koy
- Evrak türüne göre dinamik `create_model()` ile farklı zorunlu alan listesi

### 5.9 BM25 + Hibrit Arama [İYİLEŞTİRME] [YÜKSEK] [KADIM]

Mevcut RAG sadece TF-IDF. Eklenecek:
- BM25 sözcük tabanlı arama (kanun adı, madde numarası birebir eşleşme)
- Türkçe morfoloji özel gövdeleme (ilk 6 karakter, sayılar hariç)
- RRF (Reciprocal Rank Fusion) birleştirme

**Dosyalar:** `app/services/bm25_service.py`, `app/services/hybrid_retriever.py`

### 5.10 Boilerplate Madde Cezalandırma [YENİ] [YÜKSEK] [KADIM]

Amaç/Kapsam/Tanımlar/Dayanak maddelerinin skoru %88 düşürülür:
- `BOILERPLATE_FACTOR = 0.12`
- Sadece kavramsal sorgularda; doğrudan atıf sorgularında uygulanmaz

### 5.11 Kapsam Dışı Sorgu Filtreleme [YENİ] [YÜKSEK] [KADIM]

Mevzuattan cevaplanamayacak sorguları otomatik reddet:
- Telefon numarası, web adresi, güncel tarife/fiyat, yerel etkinlik, kişisel bilgi

**Dosya:** `app/services/query_scope_filter.py`

### 5.12 Madde Başlığı Boost + Belge Başı Kota [YENİ] [YÜKSEK] [KADIM]

- `TITLE_BOOST_PER_HIT = 0.10` — sorgu-başlık örtüşmesi
- Her kanundan maks N madde — çeşitlilik sağla

### 5.13 Deterministik Sorgu Oluşturma [İYİLEŞTİRME] [YÜKSEK] [KACHOW]

Model yeniden yazımı YAPMA:
- Türkçe stopword çıkar
- Domain genişletme terimleri ekle
- Tür-özgü mevzuat kelime dağarcığı

### 5.14 Yazım Briefi [YENİ] [YÜKSEK] [KACHOW]

Taslak öncesi yapılandırılmış soru-cevap:
- "Kim yazıyor?" — antet ve imza
- "Kime gidiyor?" — muhatap
- "Süreç durumu?" — tamamlandı/incelemede/reddedildi/yönlendirildi/eksik
- "Seçilen mevzuat?" — RAG sonuçlarından

**Dosya:** `app/services/writing_brief.py`

### 5.15 Post-Processing Pipeline [YENİ] [YÜKSEK] [KADIM]

- `polish_official_letter()` — yanlış antet/hitap düzeltme
- `strip_citizen_signature()` — vatandaş imza bloğu kesme
- `strip_trailing_attachments()` — sahte Ek listesi temizleme
- `ensure_legislation_in_draft()` — eksik mevzuat atfı ekleme
- `fix_duplicate_closings()` — çift kapanış temizleme

**Dosya:** `app/services/draft_postprocessor.py`

### 5.16 Yanıt Türü Genişletme [İYİLEŞTİRME] [YÜKSEK] [KADIM]

7 yanıt türü: BİLGİ_YAZISI, BİLDİRİM_YAZISI, EKSİK_BİLGİ_TAMAMLAMA_YAZISI, RET_YAZISI, YÖNLENDİRME_YAZISI, TESPİT_TUTANAĞI, ONAY_YAZISI

### 5.17 Taslak Doğrulama Pipeline'ı [YENİ] [YÜKSEK] [KACHOW]

**Katman 1 — Deterministik:**
- `check_groundedness` — kaynak evrakla tutarlılık
- `check_filler_sentences` — dolgu cümlesi tespiti
- `check_meta_commentary` — meta-yorum kontrolü
- `check_person_consistency` — kişi tutarlılığı
- `check_signature_block` — imza bloğu kontrolü
- `check_legislation_citations` — halüsinasyon tespiti
- `check_identity_leakage` — kimlik sızıntısı

**Katman 2 — LLM Judge (opsiyonel):**
- Stil, arz/rica yönü, muhatap tutarlılığı kontrolü

**Sınırlı Onarım Döngüsü:**
- Maks 2 deneme, "en iyi deneme kazanır"

**Dosyalar:** `app/services/draft_verifier.py`, `app/services/draft_judge.py`

### 5.18 Girdi/Çıktı Guardrail'leri [YENİ] [YÜKSEK] [KACHOW]

**Girdi:**
- Prompt injection temizliği (regex)
- Görünmez karakter çıkarımı
- PII tespiti (TCKN checksum, IBAN checksum, telefon, e-posta)

**Çıktı:**
- Prompt sızıntı kontrolü
- Kaynak dışı iddia kontrolü
- PII maskeleme

**Dosyalar:** `app/services/input_guardrail.py`, `app/services/output_guardrail.py`, `app/services/pii_detector.py`

### 5.19 SSE Canlı Akış [YENİ] [YÜKSEK] [KACHOW]

Event türleri: `step_start`, `step_end`, `partial`, `interrupt`, `guardrail`, `result`, `error`

Mevcut `PipelineObserver` SSE'ye bağlanabilir.

**Dosya:** `app/services/sse_broadcaster.py`

### 5.20 Frontend: Sohbet Arayüzü [YENİ] [YÜKSEK] [KACHOW]

- ChatView — mesaj baloncukları, zaman damgası
- ChatDropZone — sürükle-bırak evrak yükleme
- ThinkingBubble — düşünme animasyonu
- MarkdownMessage — Markdown yanıt gösterimi
- SourcePeekDrawer — kaynak evrak önizleme
- ConversationHistoryDrawer — konuşma geçmişi

### 5.21 Frontend: WorkflowStepper [YENİ] [YÜKSEK] [KACHOW]

Adım-adım ajan ilerlemesi göstergesi (SSE ile güncellenir):
- Her adım: bekliyor / çalışıyor / tamamlandı / hata
- Süre bilgisi

### 5.22 Frontend: InterruptPanel [YENİ] [YÜKSEK] [KACHOW]

- PromptQuestionCard — eksik bilgi soruları
- MevzuatSelectCard — mevzuat seçimi (checkbox)
- ProcessStatusCard — süreç durumu (radio)
- DraftReviewCard — taslak onay/düzenleme

### 5.23 Frontend: Geri Bildirim [YENİ] [ORTA] [KACHOW]

Her yanıtta beğen/beğenme butonları + açıklama alanı

### 5.24 Frontend: Ajan Masası [YENİ] [ORTA] [KADIM]

Üst barda ajan durum kartları: OCR | Sınıflandırma | Mevzuat | Taslak | Doğrulama

### 5.25 Frontend: Resmi Yazı Önizleme [YENİ] [ORTA] [KADIM]

Kağıt görünümünde taslak gösterimi (serif font, krem zemin)

### 5.26 Context Management [YENİ] [ORTA] [KACHOW]

- TokenBudget — her bileşene token kotası
- HistoryWindow — akıllı mesaj penceresi seçimi
- ContextUsageRing — frontend'de doluluk göstergesi
- MemorySummarizer — uzun konuşma özetleme

**Dosyalar:** `app/services/context_manager.py`, `app/services/memory_summarizer.py`

### 5.27 Kuruma Özel Adaptif Öğrenme [YENİ] [ORTA] [KACHOW]

- Geri bildirimlerden stil kuralları çıkar
- `style_rules` + `avoided_patterns`
- Taslak prompt'una enjekte et
- En az 20 geri bildirim gerekir

**Dosyalar:** `app/services/style_profiler.py`, `app/services/feedback_store.py`

### 5.28 Kurum İçi Mesajlaşma [YENİ] [ORTA] [KACHOW]

- Evrak paylaşımı, mesaj dizisi, transfer mekanizması, favoriler

**Dosyalar:** `app/services/messaging_service.py`, `app/api/routes/messaging.py`

### 5.29 Mevzuat Bilgi Grafı [YENİ] [ORTA] [KACHOW]

- Force-directed graf görselleştirme
- Bipartite layout (evraklar ↔ mevzuat)
- Pan/zoom + düğüm detay paneli
- Mevcut RAG verilerinden türetilir

**Dosyalar:** `frontend/assets/js/views/graph-view.js`, `app/api/routes/graph.py`

### 5.30 Evaluation Harness [YENİ] [ORTA] [KACHOW]

- Sınıflandırma benchmark (accuracy, F1)
- Taslak benchmark (atıf sadakati, dolgu oranı)
- RAG benchmark (Precision@K, Recall@K, MRR)
- Intent benchmark
- Latency benchmark

**Dosyalar:** `experiments/eval_harness.py`, `experiments/gold_sets/`

### 5.33 KACHOW HuggingFace Veri Seti Entegrasyonu [YENİ] [YÜKSEK] [KACHOW]

**Kaynak:** `https://huggingface.co/datasets/Ygthn/Teknofest_2026_KACHOW`  
**Yerel kopyası mevcut:** `C:\Users\user\Desktop\KACHOW-Teknofest-2026\datasets\`

KACHOW ekibi tarafından hazırlanan, Türkçe kamu yazışmaları alanında en kapsamlı açık veri seti. Sistemimize 4 farklı alanda doğrudan entegre edilebilir:

#### A) Sınıflandırma Eğitim/Değerlendirme Verisi (1763 etiketli belge)
- `datasets/resmi_yazisma/` altında 1763 gerçek/anonimleştirilmiş kamu yazışması
- Her belge YAML frontmatter ile etiketli: `kategori`, `alt_kategori`, `niyet`, `belge_turu`, `kurum`
- Kategoriler: bilgilendirme_metni, cevap_yazisi, dilekce, itiraz, gorüs_talebi, vb.
- **Kullanım:** Classifier Agent'ın doğruluk oranını ölçmek ve iyileştirmek için gold standard veri seti
- **Entegrasyon:** `experiments/gold_sets/classification_gold.jsonl` olarak dönüştürülecek

#### B) End-to-End Test Vakaları (26 altın standart vaka)
- `datasets/resmi_yazisma_vakalar/vakalar.jsonl` — 26 tam vaka
- Her vaka şunları içerir:
  - `incoming_document` — giriş evrak metni
  - `gold_draft` — beklenen cevap taslağı
  - `decision` — karar türü (ret, yetkisizlik, yalnizca_bilgilendirme, belirsiz_basvuru, coklu_talep)
  - `legal_basis` — yasal dayanak (kanun no, madde, doğrulama durumu)
  - `required_facts` — çıkarılması gereken olgular
  - `must_include` — taslakta bulunması GEREKEN ifadeler
  - `must_not_invent` — taslakta OLMAMASI gereken uydurma bilgiler (halüsinasyon kontrolü)
  - `evidence` — kaynak referansları
  - `anonymization` — anonimleştirme meta verisi
- **Kullanım:** Pipeline'ın uçtan uca doğruluğunu ölçme. Draft Agent'ın must_include/must_not_invent kısıtlarına uyumunu test etme
- **Entegrasyon:** `experiments/gold_sets/e2e_cases.jsonl` + Evaluation Harness'a E2E test modülü

#### C) Mevzuat Korpusu (7 temel kanun)
- `datasets/mevzuat/` altında 7 kanun/yönetmelik Markdown dosyası:
  - 657 sayılı Devlet Memurları Kanunu (551 KB)
  - 4982 sayılı Bilgi Edinme Hakkı Kanunu
  - 3071 sayılı Dilekçe Hakkı Kanunu
  - 5070 sayılı Elektronik İmza Kanunu
  - 6698 sayılı KVKK
  - Resmî Yazışma Yönetmeliği
  - 7201 sayılı Tebligat Kanunu
  - `sparse_vocab.json` — mevzuat arama vokabuleri
- **Kullanım:** RAG indeksini zenginleştirme. Mevcut RAG servisimizin TF-IDF indeksine bu kanunları eklemek
- **Entegrasyon:** `data/mevzuat/` klasörüne kopyalanacak, RAG startup'ında otomatik indekslenecek

#### D) Embedding Prototipleri (önceden hesaplanmış vektörler)
- `datasets/prototypes/correspondence_type.json` — Belge türü sınıflandırma prototipleri (nomic-embed-text, 768 boyut)
  - Etiketler: cover_letter, cevap_yazisi, bilgilendirme_metni vb.
- `datasets/prototypes/intent.json` — Niyet sınıflandırma prototipleri
  - Etiketler: analyze, itiraz, bilgi_edinme vb.
- **Kullanım:** Intent Router ve Classifier'da embedding benzerlikleri ile hızlı sınıflandırma (Ollama nomic-embed-text modeli ile uyumlu)
- **Entegrasyon:** `data/prototypes/` klasörüne kopyalanacak, Intent Router'da nearest-prototype yöntemi

**İmport Scripti:** `scripts/import_kachow_dataset.py`
- HuggingFace'den veya yerel kopyadan veri çekme
- YAML frontmatter parse → JSONL dönüşüm
- Mevzuat dosyalarını `data/mevzuat/` altına kopyalama
- Prototip vektörlerini `data/prototypes/` altına kopyalama
- Vakalar → `experiments/gold_sets/e2e_cases.jsonl` dönüşüm

**Değer:**
- Sınıflandırma doğruluğu ölçümü: 1763 etiketli belge ile F1 skoru hesaplama
- Halüsinasyon kontrolü: must_not_invent kısıtlarıyla taslak doğrulama
- RAG kalitesi: 7 temel kanun ile mevzuat kapsamını genişletme
- Intent doğruluğu: Prototip vektörleri ile benzerlik tabanlı niyet sınıflandırma

### 5.31 RBAC Genişletme [İYİLEŞTİRME] [ORTA] [KACHOW]

4 rol: ROOT, ADMIN, MANAGER, EMPLOYEE

### 5.32 LLM Token Tracking [İYİLEŞTİRME] [ORTA] [KACHOW]

Her LLM çağrısının token kullanımı, maliyet tahmini, pipeline trace

---

## 6. Dosya Yapısı — Yeni ve Değişecek Dosyalar

### Yeni Dosyalar (~40):
```
app/agents/assistant_agent.py
app/agents/revision_agent.py
app/agents/planning_orchestrator.py
app/services/chat_service.py
app/services/conversation_store.py
app/services/intent_router.py
app/services/interrupt_service.py
app/services/sse_broadcaster.py
app/services/field_extractor.py
app/services/structural_detector.py
app/services/deterministic_router.py
app/services/bm25_service.py
app/services/hybrid_retriever.py
app/services/query_scope_filter.py
app/services/writing_brief.py
app/services/draft_postprocessor.py
app/services/draft_verifier.py
app/services/draft_judge.py
app/services/input_guardrail.py
app/services/output_guardrail.py
app/services/pii_detector.py
app/services/context_manager.py
app/services/memory_summarizer.py
app/services/style_profiler.py
app/services/feedback_store.py
app/services/messaging_service.py
app/api/routes/chat.py
app/api/routes/messaging.py
app/api/routes/graph.py
frontend/assets/js/views/chat-view.js
frontend/assets/js/views/messages-view.js
frontend/assets/js/views/graph-view.js
frontend/assets/js/components/interrupt-panel.js
frontend/assets/js/components/workflow-stepper.js
frontend/assets/js/components/chat-dropzone.js
frontend/assets/js/components/thinking-bubble.js
frontend/assets/js/components/feedback-buttons.js
frontend/assets/js/components/context-ring.js
frontend/assets/js/components/draft-preview.js
data/topic_unit_map.json
data/intent_rules.json
data/boilerplate_titles.json
data/mevzuat/                          — KACHOW mevzuat korpusu (7 kanun)
data/prototypes/correspondence_type.json — belge türü embedding prototipleri
data/prototypes/intent.json            — niyet embedding prototipleri
scripts/import_kachow_dataset.py       — veri seti import scripti
experiments/eval_harness.py
experiments/gold_sets/
experiments/gold_sets/classification_gold.jsonl — 1763 etiketli belge
experiments/gold_sets/e2e_cases.jsonl          — 26 altın standart vaka
```

### Değişecek Dosyalar (~10):
```
app/agents/classifier_agent.py    — yapısal sinyal ekleme
app/agents/draft_agent.py         — yazım briefi + yanıt türleri
app/agents/routing_agent.py       — deterministik fallback
app/services/rag_service.py       — hibrit + boilerplate + kota
app/container.py                  — yeni servis alanları
app/main.py                       — yeni servis init
app/api/routes/config_routes.py   — yeni servis endpoint'leri
frontend/assets/js/core/api.js    — yeni API çağrıları
frontend/assets/css/app.css       — yeni bileşen stilleri
frontend/index.html               — yeni view routing
```

---

## 7. Uygulama Yol Haritası

| Aşama | Özellikler | Yeni Dosya | Efor |
|-------|-----------|-----------|------|
| **1: Chatbot Temeli + Veri** | Intent Router, ChatService, ConversationStore, SSE, Chat API, Chat frontend, PlanningOrchestrator, **KACHOW Veri Seti İmportu** (1763 belge + 26 vaka + 7 mevzuat + prototipler) | 8 | 3-4 gün |
| **2: HITL + Sınıflandırma** | InterruptService, Regex alan çıkarımı, Yapısal sinyal, Deterministik yönlendirme, WorkflowStepper, InterruptPanel | 7 | 3-4 gün |
| **3: RAG + Taslak** | BM25, Hibrit retriever, Boilerplate cezalandırma, Kapsam filtre, Yazım briefi, Post-processing, Yanıt türleri | 7 | 3-4 gün |
| **4: Doğrulama + Güvenlik** | Taslak doğrulama, Revizyon döngüsü, Guardrail'ler, PII tespit+maskeleme, TCKN/IBAN checksum | 7 | 3-4 gün |
| **5: Gelişmiş Özellikler** | AssistantAgent, RevisionAgent, Context management, Geri bildirim, Stil profili, Mesajlaşma | 6 | 3-4 gün |
| **6: Cilalama** | Bilgi grafı, Evaluation harness, Dashboard, Resmi yazı önizleme, Demo, Dokümantasyon | 4 | 2-3 gün |

**Toplam:** ~40 yeni dosya, ~10 güncelleme. Tahmini 17-23 gün.

---

## 8. Önemli Notlar

- **Gemma4:12b (Ollama)** üzerinde çalışıyoruz — dış API bağımlılığı yok, tamamen on-premise
- Bu, KADIM'in en büyük avantajını (kapalı devre) zaten karşılar
- Aşama 1-2 tamamlandığında KADIM seviyesinin üzerinde olacağız
- Aşama 4 sonunda KACHOW'un temel yeteneklerine ulaşacağız
- Aşama 5-6 ile KACHOW seviyesini yakalayıp geçeceğiz
