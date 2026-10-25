# Deney E3 — Mevzuat RAG Alt Sistemi: Geri Getirme, Kaynak İzlenebilirliği ve Çekimser Kalma

**Kapsam:** FAZ 6A (`MAKALE_HAZIRLIK_PLANI.md` §3.3, §5.1)  
**Korpus:** `app/data/rag/chunks.json` (3.056 parça), `app/data/scraped/documents.json` (956 belge)  
**Sorgu seti:** `data/eval/rag/queries_and_qrels.json` (48 cevaplanabilir + 12 cevaplanamaz) — **otomatik etiketli gümüş standart**, bkz. `data/eval/rag/README_rag_eval.md`  
**Durum:** Bu sonuçlar, S2 üretim düzeltmeleri (Türkçe-duyarlı tokenizasyon, başlık türetme, kaynak izlenebilirliği alanları) **uygulandıktan ve indeks yeniden üretildikten sonra** yeniden koşulan E3'e aittir. Dolayısıyla R1 (üretim) artık Türkçe `İ` düzeltmesini içerir.

> [!WARNING]
> **Bölüm 2'deki geri getirme metrikleri insan etiketine dayanmaz.** Alaka etiketleri, R3–R6'nın da kullandığı başlık yayılımlı korpus üzerinde sözcüksel eşleşmeyle otomatik üretilmiştir (döngüsellik riski). Dosyadaki `κ = 0.9935` iki otomatik kural arasındadır ve değerlendiriciler arası uyum olarak raporlanamaz. Bu sayılar makalede **yalnızca uzman etiketlemesiyle yeniden hesaplandıktan sonra** kullanılmalıdır. Bölüm 1 (indeks denetimi) bu sorundan etkilenmez.

---

## 1. İndeks hijyeni ve kaynak izlenebilirliği denetimi (`results/e3/provenance_audit.json`)

| Bulgu | Değer |
|---|---:|
| Jenerik `"PDF Görüntüle"` başlıklı parça | **0 / 3.056** *(düzeltme öncesi: 1.279; içerikten başlık türetiliyor)* |
| Menü/navigasyon artığı olarak işaretlenen parça | 53 |
| Birebir MD5 kopya grubu / fazladan kopya parça | 44 / 54 |
| Alfabetik oranı < 0,50 (bozuk PDF kodlaması şüphesi) | 243 (%7,95) |
| Kazımada 50.000 karakterde kesilmiş belge | 148 / 956 |
| `documents.json` içinde `date` / `url` bulunan belge | 909 / 956 (%95,1) |
| Parçada `indexed_at` alanı | **3.056 / 3.056** |
| Parçada `source_url` / `publish_date` (belge düzeyinden aktarıldı) | **909 / 956 belge kaynaklı** |
| Parçada `law_no` (regex) | 1.304 (%42,7) |
| Parçada `article_refs` (`Madde N` regex) | 2.196 (%71,9) |

> **Not:** `provenance_audit.json` içindeki `chunks_with_date_field` / `chunks_with_url_field` sayaçları eski `date`/`url` anahtar adlarını arar (bu nedenle 0); güncel kaynak alanları `source_url` / `publish_date` adlarıyla tutulur ve `attribution_fields_status` bölümünde doğru raporlanır.

**Gözlemler:**
1. **Başlık çakışması → DÜZELTİLDİ:** Yüzlerce farklı PDF aynı `"PDF Görüntüle"` başlığını taşıyordu; `search`/`search_multi` başlık tabanlı bastırma/tekilleştirme yaptığından farklı belgelerin parçaları birbirini eziyordu. `scripts/build_index.py` artık içeriğin ilk anlamlı satırından başlık türetir (jenerik başlık sayısı 1.279 → 0) ve `search_multi` kararlı `chunk_id` ile tekilleştirir.
2. **Türkçe `İ` tokenizasyon hatası → DÜZELTİLDİ:** Eski üretim vektörleyicisi (`lowercase=True`) `"İDARİ İHALE İLAN İŞ İL YARGILAMA"` → `['dari','hale','lan','yargilama']` üretiyordu (Python `str.lower()` `İ`'yi `i + U+0307`'ye çevirir; `İŞ`/`İL` düşer; `I`→`i`). `app/core/text_normalize.turkish_lower` preprocessor'ı + `lowercase=False` ile artık `['idari','ihale','ilan','iş','il','yargılama']` üretilir. Düzeltme hem indeks hem sorgu tarafında geçerlidir (preprocessor pickle ile taşınır).
3. **Kaynak meta verisi → DÜZELTİLDİ (§5.1):** `build_index.py` artık her parçaya `source_url`, `publish_date`, `indexed_at`, `chunk_id`, `law_no`, `article_refs`, `content_md5` alanlarını ekler; `RAGService` bunları sonuçta döndürür ve `LegislationAgent` RAG bağlamına (kaynak/kanun no/yayım tarihi/URL) yazar. Böylece bir retrieval sonucu kaynağına izlenebilir.

**Kalan sınırlılık:** Mevzuatın yürürlük/mülga durumunun **dinamik** denetimi hâlâ yapılmaz; `publish_date` yalnızca yayım tarihidir, güncel hukuki geçerlilik garantisi değildir (makalede sınırlılık olarak belirtilmelidir).

---

## 2. Geri getirme karşılaştırması (48 cevaplanabilir sorgu, otomatik qrels)

`results/e3/retrieval_metrics.json` (nokta tahminleri; %95 bootstrap GA'leri ve eşleştirilmiş farklar aynı dosyadadır). Δ ve $p$: R1'e karşı 2.000 tekrarlı eşleştirilmiş bootstrap farkı; $p = \min(1, 2\min(P(\Delta\ge0), P(\Delta\le0)))$ (permütasyon testi değildir).

| Kod | Yöntem | Recall@5 | Recall@10 | Hit@5 | Hit@10 | MRR@10 | nDCG@10 | Dup@10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| R1 | Üretim TF-IDF (`RAGService` — artık Türkçe-düzeltmeli) | 0,4655 | 0,6311 | 0,8958 | 0,9583 | 0,7664 | 0,6129 | 0,0417 |
| R2 | TF-IDF + MD5 tekilleştirme | 0,4708 | 0,6311 | 0,8958 | 0,9583 | 0,7664 | 0,6207 | 0 |
| R3 | TF-IDF + başlık/kanun no yayılımı | 0,4771 | 0,6688 | 0,8958 | 0,9375 | 0,7943 | 0,6661 | 0 |
| R4 | BM25 ($k_1=1{,}5$, $b=0{,}75$) + ön işleme | 0,5865 | 0,7195 | 0,9583 | 0,9792 | 0,9095 | 0,7456 | 0 |
| R5 | R4 + Türkçe ek budama (önek belirteçleri) | **0,6032** | 0,7180 | 0,9583 | 0,9792 | 0,8910 | **0,7503** | 0 |
| R6 | Hibrit RRF (R3 + R4) | 0,4709 | 0,6355 | 0,8958 | 0,9375 | 0,8377 | 0,6682 | 0 |

**R1'e göre farklar (Δ, %95 GA, $p$):**

| Kod | ΔRecall@5 ($p$) | ΔMRR@10 ($p$) | ΔnDCG@10 [%95 GA] ($p$) |
|---|---:|---:|---:|
| R2 | +0,0052 (0,741) | 0,0000 (1,000) | +0,0078 [0,002–0,015] (0,010) |
| R3 | +0,0116 (0,535) | +0,0279 (0,267) | +0,0532 [0,022–0,088] (<0,001) |
| R4 | +0,1209 (0,003) | +0,1431 (<0,001) | +0,1327 [0,071–0,209] (<0,001) |
| R5 | +0,1376 (0,001) | +0,1246 (0,010) | +0,1374 [0,078–0,210] (<0,001) |
| R6 | +0,0054 (0,857) | +0,0713 (0,103) | +0,0553 [−0,012–0,117] (0,096) |

**Yorum (koşullu):** Türkçe `İ` düzeltmesi artık **üretimde (R1)** olduğundan, eski koşuda görünen "Türkçe küçük harf" kazancı taban çizgisine dâhil oldu: R2 ve R3'ün R1'e göre Recall@5/MRR farkları artık küçük ve çoğunlukla istatistiksel olarak anlamsızdır (R3 ΔMRR@10 $p=0{,}267$). **Kalan anlamlı iyileştirme BM25 sıralamasından gelir:** R4 ve R5, R1'e göre Recall@5'i ~+0,12–0,14, MRR@10'u ~+0,12–0,14 ve nDCG@10'u ~+0,13 artırır ($p\le0{,}01$). Hibrit RRF (R6) tutarlı bir kazanç sağlamaz. Yine de qrels'in sözcüksel/otomatik üretilmiş olması R3–R6 lehine yanlılık taşıyabilir; bu farklar insan etiketiyle doğrulanmadan "%X iyileştirir" biçiminde kesin raporlanmamalıdır.

**Ölçüm notları:**
- Gecikme artık `time.perf_counter()` ile ölçülür (düzeltildi): belge başına ortalama ~0,16 ms (R1) – ~0,76 ms (R6, hibrit). Değerler yine de alt-milisaniye düzeyinde olduğundan tek-sorgu gecikmesi ana bulgu olarak sunulmamalıdır.
- Eşleştirilmiş bootstrap $p$ değeri artık `min(1, 2·min(...))` ile sınırlandırılmıştır (düzeltildi); R2 MRR@10 için tüm farklar sıfır olduğundan $p=1{,}000$ (tanımsız/fark yok).

---

## 3. Cevaplanamaz sorgular ve kanıta dayalı çekimser kalma (`results/e3/unsupported_behavior.json`)

### 3.1. Skor eşiği
- Üretimdeki `MIN_SCORE = 0,05` eşiğinde 12 cevaplanamaz sorgunun **12'si** (%100) en az bir parça döndürür (yanlış pozitif oranı 1,0).
- top-1 skoruna göre en iyi Youden eşiği: R1 için $\tau^*=0{,}182$, $J=0{,}292$; R3 için $\tau^*=0{,}187$, $J=0{,}375$; genel $\tau^*=0{,}14$. Yalnızca sözcüksel benzerlik skoruyla cevaplanabilir/cevaplanamaz ayrımı zayıftır.

### 3.2. LLM davranışı (`gemma4:12b`, 8 cevaplanabilir + 8 cevaplanamaz sorgu)

| İstem | Cevaplanabilirde yanıt döndürme | Cevaplanamazda çekimser kalma | Cevaplanamazda eşleşme uydurma |
|---|---:|---:|---:|
| Kısıtsız (üretim `LegislationAgent` istemine benzer) | 7/8 (0,875) | 5/8 | 3/8 (0,375) |
| Kanıta dayalı çekimser kalma istemi | **0/8 (0,000)** | **8/8 (1,000)** | **0/8 (0,000)** |

**Bulgu ve sınırlılıklar:** Kanıta dayalı istem, cevaplanamaz sorgularda halüsinasyonu tamamen ortadan kaldırır (0/8) **ancak aşırı çekimser kalır**: cevaplanabilir 8 sorgunun da tamamında yanıt vermez (0/8). Yani bu istem, halüsinasyonu sıfırlarken cevaplanabilir sorulardaki faydayı da yok eder — pratikte kullanılabilir bir denge için eşik/istem ayarı gerekir. Örneklem çok küçüktür (her kolda $n=8$; 0/8 ve 8/8 için Wilson %95 GA'leri geniştir). Çekimser kalma istemi $\tau^*=0{,}14$ altındaki skorlar için sert bir eşik içerir; BM25 ham skoru ile TF-IDF kosinüs eşiği aynı ölçekte olmadığından bu eşik aşırı çekimserliğin bir nedeni olabilir. Döndürülen mevzuatın doğruluğu ayrıca puanlanmamıştır.

---

## 4. Makale için sonuç

- **Doğrudan raporlanabilir:** Bölüm 1 (indeks denetimi ve uygulanan düzeltmeler: başlık türetme, Türkçe tokenizasyon, kaynak izlenebilirliği) ve Bölüm 3.1 (sabit `MIN_SCORE` eşiğinin cevaplanamaz sorguları ayırmada yetersizliği).
- **Ön bulgu olarak, sınırlılıkla birlikte:** Bölüm 2'de BM25'in (R4/R5) üretim TF-IDF'e (R1) göre anlamlı sıralama kazancı; Bölüm 3.2'de kanıta dayalı istemin halüsinasyonu sıfırlarken aşırı çekimser kalması (küçük örneklem).
- **Uzman etiketlemesi olmadan kesin raporlanmamalı:** Bölüm 2'deki mutlak değerler ve yöntem farkları (otomatik qrels döngüselliği).
