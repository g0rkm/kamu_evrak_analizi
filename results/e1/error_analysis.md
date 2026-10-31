# E1 Deneyi: 18 Sınıflı Kamu Evrakı Sınıflandırma Sonuçları ve Hata Analizi (Faz 4)

> **Deney Künyesi:**
> - **Betik:** `experiments/e1_classification.py` (`python -m experiments.e1_classification --split test`)
> - **Girdi Kümesi:** `data/eval/classification/test.json` (`n = 252` belge, 18 sınıf × 14 test örneği; `seed = 42` ile `dev.json` kümesinden ayrılmış kör test kümesi, SHA-256: `dedb35835d466c2128bf08e6b8fb54b7f758f3dd8ade52731e68e141e0c88315`)
> - **Model ve Parametreler:** `gemma4:12b` (`Q4_K_M`, Ollama `v0.40.8`, `temperature = 0.3`, `num_ctx = 16384`, `max_input_chars = 3000`, `reasoning_effort = "none"`)
> - **Donanım:** NVIDIA GeForce RTX 5070 (12 GB GDDR7 VRAM) · AMD Ryzen 7 7700X · 16 GB DDR5 RAM

---

## 1. Genel Performans Özeti ve Güven Aralıkları

| Metrik | Değer | %95 Bootstrap GA (`B=2000`, `seed=42`) | %95 Wilson Skor GA | Açıklama |
|---|---:|---:|---:|---|
| **Genel Doğruluk (Accuracy / Micro-F1)** | **0.9048** (`228 / 252`) | `[0.8690, 0.9405]` | `[0.8622, 0.9352]` | 18 sınıfın tamamında tam eşleşme oranı |
| **Macro-F1** | **0.8979** | `[0.8598, 0.9294]` | — | 18 sınıfın eşit ağırlıklı F1 ortalaması |
| **Macro-Precision** | **0.9127** | — | — | 18 sınıfın eşit ağırlıklı kesinlik ortalaması |
| **Macro-Recall** | **0.9048** | — | — | 18 sınıfın eşit ağırlıklı duyarlılık ortalaması |
| **Weighted-F1** | **0.8979** | `[0.8579, 0.9370]` | — | Dengeli test kümesinde (`n=14`/sınıf) Macro-F1 ile özdeş |
| **Sınır Toleranslı Doğruluk (Boundary-Tolerant)** | **0.9286** (`234 / 252`) | — | `[0.8900, 0.9543]` | İkincil aday (`secondary_candidates`) eşleşmelerini kapsayan oran |
| **Ortalama Tekil Yanıt Süresi (Latency)** | **1194.25 ms** | — | — | Medyan: `1115.05 ms`, P95: `1719.90 ms`, Toplam: `300.95 sn` |

### 6 Sınıflı Pilot (`n=54`) ile 18 Sınıflı Tam Değerlendirme (`n=252`) Karşılaştırması
- **Pilot Ölçüm (`n=54`, 6 mevzuat sınıfı):** `Macro-F1 = 0.935`, `Accuracy = 0.926` (`50/54`).
- **Tam Değerlendirme (`n=252`, 18 sınıf):** `Macro-F1 = 0.8979` (`%95 GA: 0.8598–0.9294`), `Accuracy = 0.9048` (`228/252`).
- **Temel Bulgu:** Değerlendirme kapsamı 6 mevzuat türünden 18 sınıfa (özellikle birbirine yakın idari yazışma alt türleri ile `karar` ↔ `kararname` sınır örneklerine) genişletildiğinde Macro-F1 skorunda **3.71 puanlık (`0.935 → 0.898`)** beklenen ve istatistiksel olarak anlamlı bir daralma gözlenmiştir.

---

## 2. Sınıf Bazlı Performans Tablosu (18 Sınıf, `n=14` / sınıf)

| # | Sınıf Kodu | Sınıf Etiketi | Precision | Recall | F1-Score | %95 Bootstrap F1 GA | TP | FP | FN | Destek |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `dilekce` | Dilekçe | 1.0000 | 1.0000 | **1.0000** | `[1.0000, 1.0000]` | 14 | 0 | 0 | 14 |
| 2 | `sikayet` | Şikâyet | 1.0000 | 1.0000 | **1.0000** | `[1.0000, 1.0000]` | 14 | 0 | 0 | 14 |
| 3 | `rapor` | Rapor | 1.0000 | 1.0000 | **1.0000** | `[1.0000, 1.0000]` | 14 | 0 | 0 | 14 |
| 4 | `tutanak` | Tutanak | 1.0000 | 1.0000 | **1.0000** | `[1.0000, 1.0000]` | 14 | 0 | 0 | 14 |
| 5 | `kanun` | Kanun | 1.0000 | 1.0000 | **1.0000** | `[1.0000, 1.0000]` | 14 | 0 | 0 | 14 |
| 6 | `sozlesme` | Sözleşme | 1.0000 | 1.0000 | **1.0000** | `[1.0000, 1.0000]` | 14 | 0 | 0 | 14 |
| 7 | `ilan` | İlan | 0.9333 | 1.0000 | **0.9655** | `[0.8750, 1.0000]` | 14 | 1 | 0 | 14 |
| 8 | `genelge` | Genelge | 1.0000 | 0.9286 | **0.9630** | `[0.8571, 1.0000]` | 13 | 0 | 1 | 14 |
| 9 | `talep_yazisi` | Talep Yazısı | 0.8750 | 1.0000 | **0.9333** | `[0.8235, 1.0000]` | 14 | 2 | 0 | 14 |
| 10 | `yonetmelik` | Yönetmelik | 0.8750 | 1.0000 | **0.9333** | `[0.8204, 1.0000]` | 14 | 2 | 0 | 14 |
| 11 | `yonerge` | Yönerge | 0.8750 | 1.0000 | **0.9333** | `[0.8182, 1.0000]` | 14 | 2 | 0 | 14 |
| 12 | `teblig` | Tebliğ | 0.9286 | 0.9286 | **0.9286** | `[0.8000, 1.0000]` | 13 | 1 | 1 | 14 |
| 13 | `gorus_sorma` | Görüş Sorma | 1.0000 | 0.8571 | **0.9231** | `[0.7778, 1.0000]` | 12 | 0 | 2 | 14 |
| 14 | `resmi_yazi` | Resmî Yazı | 0.7778 | 1.0000 | **0.8750** | `[0.7200, 0.9744]` | 14 | 4 | 0 | 14 |
| 15 | `kurum_ici` | Kurum İçi Yazışma | 1.0000 | 0.7143 | **0.8333** | `[0.6363, 0.9697]` | 10 | 0 | 4 | 14 |
| 16 | `bilgilendirme` | Bilgilendirme Yazısı | 0.7857 | 0.7857 | **0.7857** | `[0.5714, 0.9333]` | 11 | 3 | 3 | 14 |
| 17 | `kararname` | Kararname | 0.5789 | 0.7857 | **0.6667** | `[0.4284, 0.8333]` | 11 | 8 | 3 | 14 |
| 18 | `karar` | Karar | 0.8000 | 0.2857 | **0.4211** | `[0.1111, 0.6667]` | 4 | 1 | 10 | 14 |

---

## 3. Alt Grup (Subgroup) Analizi

| Alt Grup Boyutu | Alt Grup | Örnek Sayısı (`n`) | Doğruluk (Accuracy) | Macro-F1 |
|---|---|---:|---:|---:|
| **Veri Kaynağı (`origin_type`)** | `scraped_official` (Resmî Gazete / Mevzuat) | 78 | 0.8590 | 0.8341 |
| **Veri Kaynağı (`origin_type`)** | `curated_anonymized` (Kurumsal Anonim Şablon) | 174 | 0.9253 | 0.9298 |
| **Belge Uzunluğu (`length_bucket`)** | `kisa` (`< 1.000` karakter) | 196 | 0.9082 | 0.8692 |
| **Belge Uzunluğu (`length_bucket`)** | `orta` (`1.000 – 5.000` karakter) | 24 | 0.7917 | 0.8106 |
| **Belge Uzunluğu (`length_bucket`)** | `uzun` (`> 5.000` karakter, `3.000` kar. kırpma) | 32 | 0.9688 | 0.7778 |

---

## 4. Hata Analizi: En Sık Karışan Sınıf Çiftleri ve Kök Nedenler

Toplam `252` test örneğinde `24` hata (`%9.52`) gözlenmiştir. Bu hataların tamamı 3 yapısal kümede toplanmaktadır:

| Sıra | Gerçek Sınıf (`GT`) | Tahmin (`Pred`) | Hata Sayısı | Toplam Hatadaki Payı | Yapısal / Dilbilimsel Kök Neden |
|---|---|---|---:|---:|---|
| 1 | `karar` | `kararname` | **8** | %33.3 | **Cumhurbaşkanı Kararı ↔ Cumhurbaşkanlığı Kararnamesi Geçişkenliği:** `ClassifierAgent` sıfır-örnekli (zero-shot) isteminde `taxonomy.py` içindeki kısa açıklama (`"Karar, kurul kararı, Cumhurbaşkanlığı kararı"` vs `"Cumhurbaşkanlığı kararnamesi veya KHK"`) yer almaktadır. Model, `"CUMHURBAŞKANI KARARI (Karar Sayısı: 8459, 8810, 11388 vb.)"` başlıklı birel/yürütme kararlarını Cumhurbaşkanı imzası taşıdığı için `kararname` olarak kodlamıştır. |
| 2 | `bilgilendirme` | `resmi_yazi` | **3** | %12.5 | **Üst Yazı Zarfı Baskınlığı:** Kurumlar arası gönderilen ve `Sayı:`, `Konu:` ile başlayıp `"Bilgilerinize arz ederim"` ile biten sınır örneklerinde model, içerikteki salt bilgilendirme işlevi yerine resmî üst yazı biçimine öncelik vermiştir. |
| 3 | `kurum_ici` | `bilgilendirme` | **3** | %12.5 | **İç Duyuru / Rehber Paylaşımı Kesişimi:** Aynı kurum içindeki birimlere gönderilen telefon rehberi, masaüstü ekran kilidi hatırlatması ve malzeme dağıtım listesi örneklerinde model, belgenin kurum içi yönünü değil bilgilendirme işlevini birincil etiket seçmiştir. |
| 4 | `gorus_sorma` | `talep_yazisi` | **2** | %8.3 | **Örtük Görüş İstemleri (`hard=True`):** Konu satırında açıkça `"Görüş"` kelimesi geçmeyen ve `"değerlendirilerek Başkanlığımıza bildirilmesini arz ederim"` şeklinde biten iki sınır örneği genel talep yazısı (`talep_yazisi`) olarak sınıflandırılmıştır. |
| 5 | `kararname` | `yonetmelik` | **2** | %8.3 | **Madde Yapılı Teşkilat Düzenlemeleri (`hard=True`):** Başlığında açık `"Kararname"` ibaresi yerine `"Düzenlemesi"` geçen ve `MADDE 1 –` yapısıyla teşkilat/atama kurallarını düzenleyen iki sınır örneği `yonetmelik` olarak tahmin edilmiştir. |
| 6 | `kurum_ici` | `yonerge` | **1** | %4.2 | `"Birim Arşivi Ayıklama ve İmha Hazırlık Çalışması İç Talimatı"` başlıklı iç yazışma, kural sıralaması içerdiğinden `yonerge` olarak kodlanmıştır. |
| 7 | `genelge` | `resmi_yazi` | **1** | %4.2 | Metin gövdesinde açık `"GENELGE"` başlığı bulunmayan `"Kurban Hizmetlerinin Yürütülmesi... (2026/13)"` sınır örneği `resmi_yazi` olarak tahmin edilmiştir. |
| 8 | `teblig` | `yonerge` | **1** | %4.2 | `"Hukuk Muhakemeleri Kanunu Gider Avansı Tarifesi"` (`scraped_official`), başlığında `"Tebliğ"` kelimesi bulunmadığı ve maddeler halinde uygulama esasları içerdiği için `yonerge` olarak sınıflandırılmıştır. |
| 9 | `karar` | `teblig` | **1** | %4.2 | Resmî Gazete'de `TEBLİĞLER` üst bölüm başlığı altında yayımlanan `Özelleştirme İdaresi Başkanlığının 2025/ÖİB-K-19 Sayılı Kararı`, üst bölüm başlığı nedeniyle `teblig` olarak sınıflandırılmıştır. |
| 10 | `karar` | `ilan` | **1** | %4.2 | Resmî Gazete'de yayımlanan kısa `DÜZELTME` metni (`Sender Ödeme Hizmetleri A.Ş. Kararı ile İlgili`), duyuru formatı nedeniyle `ilan` olarak sınıflandırılmıştır. |

---

## 5. Temsilî Hata Örnekleri ve Model Gerekçeleri (`reasoning`)

1. **`eval_karar_003` (`GT: karar` → `Pred: kararname`, Güven: `1.00`, `scraped_official`):**
   - *Başlık:* `–– Birleşmiş Milletler Güvenlik Konseyinin 1267 (1999)... Sayılı Kararlarıyla Listelenen Kişi, Kuruluş veya Organizasyonların Tasarrufunda Bulunan Malvarlığının Dondurulması Hakkındaki... Karar (Karar Sayısı: 11388)`
   - *Model Gerekçesi:* `"Metin açıkça 'CUMHURBAŞKANI KARARI' başlığını taşımakta olup, Cumhurbaşkanı tarafından imzalanmış, Resmi Gazete'de yayımlanmış ve belirli bir listeye ilişkin hukuki değişiklikleri içeren bir kararname niteliğindedir."`
   - *Analiz:* Model, 2018 sonrası Türk idare hukukundaki **Cumhurbaşkanı Kararı** (`Karar Sayısı: 11388` — birel/idari işlem) ile **Cumhurbaşkanlığı Kararnamesi** (`Kararname Numarası: 1..173` — asli/düzenleyici norm) ayrımını kısa taksonomi açıklamasından çıkaramamıştır. `karar` ve `kararname` dışındaki 16 sınıfta ortalama F1 skoru **`0.9462`** düzeyindedir.

2. **`eval_bilgilendirme_017` (`GT: bilgilendirme` → `Pred: resmi_yazi`, Güven: `0.95`, `is_boundary_match: True`):**
   - *Başlık:* `Konu: Ulusal Coğrafi Bilgi Platformu Veri Katmanı Güncellemesi`
   - *Model Gerekçesi:* `"Metin, bir kurumun (Genel Müdürlük) başka bir kuruma (Gazi Üniversitesi Rektörlüğü) gönderdiği, resmi sayı ve konu başlığı içeren, bilgi aktarımı amaçlı bir üst yazıdır."`
   - *Analiz:* Model yazının `"bilgi aktarımı amaçlı"` olduğunu kendi gerekçesinde doğru tespit etmiş, ancak üst kategori olan `resmi_yazi` etiketini seçmiştir.

3. **`eval_teblig_008` (`GT: teblig` → `Pred: yonerge`, Güven: `0.95`, `scraped_official`):**
   - *Başlık:* `–– Hukuk Muhakemeleri Kanunu Gider Avansı Tarifesi`
   - *Model Gerekçesi:* `"Metin, Hukuk Muhakemeleri Kanunu kapsamında gider avansının miktarı, ödenmesi ve iadesine ilişkin usul ve esasları belirleyen bir tarife belgesidir. Maddeler halinde düzenlenmiş usul ve esasları içerdiği için 'yonerge' kategorisine uygundur."`
   - *Analiz:* Bakanlıklarca Resmî Gazete'de yayımlanan yıllık ücret/gider tarifeleri başlıklarında `"Tebliğ"` kelimesi geçmediğinde model tarafından `yonerge` ile karıştırılabilmektedir.
