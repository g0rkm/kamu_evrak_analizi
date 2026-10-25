# Deney Ortamı Künyesi ve Performans Ölçüm Protokolü

> **Belge amacı:** JOINSSR makale hazırlığı kapsamında yürütülecek tüm deneylerin (E1–E6) başka bir araştırmacı veya makine tarafından birebir tekrarlanabilmesi için donanım, işletim sistemi, sürücü, yerel LLM (Ollama) model katmanları, çıkarım parametreleri ve veri/ölçüm kurallarını kayıt altına alır (Faz 0 ve Faz 8 — Hakem Raporu §3.3, §6, Tablo 8).

---

## 1. Donanım, İşletim Sistemi ve Sürücü Künyesi (Tablo 8)

| Bileşen | Değer / Ayrıntı |
|---|---|
| **GPU** | NVIDIA GeForce RTX 5070 (WDDM, Bus-ID `00000000:01:00.0`) |
| **VRAM** | 12,227 MiB (~12 GB GDDR7), güç sınırı 250 W |
| **NVIDIA Sürücüsü / CUDA** | NVIDIA-SMI / KMD Driver `616.64` · CUDA UMD `13.4` |
| **CPU** | AMD Ryzen 7 7700X 8-Core Processor (8 fiziksel çekirdek, 16 mantıksal iş parçacığı) |
| **Sistem Belleği (RAM)** | 16 GB DDR5 (`16,278,056,960` bayt / `15.16 GB` kullanılabilir fiziksel bellek) |
| **İşletim Sistemi** | Microsoft Windows 11 Pro (`10.0.26200`, Build `26200`) |

---

## 2. Yerel LLM Sunucusu ve Model Künyesi

### 2.1 Birincil Model (`gemma4:12b`)
| Parametre | Değer |
|---|---|
| **Sunucu / Çalıştırıcı** | Ollama `v0.40.8` (`runner: llamacpp`, OpenAI uyumlu `/v1/chat/completions` uç noktası) |
| **Model Etiketi** | `gemma4:12b` (`registry.ollama.ai/library/gemma4:12b`) |
| **Model Ailesi ve Boyutu** | `gemma4` · `11.9B` parametre (`model_format: gguf`, `renderer/parser: gemma4`) |
| **Nicemleme (Quantization)** | `Q4_K_M` (`imatrix-20260927-12b/model-q4_K_M.gguf`, `7,381,383,680` bayt / ~7.38 GB) |
| **Multimodal Projector Katmanı** | `12b/gguf/mmproj-bf16.gguf` (`175,115,616` bayt) |
| **Speculative Draft Katmanı** | `12b.gguf` (`gemma4-assistant`, `465,109,152` bayt, `draft_num_predict: 3`) |
| **Manifest Config SHA-256** | `sha256:e5ca99f918964e7d5a912f974eae708ae59370883a5b182fc0660fe7adf3f0e4` |
| **Model Ağırlık SHA-256** | `sha256:bb722270d54346adc198f213851dbe0207e87c3ecf2a0aff4d92262726215391` |
| **Params Blob SHA-256** | `sha256:2365fbb6d97bf654fdda0353b7505baa2254c662122cff0f153e4b47e6220ded` |

### 2.2 Alternatif Yerel Model (Faz 5 — Opsiyonel Baseline C Adayı)
| Parametre | Değer |
|---|---|
| **Model Etiketi** | `qwen3:8b` (`registry.ollama.ai/library/qwen3:8b`) |
| **Manifest Config SHA-256** | `sha256:05a61d37b08453e59290add468e3bb2f688e23a01e967fecb0e2fa41218cea76` |
| **Model Ağırlık SHA-256** | `sha256:a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f` (`5,225,374,496` bayt / ~5.23 GB) |

---

## 3. Çıkarım (Inference), Sampling ve İstemci Ayarları (`app/config.py`, `app/services/llm_service.py`)

| Ayar / Parametre | Değer | Açıklama |
|---|---|---|
| `LLM_API_BASE` | `http://localhost:11434/v1` | Yerel Ollama OpenAI uyumlu API adresi (`is_local = True`) |
| `LLM_NUM_CTX` (`options.num_ctx`) | `16384` | Bağlam penceresi uzunluğu (token) |
| `LLM_TEMPERATURE` (`temperature`) | `0.3` | Uygulama ve deney varsayılan sıcaklığı |
| Model Şablon Varsayılanları | `top_k: 64`, `top_p: 0.95` | Ollama `gemma4:12b` params blob varsayılanları |
| `reasoning_effort` | `"none"` | Yerel çağrılarda düşünme/muhakeme modu kapalıdır |
| Düşünme Bloğu Temizliği | `LLMService.strip_thinking` | `<\|channel>thought...<channel\|>` ve `<think>...</think>` blokları deterministik olarak silinir |
| JSON Modu (`response_format`) | `{"type": "json_object"}` | `LLMAgent.ask_json` / `LLMService.chat_json` çağrılarında aktif |
| JSON Onarım / Tekrar Deneme | 1 ek deneme | Yanıt geçerli JSON değilse `"Yanıtını YALNIZCA geçerli JSON olarak ver."` ekiyle 1 kez yeniden istenir |
| HTTP İstek Tekrarı (`LLM_MAX_RETRIES`) | `3` | HTTP `408, 409, 425, 429, 500, 502, 503, 504` ve zaman aşımında üstel geri çekilme (`2^attempt` sn, maks. `30.0` sn) |
| İstek Zaman Aşımı (`LLM_TIMEOUT_SECONDS`) | `180.0` sn | Tekil LLM HTTP çağrısı zaman aşımı; pipeline üst sınırı `300.0` sn |
| Eşzamanlı İstek Sınırı (`LLM_MAX_CONCURRENT_REQUESTS`) | `2` | `asyncio.Semaphore(2)` ile yerel GPU kuyruk koruması |
| Model Bellekte Tutma (`LLM_KEEP_ALIVE`) | `"30m"` | Modelin VRAM'den düşmemesi için saklama süresi |
| Yanıt Önbelleği (`LLM_CACHE_TTL_SECONDS`) | `3600` sn (Üretim) / `0` (Deney) | SHA-256 anahtarlı bellek-içi önbellek. **Not:** Gecikme ve tekrarlı deneylerde (E6) önbellek devre dışı bırakılır (`LLM_CACHE_TTL_SECONDS=0` veya her koşu öncesi `.clear()`). |

---

## 4. Yazılım Ortamı ve Bağımlılık Künyesi

- **Python Sürümü:** `Python 3.11.8`
- **Tam Dondurulmuş Paket Listesi:** [`experiments/requirements.lock.txt`](../experiments/requirements.lock.txt) (`pip freeze`, 331 paket)
- **Temel Proje Kütüphaneleri (kilitli sürümler):**
  - `fastapi==0.128.8`, `uvicorn==0.51.0`, `httpx==0.28.1`
  - `pydantic==2.12.5`, `pydantic-settings==2.14.2`
  - `scikit-learn==1.8.0`, `numpy==1.26.4`, `scipy==1.15.3` (RAG TF-IDF: `RAG_TOP_K=8`, `RAG_CHUNK_SIZE=600`, `RAG_CHUNK_OVERLAP=100`)
  - `PyMuPDF==1.28.2`, `pytesseract==0.3.13`, `pillow==12.1.1`
  - `huggingface_hub==2.3.0`, `pytest==8.0.0`, `pytest-asyncio==1.4.0`
- **Dal (Branch) ve Başlangıç Noktası:**
  - Kaynak dal: `Develop` (`69c8a3f`)
  - Çalışma dalı: `makale-hazirlik`

### Ortamı Başka Bir Makinede Kurma
```bash
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r experiments/requirements.lock.txt
ollama pull gemma4:12b         # Digest doğrulaması: sha256:bb722270d543...
python scripts/setup_data.py   # RAG korpusu (g0rkm/kamu-evrak-korpus) ve yerel TF-IDF indeksi
```

---

## 5. Veri ve Çıktı Versiyonlama Politikası (`.gitignore`)

Hakem raporundaki veri mahremiyeti (§2, §5.3) ve tekrarlanabilirlik (§4.2, §6) ilkeleri doğrultusunda:
1. **Versiyonlanan (Git'e dahil edilen) dosyalar:**
   - `data/eval/classification/`, `data/eval/rag/`, `data/eval/drafts/` altındaki **anonimleştirilmiş** değerlendirme kümeleri, etiket şemaları (`labels_schema.json`) ve veri bölünme (`seed`) kayıtları.
   - `results/` altındaki toplulaştırılmış metrik dosyaları (`.json`, `.csv`), karışıklık matrisleri ve şekiller.
2. **Versiyonlanmayan (`.gitignore` ile hariç tutulan) dosyalar:**
   - Ham kişisel veri (PII) içerebilecek veya anonimleştirilmemiş belgeler (`data/eval/**/raw/`, `results/**/raw/`, `*.raw.*`, `*.pii.*`).
   - Uygulama çalışma zamanı verileri ve logları (`data/history/`, `data/logs/`, `data/backups/`, `data/auth/`, `data/notifications/`, `data/templates/`, `uploads/`).

---

## 6. Performans ve Gecikme Ölçüm Kuralları (Faz 8 — E6 Çerçevesi)

> *Bu bölüm Faz 8'de (`experiments/e6_latency.py`) uygulanacak deney protokolünün temel kurallarını tanımlar:*

1. **İki Hız Metriğinin Ayrıştırılması (Hakem §3.3):**
   - **Tekil Sınıflandırma Süresi:** Yalnızca `ClassifierAgent.execute()` çağrısının uçtan uca süresi.
   - **Orkestrasyon / Pipeline Süresi:** `OrchestratorAgent.run()` kapsamında çalışan 6 LLM ajanının (3 paralel aşama: `Classifier ‖ Analyzer` → `Legislation ‖ Summary` → `Draft ‖ Routing`) ve deterministik adımların (`OCRAgent`, `ReasoningAgent`) hem tekil ajan bazında hem aşama bazında duvar saati (wall-clock) süreleri.
   - Paralel aşamalarda `LLM_MAX_CONCURRENT_REQUESTS` semaforunun kuyruk etkisi açıkça kaydedilir.
2. **Soğuk Başlangıç (Cold Start) ve Sıcak Çağrı (Warm Inference) Ayrımı:**
   - **Soğuk başlangıç:** Model VRAM'de yüklü değilken (`ollama stop gemma4:12b` sonrası ilk istek) ağırlıkların diskten GPU belleğine yüklenme süresi dahil ölçüm.
   - **Sıcak çağrı:** Model VRAM'de yüklüyken (`keep_alive` aktif) ve uygulama içi `_LLMCache` devre dışıyken (`ttl=0`) yapılan ardışık ölçümler.
3. **Belge Uzunluğu Grupları ve Tekrarlı Ölçüm:**
   - Belgeler karakter/token uzunluğuna göre **kısa**, **orta** ve **uzun** gruplara ayrılır.
   - Her koşulda tekil sıcak koşu yerine çoklu tekrar (`N` tekrar) üzerinden **ortalama, standart sapma, medyan, p95, %95 güven aralığı (GA)** ile kısmi/başarısız analiz oranı ve tepe VRAM/RAM kullanımı raporlanır.
