# Deney E4 — `ReasoningAgent` Ablation Analizi

**Kapsam:** FAZ 6B (`MAKALE_HAZIRLIK_PLANI.md` §3.4)  
**Veri:** `data/eval/classification/test.json` ($N=252$) + E1 `gemma4:12b` tahminleri (`results/e1/predictions.json`)  
**Betik:** `experiments/e4_ablation.py` · **Çıktılar:** `results/e4/ablation.csv`, `results/e4/rule_breakdown.csv`, `results/e4/ablation_metrics.json`

> [!WARNING]
> **Yorumlamadan önce bilinmesi gereken iki tasarım kısıtı:**
> 1. **Taslak, yönlendirme ve öncelik girdileri sentetiktir.** Deney gerçek `DraftAgent`/`RoutingAgent` çıktılarını kullanmaz. Taslak türü altın etikete göre atanır ve her 7. belgeye (`i % 7 == 0`, %14,3) bilerek şema dışı tür enjekte edilir; hedef birim anahtar kelime sezgisiyle, öncelik `i % 9` / `i % 5` kurallarıyla üretilir. Bu yüzden **taslak şema geçerliliği, `draft_type_consistency`, `priority_rules` ve `keyword_routing` satırları gerçek sistem davranışını ölçmez**; yalnızca kuralların yapay bozulmalara tepkisini gösterir.
> 2. **C3, test kümesi görülerek tasarlanmıştır.** C3'teki `structural_classification` kuralı, E1 test kümesi hata matrisinde gözlenen `karar` ↔ `kararname` karışıklığına bakılarak yazılmıştır ve aynı test kümesinde değerlendirilmiştir. C3'ün C0'a karşı kazancı (**+8 belge**) bu nedenle **iyimser yanlıdır** ve bağımsız bir küme (ör. `train`/`dev` veya yeni toplanmış belgeler) üzerinde doğrulanmadan genellenemez.
>
> Sınıflandırma sonuçları (C0 ve C1 doğruluk/F1, `keyword_classification` satırı) gerçek E1 tahminleri ve üretim kurallarıyla elde edildiğinden bu kısıtlardan etkilenmez.

---

## 1. Konfigürasyonlar

| Kod | Tanım |
|---|---|
| C0 | `ReasoningAgent` kapalı; E1 LLM çıktısı aynen kullanılır. |
| C1 | Üretim kural seti (`default_rules`) + `ConfidenceCalculator`, değiştirilmeden. |
| C2 | C1, ancak `ClassificationConsistencyRule` ve `RoutingConsistencyRule` yalnızca `info` kaydı düşer (ezme yok). |
| C3 | Önerilen v2: anahtar kelime ezmesi yok; `karar`/`kararname` için yapısal başlık kuralı; `RequiredFieldsRule` yalnızca yazışma türlerinde; güven skoru uyarılardan ayrık. **(post-hoc, bkz. uyarı)** |

## 2. Ana sonuçlar (`results/e4/ablation.csv`)

| Konfig. | Accuracy [%95 GA] | Macro-F1 [%95 GA] | Doğru düz. | Yanlış düz. | Yanlış→yanlış | ECE | Brier | McNemar $p$ (C0'a karşı) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C0 | 0,9048 [0,865–0,940] | 0,8979 [0,859–0,929] | 0 | 0 | 0 | 0,0808 | 0,0888 | — |
| **C1 (üretim)** | **0,3254** [0,270–0,385] | **0,3240** [0,259–0,371] | **0** | **146** | 14 | 0,2427 | 0,1188 | $2{,}2 \times 10^{-44}$ |
| C2 | 0,9048 [0,865–0,940] | 0,8979 [0,859–0,929] | 0 | 0 | 0 | 0,0833 | 0,0950 | 1,000 |
| C3 *(post-hoc)* | 0,9365 [0,905–0,964] | 0,9357 [0,902–0,962] | 8 | 0 | 0 | 0,0490 | 0,0579 | 0,0078 |

Sentetik girdilere bağlı sütunlar (yalnızca bilgi amaçlı): taslak şema geçerliliği C0 %85,7 (enjeksiyon oranının tümleyeni), C1 %90,5, C2/C3 %99,6; "yanlış eksik alan uyarısı" (normatif türlerde `pattern_missing_field` uyarısı) C1 198, C2 210, C3 0.

Gecikme: kural katmanı belge başına ortalama < 1 ms (p95 < 3,2 ms); LLM çağrısı yanında ihmal edilebilir.

## 3. Kural bazlı döküm (`results/e4/rule_breakdown.csv`, C1)

| Kural | Tetiklenme | Düzeltme | Doğru | Yanlış | Not |
|---|---:|---:|---:|---:|---|
| `keyword_classification` | 193 | 160 | 0 | **146** | Gerçek veri — ana bulgu |
| `pattern_missing_field` | 541 uyarı | — | — | 198 (normatif türlerde) | Gerçek metin; "yanlış" tanımı tür tabanlı sezgidir |
| `draft_type_consistency` | 48 | 48 | 24 | 24 | Sentetik girdi |
| `priority_rules` | 96 | 96 | — | — | Sentetik girdi; doğruluğu ölçülmedi |
| `keyword_routing` | 28 | 28 | — | — | Sentetik girdi; doğruluğu ölçülmedi |
| `pii_detection` | 13 | 0 | — | — | Bilgilendirme |

## 4. Yorum

1. **Ana bulgu (sağlam):** Üretim `ClassificationConsistencyRule`, ham anahtar kelime sayımına (`KeywordMatcher.best_document_type`) dayanarak 252 belgenin 160'ında LLM kararını değiştirmiş, bunların **146'sında doğru tahmini bozmuş** ve hiçbir hatayı düzeltmemiştir. Doğruluk %90,5'ten %32,5'e düşer ($p \approx 2 \times 10^{-44}$). Bu, üretim `ReasoningAgent`'ının mevcut haliyle sınıflandırmaya **net zarar** verdiğini gösterir; makalede "doğrulama katmanı güvenilirliği artırır" iddiası bu veriyle **desteklenmez**.
2. **Ezmenin kaldırılması (C2):** Anahtar kelime ezmesi kapatıldığında sınıflandırma C0 ile aynıdır; yani kalan kurallar sınıflandırmaya ne katkı ne zarar verir.
3. **C3 (ön bulgu):** Yapısal başlık kuralı test kümesinde 8 doğru, 0 yanlış düzeltme yapmıştır. Kural test kümesi görülerek yazıldığından bu kazanç bağımsız bir kümede doğrulanmalıdır; o zamana kadar makalede yalnızca "hedefli yapısal kuralların zararsız olabileceğine dair ön bulgu" olarak anılmalıdır.
4. **Güven skoru:** C1'de `ConfidenceCalculator` cezaları ortalama güveni 0,986'dan 0,501'e indirir ve ECE'yi 0,081'den 0,243'e yükseltir; yani üretim güven hesabı kalibrasyonu bozar.
