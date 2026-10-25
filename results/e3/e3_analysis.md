# Deney E3 — Mevzuat RAG Alt Sistemi Değerlendirme ve Kaynak İzlenebilirliği (Provenance) Analiz Raporu

**Tarih:** 2026-10-25  
**Kapsam:** FAZ 6A — Deney E3 (`MAKALE_HAZIRLIK_PLANI.md` §3.3, §5.1)  
**Veri Kümesi:** `app/data/rag/chunks.json` ($N=3.056$ parça / `956` kazınmış belge), `data/eval/rag/queries_and_qrels.json` ($Q=60$ sorgu: $48$ cevaplanabilir + $12$ kapsam dışı; $\text{Cohen's }\kappa = 0.9863$)

---

## 1. İndeks Hijyeni ve Kaynak İzlenebilirliği (Provenance) Denetimi Bulguları (§5.1)

`results/e3/provenance_audit.json` üzerinde yürütülen tam indeks denetimi, mevcut üretim RAG indeksinde (`app/data/rag/chunks.json` ve `app/data/rag/tfidf.pkl`) hem arama isabetini hem de hukuki izlenebilirliği doğrudan etkileyen **5 yapısal bulgu** ortaya koymuştur:

### 1.1. Jenerik Başlık Çakışması (`"PDF Görüntüle"`) ve Tekilleştirme Hatası
- `3.056` parçanın **`1.279`'u (`%41,85`)** kazıma sırasında PDF görüntüleyici pencere başlığı olan `"PDF Görüntüle"` başlığıyla indekslenmiştir.
- Üretimdeki `RAGService.search` (`app/services/rag_service.py`) aynı `title` değerine sahip parçaları `max_per_title = max(1, top_k // 2)` (`top_k=5` için en fazla `2` parça) ile sınırlandırmaktadır. Bu durum, `"PDF Görüntüle"` başlıklı yüzlerce farklı Resmi Gazete PDF'inden yalnızca ilk 2 tanesinin sonuç listesine girmesine, geri kalan tüm PDF mevzuat parçalarının yanlışlıkla bastırılmasına yol açmaktadır.
- Ayrıca `RAGService.search_multi` fonksiyonu tekilleştirme anahtarı olarak `(hit.title, hit.chunk_index)` çiftini kullandığından, farklı PDF belgelerinin aynı indeksli parçaları (`("PDF Görüntüle", 0)`) birbirinin üzerine yazılmaktadır.

### 1.2. Mükerrer Parçalar, Menü Artıkları ve Bozuk PDF Karakter Kodlaması (CMap)
- **Tam İçerik Tekrarı (MD5):** İndekste `44` mükerrer içerik grubunda toplam **`54` fazladan kopya parça** (`3.002` tekil MD5) bulunmaktadır. Özellikle **5018, 4734, 3071 ve 2577 sayılı temel kanunlar** hem `mevzuat_gov_tr` hem de `kanun` kategorisi altında ikişer kez indekslenmiştir.
- **Menü Artıkları:** `"T.C. CUMHURBAŞKANLIĞI"` başlıklı `6` parça gerçek mevzuat metni değil, web sayfası üst menü/navigasyon kalıntısıdır.
- **Bozuk PDF CMap Kodlaması:** `243` parçada (`%7,95`) alfabetik karakter oranı `< 0.50` olup, bozuk font tablosu nedeniyle okunamaz karakter dizileri yer almaktadır.
- **50.000 Karakter Kesmesi (Truncation):** `app/data/scraped/documents.json` içindeki `956` belgenin **`148`'i** (`mevzuat_gov_tr` kategorisindeki `47` ana kanunun `28`'i dahil) kazıma aşamasında tam `50.000` karakterde kesilmiştir. Bu nedenle uzun kanunların (örn. 657 sayılı DMK, 4734 sayılı KİK, 5018 sayılı KMYKK) ilerleyen maddeleri indekste yer almamaktadır.

### 1.3. Python Varsayılan `.lower()` Kaynaklı Türkçe `İ`/`I` Tokenizasyon Hatası
- `scripts/build_index.py` içinde oluşturulan `TfidfVectorizer`, Python'un standart `.lower()` dönüşümünü ve `(?u)\b\w\w+\b` kelime bölme regex'ini kullanmaktadır.
- Unicode standardında büyük `İ` (`U+0130`) karakteri `.lower()` uygulandığında `i` + `U+0307` (combining dot above) dizisine dönüşmekte; `\w` regex'i `U+0307` birleştirici nokta karakterinde kelimeyi bölmektedir:
  - `"İDARİ"` $\to$ `"dari"` (`i` tek harf kaldığı için atılır!)
  - `"İHALE"` $\to$ `"hale"`
  - `"İLAN"` $\to$ `"lan"`
  - `"İŞ"` ve `"İL"` $\to$ tamamen silinir (2 karakter altı kaldığı için)!
- Benzer şekilde büyük `"I"` karakteri `"ı"` yerine `"i"` harfine dönüşmekte (`"YARGILAMA"` $\to$ `"yargilama"` $\neq$ `"yargılama"`), şapkalı harfler (`"kâr"`, `"hükûmet"`, `"mülkî"`) ise şapkasız sorgularla eşleşmemektedir.

### 1.4. Kaynak İzlenebilirliği (Provenance) Meta Veri Kaybı ve Şema İyileştirme Planı
Aşağıdaki tablo, kazınmış ham veri (`documents.json`), mevcut üretim indeksi (`chunks.json`) ve önerilen zenginleştirilmiş şema arasındaki farkı göstermektedir:

| Meta Veri Alanı | `documents.json` ($N=956$) | Mevcut `chunks.json` ($N=3.056$) | Metinden Regex ile Kurtarılabilirlik | Önerilen `chunks_v2` Şeması |
|---|---:|---:|---:|---|
| `chunk_id` (Kararlı Kimlik) | Yok | **Yok (`%0`)** (liste sırasına bağımlı) | `%100` (`doc_id` + `chunk_index` + `md5[:8]`) | Zorunlu alan (`str`) |
| `title` (Anlamlı Başlık) | `%58,1` anlamlı | `%58,1` anlamlı (`%41,85` `"PDF Görüntüle"`) | **`%99,6`** (`3.044/3.056` ilk satır/başlık yayılımı ile) | Zorunlu alan (temizlenmiş başlık) |
| `category` (Mevzuat Türü) | `%100,0` | `%100,0` | `%100,0` | Zorunlu alan (`kanun`, `cbk`, `yonetmelik` vb.) |
| `source_url` (Resmi Kaynak URL) | **`%95,1`** (`909/956`) | **Yok (`%0`)** (`build_index.py` düşürüyor) | `documents.json` birleştirmesi ile `%95,1` | Zorunlu alan (`url`) |
| `publish_date` (Yayım Tarihi) | **`%95,1`** (`909/956`) | **Yok (`%0`)** (`build_index.py` düşürüyor) | `documents.json` + metin içi tarih ile `%96,4` | Zorunlu alan (`ISO-8601 date`) |
| `law_or_cbk_no` (Kanun/CBK No) | Yok | **Yok (`%0`)** | **`%42,7`** (`1.304/3.056` parçada açık numara) | Belge düzeyinden miralanan alan |
| `article_no` (`Madde X`) | Yok | **Yok (`%0`)** | **`%71,9`** (`2.196/3.056` parçada açık madde no) | Parça düzeyinde çıkarılan liste (`["Madde 4", ...]`) |
| `content_md5` (Tekilleştirme Özeti) | Yok | **Yok (`%0`)** | `%100,0` | İndeksleme anında tekilleştirme anahtarı |

---

## 2. Geri Getirme (Retrieval) Yöntemleri Karşılaştırması ($Q_{\text{ans}} = 48$)

Altı geri getirme konfigürasyonu aynı `48` cevaplanabilir sorgu üzerinde `Recall@3/5/10`, `HitRate@5/10`, `MRR@10`, dereceli `nDCG@10` (`2000` tekrarlı eşleştirilmiş bootstrap `%95 GA` ve `R1` üretim baz çizgisine karşı iki yönlü eşleştirilmiş permütasyon testi $p$-değeri ile) değerlendirilmiştir (`results/e3/retrieval_comparison.csv`):

| Kod | Yöntem Tanımı | Recall@3 | Recall@5 [%95 GA] | Recall@10 | HitRate@5 | MRR@10 [%95 GA] | nDCG@10 [%95 GA] | $\Delta\text{nDCG@10}$ ($p$) | Dup@10 | Gecikme (ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **R1** | `prod_tfidf` (Mevcut Üretim `RAGService`) | 0.3490 | 0.4735 [0.379, 0.575] | 0.6081 | 0.9375 | 0.8142 [0.717, 0.898] | 0.6667 [0.587, 0.745] | Baz çizgisi | %4,38 | **0.09** |
| **R2** | `raw_tfidf_dedup` (MD5 Tekilleştirme, Başlık Bastırmasız) | 0.3490 | 0.4770 [0.382, 0.576] | 0.6194 | 0.9375 | 0.8142 [0.717, 0.898] | 0.6744 [0.594, 0.751] | +0.0077 ($p<0.001$) | **%0,00** | 0.60 |
| **R3** | `tr_tfidf_title` (Türkçe `İ`/`I` Norm. + Başlık/Kanun No Yayılımı) | 0.3694 | 0.4926 [0.402, 0.590] | 0.6637 | 0.9792 | 0.8889 [0.810, 0.955] | 0.7460 [0.678, 0.809] | +0.0793 ($p<0.001$) | %0,00 | 0.89 |
| **R4** | `bm25_tr` (Okapi BM25 $k_1=1.5, b=0.75$ + Türkçe Norm. + Başlık) | 0.4158 | 0.5490 [0.453, 0.646] | 0.7167 | 0.9583 | 0.9201 [0.854, 0.974] | 0.7908 [0.728, 0.848] | +0.1241 ($p<0.001$) | %0,00 | 0.44 |
| **R5** | **`bm25_tr_prefix` (Okapi BM25 + Türkçe Çekim Eki Kökleme)** | **0.4319** | **0.5786 [0.484, 0.674]** | **0.7472** | **0.9792** | **0.9340 [0.868, 0.979]** | **0.8128 [0.750, 0.870]** | **+0.1462 ($p<0.001$)** | **%0,00** | 0.53 |
| **R6** | `hybrid_rrf` (Hibrit RRF: `R3` Karakter/Kelime TF-IDF + `R4` BM25) | 0.3910 | 0.4926 [0.405, 0.588] | 0.7031 | **0.9792** | 0.9329 [0.872, 0.980] | 0.7684 [0.707, 0.827] | +0.1017 ($p=0.001$) | %0,00 | 1.38 |

### Temel Çıkarımlar:
1. **Türkçe Normalizasyon ve Başlık Yayılımının Etkisi (`R1` $\to$ `R3`):** Yalnızca Python `.lower()` kaynaklı `İ`/`I` hatasının giderilmesi (`"İDARİ"` $\to$ `"idari"`, `"İHALE"` $\to$ `"ihale"`) ve belge başındaki kanun numarası/başlığın alt parçalara yayılması bile `MRR@10` değerini `0.8142`'den `0.8889`'a (`+0.0747`, $p=0.011$), `nDCG@10` değerini ise `0.6667`'den `0.7460`'a (`+0.0793`, $p<0.001$) yükseltmektedir.
2. **BM25 ve Sondan Eklemeli (Agglutinative) Kök Норmalizasyonu (`R5`):** Türkçe mevzuat metinlerinde yoğun çekim ekleri (`"ihalesine"`, `"ihalede"`, `"ihalelerin"` $\to$ `"ihale"`) kelime bazlı tam eşleşmeyi düşürmektedir. Türkçe çekim eki budama/kök eşleştirme destekli Okapi BM25 (`R5_bm25_tr_prefix`), üretimdeki `R1` sistemine kıyasla **`Recall@5`'i `%47,35`'ten `%57,86`'ya (`+10,51` puan, $p<0.001$)**, **`MRR@10`'u `0.8142`'den `0.9340`'a (`+11,98` puan, $p=0.004$)** ve **`nDCG@10`'u `0.6667`'den `0.8128`'e (`+14,62` puan, $p<0.001$)** taşımaktadır. Üstelik sorgu başına gecikme yalnızca `0.53 ms` olup harici bir GPU/vektör veritabanı gerektirmemektedir.

---

## 3. Kapsam Dışı Sorgular (Unsupported Queries) ve Kanıta Dayalı Çekimser Kalma (Grounded Abstention)

İndekste karşılığı bulunmayan `12` kapsam dışı sorgu (`Q49`–`Q60`) üzerinde yapılan analiz (`results/e3/unsupported_behavior.json`) iki kritik güvenlik/doğruluk bulgusu sunmaktadır:

### 3.1. Sabit Skor Eşiği (`MIN_SCORE = 0.05`) Yetersizliği
- Üretimdeki `RAGService.MIN_SCORE = 0.05` eşiği altında, `12` kapsam dışı sorgunun **tamamında (`12/12`, `%100` Yanlış Pozitif Geri Getirme Oranı)** en az bir mevzuat parçası eşiği geçerek LLM bağlamına (`__LEGISLATION_DB__`) enjekte edilmektedir (`top-1` skor ortalaması: cevaplanabilir sorgularda `0.3695`, kapsam dışı sorgularda `0.2116`).
- ROC/Youden analizi, salt sözcüksel benzerlik skoru ile kapsam dışı sorguları ayırmanın mümkün olmadığını göstermektedir (`R1` için en iyi eşik $\tau^* = 0.1465$'te bile $\text{Youden's } J = 0.250$; `R3` için $\tau^* = 0.1818$'de $J = 0.396$). Bunun nedeni, kapsam dışı hukuki soruların da (`"kanun"`, `"yönetmelik"`, `"madde"`, `"ceza"`, `"başvuru"`) genel hukuk terminolojisini paylaşmasıdır.

### 3.2. `LegislationAgent` Halüsinasyon Testi (`gemma4:12b`) ve Grounded Abstention Çözümü
Yerel `gemma4:12b` modeli üzerinde `8` cevaplanabilir ve `8` kapsam dışı sorgu ile iki farklı istem (prompt) stratejisi karşılaştırılmıştır:

| İstem (Prompt) Stratejisi | Kapsam İçi Doğru Yanıtlama Oranı ($n=8$) | Kapsam Dışı Çekimser Kalma Doğruluğu (Abstention Accuracy, $n=8$) | Kapsam Dışı Halüsinasyon / Uydurma Mevzuat Oranı ($n=8$) | Ort. Gecikme (ms) |
|---|---:|---:|---:|---:|
| **Mevcut Üretim İstem Şablonu (`Unconstrained LegislationAgent`)** | `%100,0` (`8/8`) | **`%0,0` (`0/8`)** | **`%100,0` (`8/8`)** | 3.743 ms |
| **Kanıta Dayalı Çekimser Kalma İstemi (`Grounded Abstention Prompt`)** | **`%100,0` (`8/8`)** | **`%87,5` (`7/8`)** | **`%12,5` (`1/8`)** | 2.660 ms |

- **Kök Neden:** Mevcut `LegislationAgent` istemi, `__LEGISLATION_DB__` bağlamında ilgili kanun bulunmasa dahi modelden her zaman `relevant_articles` dizisini doldurmasını beklemekte ve açık bir *"yalnızca sağlanan parçalara dayan; parçalarda doğrudan hüküm yoksa `abstention: true` döndür"* kuralı içermemektedir. Sonuç olarak model, kapsam dışı 8 sorunun tamamında (`%100`) ya alakasız bir kanun maddesini soruya zorla uyarlamış ya da kendi parametrik belleğinden gerçekte olmayan kanun/madde numaraları üretmiştir.
- **Çözüm:** Sisteme eklenen **Grounded Abstention (Kanıta Dayalı Çekimser Kalma)** şeması, kapsam içi sorulardaki `%100` yanıt başarısını korurken, kapsam dışı sorularda uydurma mevzuat üretme (halüsinasyon) oranını **`%100,0`'dan `%12,5`'e (`7/8` doğru reddetme)** düşürmüştür.
