# Deney E6 — Performans ve Tekrarlanabilirlik Ölçümü

**Kapsam:** FAZ 8 (`MAKALE_HAZIRLIK_PLANI.md` §3.3, §6, Tablo 8)
**Betik:** `experiments/e6_latency.py` · **Çıktılar:** `results/e6/latency.json`, `results/e6/latency.csv`
**Model/Donanım:** `gemma4:12b` (`Q4_K_M`), NVIDIA RTX 5070 (12 GB), Ollama `0.40.11`, `LLM_MAX_CONCURRENT_REQUESTS=2`, `num_ctx=16384`, `temperature=0.3`. Tam künye: [`docs/olcum_protokolu.md`](../../docs/olcum_protokolu.md). Örnek: Resmî Gazete korpusundan `seed=42` ile 3 uzunluk grubu × 3 belge × 5 tekrar. **0 başarısız istek.**

> **NOT:** `ClassifierAgent` girdiyi 3000 karaktere kırpar (`max_input_chars`); bu nedenle "uzun" belgelerde sınıflandırma süresi girdi uzunluğuyla doğrusal artmaz (girdi üst sınırı sabittir).

## 1. İki hız metriğinin ayrıştırılması (Hakem §3.3)

| Koşul | kısa | orta | uzun |
|---|---:|---:|---:|
| **İzole sınıflandırıcı** (ortalama, sn) | **0,97** | **1,07** | **1,11** |
| — medyan / p95 | 0,94 / 1,06 | 0,94 / 1,74 | 0,90 / 2,18 |
| — %95 GA (ortalama) | [0,94–1,01] | [0,92–1,28] | [0,87–1,39] |
| **Eşzamanlı sınıflandırıcı** (Classifier ‖ Analyzer, ortalama sn) | **3,31** | **3,58** | **2,02** |
| — medyan / p95 | 4,01 / 5,22 | 4,79 / 5,15 | 1,39 / 5,36 |
| **Aşama duvar-saati** (max(Classifier, Analyzer), ortalama sn) | 4,79 | 5,48 | 6,10 |

**Bulgu:** README'deki **~1,3 sn** (tekil sınıflandırma) ve **4,36 sn** (pipeline içindeki sınıflandırma çağrısı) *farklı koşullara* aittir ve ikisi de yeniden üretildi:
- **İzole** (tek ajan, sıcak) sınıflandırma ortalama **~1,0 sn**'dir.
- Aynı çağrı, aşama 2'de `AnalyzerAgent` ile **eşzamanlı** çalışıp tek GPU'yu paylaştığında ortalama **~3,3–3,6 sn**'ye (kısa/orta) yükselir. Fark, GPU hesaplama çekişmesinden kaynaklanır; `LLM_MAX_CONCURRENT_REQUESTS=2` semaforu bellek kuyruğunu korur ama tek GPU hesaplamayı seri yapar.
- "uzun" grubun eşzamanlı ortalamasının düşük (2,02 sn) ve medyanının (1,39 sn) oynak olması küçük örneklem + GPU zamanlama varyansındandır; p95 (5,36 sn) diğer gruplarla uyumludur.

## 2. Soğuk başlangıç, VRAM ve throughput

| Metrik | Değer |
|---|---:|
| **Soğuk başlangıç** (`ollama stop` sonrası ilk çağrı; ağırlık yükleme dâhil) | **7,65 sn** |
| **Tepe VRAM** (taban 1.489 MiB) | **10.783 MiB** (~10,5 / 12 GB) |
| Throughput — sıralı (6 belge) | 8,05 sn · **0,75 belge/sn** |
| Throughput — eşzamanlı (6 belge) | 7,38 sn · **0,81 belge/sn** |
| Başarısız istek | 0 |

**Bulgu:** Soğuk başlangıç (7,65 sn) sıcak çağrıdan (~1 sn) açıkça ayrılmalıdır; tek sıcak koşu ortalama gibi sunulmamalıdır. Tepe VRAM (~10,8 GB) README'deki ~10,2 GB iddiasını doğrular ve 12 GB'a sığar. Tek GPU'da eşzamanlılık throughput'u yalnızca **~%8** artırır (hesaplama seri); yani eşzamanlı istek sınırı bir bellek/kuyruk koruması olup doğrusal hızlanma sağlamaz.

## 3. Sınırlılıklar
- Küçük örneklem (grup başı 3 belge × 5 tekrar = 15 ölçüm); değerler yön gösterir.
- Tek donanım profili (RTX 5070 12 GB); CPU-only veya farklı GPU'larda sonuç değişir.
- Sınıflandırma girdisi 3000 karaktere kırpıldığından uzunluk etkisi sınırlıdır; tam pipeline (6 ajan) uçtan uca süresi ayrıca ölçülmemiştir (bu deney tekil ajan ve aşama-2 eşzamanlılığına odaklanır).
