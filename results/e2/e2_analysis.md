# E2 Deneyi: Baseline ve Alternatif Model Karşılaştırma Raporu (Faz 5)

> **Deney Künyesi (Hakem Raporu §3.2, Tablo 7-E2, Tablo 12-P3):**
> - **Betikler:** `experiments/baseline_rule.py`, `experiments/baseline_ml.py` (`python -m experiments.baseline_ml`)
> - **Eğitim / Kalibrasyon Kümesi (Klasik ML için):** `data/eval/classification/dev.json` (`n = 108` belge, 18 sınıf × 6 örnek, `seed = 42`)
> - **Kör Değerlendirme Kümesi (Tüm Yöntemler İçin Ortak):** `data/eval/classification/test.json` (`n = 252` belge, 18 sınıf × 14 örnek, `seed = 42`)
> - **Donanım ve Çıkarım Ortamı:** NVIDIA GeForce RTX 5070 (12 GB GDDR7 VRAM) · AMD Ryzen 7 7700X · 16 GB DDR5 RAM · Ollama `v0.40.8` (`temperature = 0.3`, `num_ctx = 16384`, `max_input_chars = 3000`, `reasoning_effort = "none"`)

---

## 1. Karşılaştırılan Yöntemler ve Deneysel Tasarım

Hakem Raporu §3.2'de belirtilen *"0.935 (ve 18 sınıfta 0.8979) skorunun daha basit yöntemlere kıyasla ne ölçüde katma değer sağladığının gösterilmesi"* gereksinimi doğrultusunda aynı 252 belgelik kör test kümesi üzerinde **6 yöntem** karşılaştırılmıştır:

1. **Baseline A1 — Kural Tabanlı (Taksonomi Anahtar Kelime Eşleştirici / `rule_taxonomy_keywords`):** `app/core/taxonomy.py` içindeki `DOCUMENT_TYPES` etiket ve anahtar kelimelerini başlıkta ($2\times$–$3\times$ ağırlıklı) ve gövde metninde sayarak en yüksek puanlı sınıfı atayan deterministik sınıflandırıcı.
2. **Baseline A2 — Kural Tabanlı (Başlık ve Yapısal Biçim Kuralları / `rule_header_structural`):** Türk kamu mevzuatı ve resmî yazışma başlık/biçim kalıplarını (`Kanun Numarası`, `Kararname Numarası`, `Karar Sayısı`, `Yönetmeliği`, `Tebliği`, `Genelge`, `Yönergesi`, `Tutanak`, `Rapor`, `Sözleşme`, `İlan` ve söz eylemi ipuçları) öncelik sırasıyla denetleyen kural sınıflandırıcısı.
3. **Baseline B1 — Klasik ML (`TF-IDF + Logistic Regression`):** `dev.json` (`n=108`) üzerinde kelime (`1–2` n-gram, `15.000` özellik) ve karakter (`char_wb`, `3–5` n-gram, `25.000` özellik) `FeatureUnion` TF-IDF vektörleriyle eğitilen L2-düzenlileştirmeli Lojistik Regresyon (`C=2.0, random_state=42`).
4. **Baseline B2 — Klasik ML (`TF-IDF + LinearSVC`):** Aynı `FeatureUnion` TF-IDF temsiliyle `dev.json` (`n=108`) üzerinde eğitilen doğrusal Destek Vektör Makinesi (`LinearSVC`, `C=1.0, random_state=42`).
5. **Baseline C — Alternatif Yerel LLM (`qwen3:8b`, `Q4_K_M`, 8.2B):** Aynı donanımda, aynı `ClassifierAgent` sistem istemi ve aynı hiperparametrelerle (`temperature=0.3`, `num_ctx=16384`, `max_input_chars=3000`) sıfır-örnekli (zero-shot) çalıştırılan alternatif açık ağırlıklı yerel model.
6. **Önerilen Referans Model (`gemma4:12b`, `Q4_K_M`, 12.2B):** Sistemin varsayılan sıfır-örnekli sınıflandırma ajanı (`E1` deneyi çıktısı).

---

## 2. Genel Performans ve Güven Aralığı Tablosu (`n = 252` Test Kümesi)

| Yöntem | Kategori | Eğitim Verisi | Doğruluk (Accuracy) | %95 Wilson GA | Macro-F1 | %95 Bootstrap F1 GA (`B=2000`) | Sınır Toleranslı Doğruluk | Ortalama Süre (`ms/belge`) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **Baseline A1:** Kural (Taksonomi Keywords) | Kural Tabanlı | Yok | 0.5397 | `[0.4780, 0.6002]` | 0.5368 | `[0.4800, 0.5816]` | 0.6151 | 0.05 ms |
| **Baseline A2:** Kural (Başlık/Yapısal Regex) | Kural Tabanlı | Yok | 0.6468 | `[0.5860, 0.7032]` | 0.6850 | `[0.6239, 0.7329]` | 0.7103 | 0.02 ms |
| **Baseline B1:** TF-IDF + Logistic Regression | Klasik ML | `dev` (`n=108`) | 0.7579 | `[0.7014, 0.8067]` | 0.7544 | `[0.6959, 0.7998]` | 0.7897 | 0.72 ms |
| **Baseline B2:** TF-IDF + LinearSVC | Klasik ML | `dev` (`n=108`) | 0.7619 | `[0.7056, 0.8103]` | 0.7568 | `[0.6978, 0.8023]` | 0.8056 | 0.66 ms |
| **Baseline C:** Qwen 3 8B (`qwen3:8b`) | Yerel LLM | Yok (Zero-Shot) | 0.7500 | `[0.6931, 0.7994]` | 0.7301 | `[0.6734, 0.7750]` | 0.8214 | 1224.56 ms |
| **Önerilen:** **Gemma 4 12B (`gemma4:12b`)** | **Yerel LLM** | **Yok (Zero-Shot)** | **0.9048** | **`[0.8622, 0.9352]`** | **0.8979** | **`[0.8598, 0.9294]`** | **0.9286** | **1194.25 ms** |

---

## 3. İstatistiksel Anlamlılık Testleri (Referans: `Gemma 4 12B`)

Her bir baseline yöntemi ile `Gemma 4 12B` arasındaki performans farkı; **(i)** `B = 2000` tekrarlı eşleştirilmiş (paired) bootstrap güven aralığı ve **(ii)** uyuşmayan (discordant) tahmin çiftleri üzerinden **McNemar tam binom testi** (`scipy.stats.binomtest`) ile sınanmıştır:

| Karşılaştırma (`Gemma 4 12B` vs. Baseline) | $\Delta$ Macro-F1 | Eşleştirilmiş Bootstrap %95 GA | $\Delta$ Accuracy | Eşleştirilmiş Bootstrap %95 GA | McNemar $b$ *(Gemma Doğru, Base Yanlış)* | McNemar $c$ *(Gemma Yanlış, Base Doğru)* | McNemar Tam $p$-Değeri | Eşleştirilmiş Bootstrap $p$ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| vs. **Baseline A1 (Keywords)** | **+0.3611** | `[+0.3054, +0.4246]` | **+0.3651** | `[+0.3016, +0.4325]` | 101 | 9 | $7.84 \times 10^{-21}$ | $< 0.0001$ |
| vs. **Baseline A2 (Başlık/Yapısal)** | **+0.2129** | `[+0.1578, +0.2777]` | **+0.2580** | `[+0.1905, +0.3254]` | 78 | 13 | $1.85 \times 10^{-12}$ | $< 0.0001$ |
| vs. **Baseline B1 (TF-IDF + LogReg)** | **+0.1435** | `[+0.0877, +0.2072]` | **+0.1469** | `[+0.0873, +0.2103]` | 51 | 14 | $4.48 \times 10^{-6}$ | $< 0.0001$ |
| vs. **Baseline B2 (TF-IDF + LinearSVC)** | **+0.1411** | `[+0.0821, +0.2043]` | **+0.1429** | `[+0.0794, +0.2063]` | 51 | 15 | $1.01 \times 10^{-5}$ | $< 0.0001$ |
| vs. **Baseline C (Qwen 3 8B)** | **+0.1678** | `[+0.1229, +0.2208]` | **+0.1548** | `[+0.1111, +0.2024]` | 41 | 2 | $2.15 \times 10^{-10}$ | $< 0.0001$ |

> **İstatistiksel Sonuç:** `Gemma 4 12B`, hem kural tabanlı yaklaşımlara (`+21.3` ile `+36.1` Macro-F1 puanı, $p < 10^{-11}$), hem `dev` kümesinde eğitilmiş klasik TF-IDF + DVM/Lojistik Regresyon modellerine (`+14.1` ile `+14.4` Macro-F1 puanı, $p \le 1.01 \times 10^{-5}$), hem de aynı donanımdaki 8B parametreli alternatif yerel LLM'e (`+16.8` Macro-F1 puanı, $p = 2.15 \times 10^{-10}$) kıyasla **istatistiksel olarak yüksek düzeyde anlamlı** üstünlük sağlamaktadır.

---

## 4. Sınıf Bazında F1 Karşılaştırma Tablosu (18 Sınıf)

| Sınıf Kodu | Kural A1 (Keywords) | Kural A2 (Başlık/Biçim) | Klasik ML B1 (TF-IDF+LogReg) | Klasik ML B2 (TF-IDF+LinearSVC) | Yerel LLM C (`qwen3:8b`) | **Önerilen (`gemma4:12b`)** |
|---|---:|---:|---:|---:|---:|---:|
| `dilekce` | 0.7500 | 0.7200 | 0.6429 | 0.6923 | 0.8966 | **1.0000** |
| `resmi_yazi` | 0.2020 | 0.2299 | 0.5405 | 0.5143 | 0.3846 | **0.8750** |
| `talep_yazisi` | 0.3158 | 0.3000 | 0.4444 | 0.4444 | 0.7429 | **0.9333** |
| `bilgilendirme` | 0.1333 | 0.5263 | 0.4545 | 0.4545 | 0.5263 | **0.7857** |
| `gorus_sorma` | 0.2500 | 0.4444 | 0.7692 | 0.6923 | 0.5263 | **0.9231** |
| `sikayet` | 0.6667 | 0.7826 | 0.6923 | 0.7586 | **1.0000** | **1.0000** |
| `kurum_ici` | 0.0000 | 0.5263 | 0.5600 | 0.5833 | 0.7273 | **0.8333** |
| `genelge` | 0.9231 | 0.9231 | 0.7692 | 0.7692 | 0.9231 | **0.9630** |
| `rapor` | 0.8000 | 0.8462 | 0.8276 | 0.8571 | 0.8667 | **1.0000** |
| `tutanak` | 0.1250 | 0.8889 | 0.9286 | 0.8966 | 0.8148 | **1.0000** |
| `yonetmelik` | 0.8750 | 0.9286 | 0.8387 | 0.8387 | 0.7179 | **0.9333** |
| `teblig` | **0.9630** | 0.8800 | 0.8667 | 0.8966 | 0.8485 | 0.9286 |
| `kanun` | 0.5957 | 0.7778 | 0.9333 | 0.9333 | 0.9333 | **1.0000** |
| `karar` | 0.7027 | **0.8667** | 0.6667 | 0.7143 | 0.1000 | 0.4211 |
| `kararname` | 0.1333 | 0.6667 | **0.9630** | 0.9286 | 0.5882 | 0.6667 |
| `ilan` | 0.7273 | 0.5217 | 0.9630 | 0.9286 | 0.8485 | **0.9655** |
| `yonerge` | 0.8333 | 0.8333 | **0.9333** | **0.9333** | 0.8000 | **0.9333** |
| `sozlesme` | 0.6667 | 0.6667 | 0.7857 | 0.7857 | 0.8966 | **1.0000** |

---

## 5. Temel Analitik Bulgular (Makale Tartışma Bölümü İçin)

1. **İdari Yazışma Sınıflarında LLM'in Bağlamsal Üstünlüğü:**
   Biçimsel şablonu (`T.C.`, `Sayı:`, `Konu:`) ortak olan ve ayrımı yalnızca son paragraftaki söz eylemine (bilgi verme, kaynak/ödenek talep etme, hukuki mütalaa sorma, kurum içi koordinasyon, bireysel başvuru vs. şikâyet) dayanan 7 idari yazışma sınıfında (`dilekce`, `resmi_yazi`, `talep_yazisi`, `bilgilendirme`, `gorus_sorma`, `sikayet`, `kurum_ici`) kural tabanlı modeller (`0.33–0.50` ortalama F1) ve TF-IDF modelleri (`0.59–0.61` ortalama F1) yetersiz kalırken, `Gemma 4 12B` **`0.9072` ortalama F1** elde etmiştir.
2. **`karar` ↔ `kararname` Ayrımında Kural ve Klasik ML Tamamlayıcılığı (Hibrit Mimari Kanıtı):**
   Sıfır-örnekli her iki yerel LLM (`qwen3:8b` `F1=0.1000`, `gemma4:12b` `F1=0.4211`), `"CUMHURBAŞKANI KARARI (Karar Sayısı: ...)"` ibaresini anayasal `"Cumhurbaşkanlığı Kararnamesi"` ile karıştırırken; açık başlık dizgisi (`"karar sayısı"` vs `"kararname numarası"`) arayan **Baseline A2 (`F1=0.8667`)** ve karakter/kelime n-gram ağırlıklarını öğrenen **TF-IDF + LinearSVC (`F1=0.7143` / `0.9286`)** bu iki sınıfı çok daha iyi ayırmıştır. Bu bulgu, sistemde LLM çıktılarının deterministik kurallarla (`ReasoningAgent`) denetlenmesi gerektiği yönündeki hibrit tasarım tezini doğrudan doğrulamaktadır.
3. **Hız – Doğruluk Ödünleşimi (Latency–Accuracy Trade-off):**
   TF-IDF + LinearSVC modeli belge başına `0.66 ms` gecikmeyle `%76.19` doğruluk sunarken, `Gemma 4 12B` belge başına `1194.25 ms` (`~1.19 sn`) gecikmeyle doğruluğu `%90.48`'e (`+14.29` puan) taşımaktadır. `Qwen 3 8B` ise benzer gecikmeye (`1224.56 ms`) rağmen Türkçe idari/hukuki ayrımlarda (`yonetmelik` ↔ `yonerge`, `resmi_yazi` ↔ `talep_yazisi`/`gorus_sorma`) `Gemma 4 12B`'nin `16.78` Macro-F1 puanı gerisinde kalmıştır.
