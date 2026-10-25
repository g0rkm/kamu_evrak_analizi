# Deney E4 — `ReasoningAgent` ve Doğrulama Kuralları Ablation (Bileşen Çıkarma) Analiz Raporu

**Tarih:** 2026-10-25  
**Kapsam:** FAZ 6B — Deney E4 (`MAKALE_HAZIRLIK_PLANI.md` §3.4)  
**Veri Kümesi:** `data/eval/classification/test.json` ($N=252$, 18 sınıf $\times$ 14 evrak) ve Deney E1 `gemma4:12b` ham tahminleri (`results/e1/predictions.json`)

---

## 1. Araştırma Sorusu ve Deney Tasarımı

Sistemdeki `ReasoningAgent` (`app/agents/reasoning_agent.py` ve `app/agents/validation_rules.py`), LLM tabanlı ajanların (`AnalyzerAgent`, `DraftAgent`, `RoutingAgent`) çıktılarını deterministik kurallarla denetleyen nöro-sembolik bir doğrulama katmanı olarak tasarlanmıştır. Ancak kural tabanlı bir son-işleme (post-processing) katmanının gerçekten hataları mı düzelttiği, yoksa LLM'in doğru tahminlerini mi bozduğu (`false correction`) ampirik olarak ölçülmek zorundadır.

Bu amaçla $N=252$ test evrakı üzerinde **4 farklı konfigürasyon** karşılaştırılmıştır:
1. **`C0_Reasoning_OFF` (Yalnızca LLM — Baz Çizgisi):** `ReasoningAgent` tamamen devre dışı; `gemma4:12b` çıktıları doğrudan kullanılır.
2. **`C1_Reasoning_ON_v1_Default` (Mevcut Üretim `ReasoningAgent`):** Üretim kodundaki 6 kural (`ClassificationConsistencyRule`, `DraftTypeConsistencyRule`, `RoutingConsistencyRule`, `PriorityRule`, `RequiredFieldsRule`, `PersonalDataRule`) ve `ConfidenceCalculator` (`-0.05` düzeltme, `-0.03` uyarı cezası) olduğu gibi çalıştırılır.
3. **`C2_Reasoning_ON_No_Kw_Override` (Anahtar Kelime Ezmesi Devre Dışı):** `ClassificationConsistencyRule` ve `RoutingConsistencyRule` içindeki ham anahtar kelime sayımına dayalı sınıf/birim değiştirme (`override`) kapatılıp yalnızca `info` seviyesinde loglanır; şema (`DraftTypeConsistencyRule`), öncelik ve zorunlu alan kuralları aktif tutulur.
4. **`C3_Reasoning_ON_v2_Calibrated` (Önerilen Kalibre Nöro-Sembolik `ReasoningAgent v2`):**
   - Ham anahtar kelime sayımıyla sınıf ezme yerine, E1 hata matrisinde saptanan en büyük karışıklık sınırı (`kararname` $\leftrightarrow$ `karar`) için **Yapısal Başlık Ayrıştırma Kuralı (`structural_classification`)** (`"CUMHURBAŞKANI KARARI"` / `"Karar Sayısı:"` vs `"CUMHURBAŞKANLIĞI KARARNAMESİ"` / `"Kararname Numarası"`) uygulanır.
   - `DraftTypeConsistencyRule`, doğru sınıf etiketi üzerinde taslak şeması uyumluluğunu (`DOCUMENT_TYPES[doc_type].draft_types`) zorunlu kılar.
   - `RequiredFieldsRule` yalnızca yazışma/başvuru türlerine (`dilekce`, `resmi_yazi`, `talep_yazisi`, `bilgilendirme`, `gorus_sorma`, `sikayet`, `kurum_ici`) uygulanır; Resmi Gazete normatif metinlerinde (`kanun`, `kararname`, `yonetmelik`, `teblig`, `ilan`, `karar`) yanlış `"sayı:"`/`"konu:"` eksikliği uyarısı üretmez.
   - Sınıflandırma güven skoru (`confidence`), zorunlu alan veya KVKK uyarılarından ayrıştırılarak (decoupled) kalibrasyon bozulması önlenir.

---

## 2. Ablation Deneyi Ana Bulguları (`results/e4/ablation.csv`)

| Konfigürasyon | Accuracy [%95 GA] | Macro-F1 [%95 GA] | Doğru Düzeltme (TP) | Yanlış Düzeltme (FP) | Yanlıştan Yanlışa | Taslak Şema Geçerliliği | Yanlış Eksik Alan Uyarısı | Ort. Güven | ECE $\downarrow$ | Brier $\downarrow$ | McNemar $p$ (vs C0) | Gecikme (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`C0_Reasoning_OFF`** | 0.9048 [0.865, 0.940] | 0.8979 [0.859, 0.929] | 0 | 0 | 0 | %85,71 | 0 | 0.9855 | 0.0808 | 0.0888 | 1.000 | **0.0001** |
| **`C1_Reasoning_ON_v1_Default`** | **0.3254** [0.270, 0.385] | **0.3240** [0.259, 0.371] | **0** | **146** | **14** | %90,48 | **198** | 0.5010 | **0.2427** | 0.1188 | **$2.24 \times 10^{-44}$** | 0.4736 |
| **`C2_Reasoning_ON_No_Kw_Override`** | 0.9048 [0.865, 0.940] | 0.8979 [0.859, 0.929] | 0 | 0 | 0 | **%99,60** | 210 | 0.8214 | 0.0833 | 0.0950 | 1.000 | 0.6104 |
| **`C3_Reasoning_ON_v2_Calibrated`** | **0.9365 [0.905, 0.964]** | **0.9357 [0.902, 0.962]** | **8** | **0** | **0** | **%99,60** | **0** | 0.9855 | **0.0490** | **0.0579** | **0.0078** | 0.5024 |

---

## 3. Kural Bazlı Etki Analizi (`results/e4/rule_breakdown.csv`)

| Kural Kodu | Kural Başlığı | Konfigürasyon | Tetiklenme | Düzeltme (`correction`) | Uyarı (`warning`) | Bilgi (`info`) | Doğru Müdahale (TP) | Yanlış Müdahale (FP) | Kesinlik (Precision) | Net Doğruluk Etkisi |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `keyword_classification` | Sınıflandırma tutarlılığı | `C1_v1_Default` | 193 | 160 | 0 | 33 | 0 | **146** | %0,0 | **-146 evrak (-%57,94)** |
| `draft_type_consistency` | Taslak türü uygunluğu | `C1_v1_Default` | 48 | 48 | 0 | 0 | 24 | **24** | %50,0 | 0 (zincirleme bozulma) |
| `pattern_missing_field` | Zorunlu alan kontrolü | `C1_v1_Default` | 541 | 0 | 541 | 0 | 0 | **198** | %0,0 | -198 yanlış uyarı |
| `keyword_routing` | Yönlendirme tutarlılığı | `C1_v1_Default` | 28 | 28 | 0 | 0 | 0 | 0 | — | 0 |
| `priority_rules` | Öncelik kuralı | `C1_v1_Default` | 96 | 96 | 0 | 0 | — | — | — | Kural tabanlı yükseltme |
| `pii_detection` | Kişisel veri (KVKK) tespiti | `C1_v1_Default` | 13 | 0 | 1 | 12 | — | — | — | Bilgilendirme / Maskeleme |
| `structural_classification` | Yapısal sınıflandırma | `C3_v2_Calibrated` | **8** | **8** | 0 | 0 | **8** | **0** | **%100,0** | **+8 evrak (+%3,17)** |
| `keyword_classification` | Sınıflandırma tutarlılığı | `C3_v2_Calibrated` | 189 | 0 | 0 | 189 | 0 | 0 | — | 0 (yalnızca `info` logu) |
| `draft_type_consistency` | Taslak türü uygunluğu | `C3_v2_Calibrated` | **36** | **36** | 0 | 0 | **35** | **1** | **%97,2** | **+%13,89 şema uyumu** |
| `pattern_missing_field` | Zorunlu alan kontrolü | `C3_v2_Calibrated` | 161 | 0 | 161 | 0 | 0 | **0** | — | **0 yanlış uyarı** |

---

## 4. Tartışma ve Mimari Çıkarımlar

1. **Naif Anahtar Kelime Sayımının Yıkıcı Etkisi (`C1` Bulgusu):**
   Üretimdeki `KeywordMatcher.best_document_type` metodu, her sınıf için tanımlanan anahtar kelimelerin metin içinde geçme sayısını (`sum(kw in text_lower)`) hesaplamaktadır. Ancak `"t.c."`, `"sayı:"`, `"konu:"`, `"arz ederim"` (`resmi_yazi` / `dilekce`) veya `"madde"`, `"kanun"`, `"yürürlük"` (`kanun`) gibi genel ifadeler neredeyse tüm kamu evraklarında geçtiğinden, `ClassificationConsistencyRule` `252` evrakın **`160`'ında LLM kararını ezmiş**; bunların **`146`'sında `gemma4:12b`'nin doğru tahminini bozmuş**, hiçbir evrakta (`0/160`) doğru düzeltme yapamamıştır. Bu bulgu, güçlü bir yerel LLM'in (`%90,48` doğruluk) arkasında basit kelime frekansı kuralı çalıştırmanın doğruluğu **`%32,54`'e** düşürdüğünü kanıtlamaktadır ($p = 2.24 \times 10^{-44}$).
2. **Zincirleme (Cascading) Hata Yayılımı:**
   `C1` konfigürasyonunda `DraftTypeConsistencyRule`, `ClassificationConsistencyRule`'dan *sonra* çalıştığı için, önce sınıfı yanlışlıkla (örneğin `mali_evrak` veya `teblig` iken `resmi_yazi` olarak) değiştirilen evrakların doğru taslak türlerini de (`24` evrakta) bozmuştur. Anahtar kelime ezmesi kapatıldığında (`C2` ve `C3`), `DraftTypeConsistencyRule` `%97,2` kesinlikle çalışarak taslak şema geçerliliğini `%85,71`'den **`%99,60`'a (`251/252`)** çıkarmaktadır.
3. **Kalibre Nöro-Sembolik Doğrulamanın Katkısı (`C3` Bulgusu):**
   Sembolik kurallar kelime sayımı yerine **belge-yapısal değişmezlere (structural invariants)** odaklandığında (örn. Resmi Gazete'de `"CUMHURBAŞKANI KARARI"` ve `"Karar Sayısı:"` başlığı taşıyan bireysel idari kararların normatif `"CUMHURBAŞKANLIĞI KARARNAMESİ"` sınıfından ayrıştırılması), `C3_Reasoning_ON_v2_Calibrated` modeli **8 doğru düzeltme ve 0 yanlış düzeltme** (`McNemar` $p = 0.0078$) ile genel doğruluğu **`%90,48`'den `%93,65`'e (`+3,17` puan)**, `Macro-F1` skorunu **`0.8979`'dan `0.9357`'ye (`+3,78` puan)** yükseltmekte ve beklenen kalibrasyon hatasını (`ECE`) **`0.0808`'den `0.0490`'a** indirmektedir.
