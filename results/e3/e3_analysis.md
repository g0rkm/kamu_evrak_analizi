# Deney E3 — Mevzuat RAG Alt Sistemi: Geri Getirme, Kaynak İzlenebilirliği ve Çekimser Kalma

**Kapsam:** FAZ 6A (`MAKALE_HAZIRLIK_PLANI.md` §3.3, §5.1)  
**Korpus:** `app/data/rag/chunks.json` (3.056 parça), `app/data/scraped/documents.json` (956 belge)  
**Sorgu seti:** `data/eval/rag/queries_and_qrels.json` (48 cevaplanabilir + 12 cevaplanamaz) — **otomatik etiketli gümüş standart**, bkz. `data/eval/rag/README_rag_eval.md`

> [!WARNING]
> **Bölüm 2'deki geri getirme metrikleri insan etiketine dayanmaz.** Alaka etiketleri, R3–R6'nın da kullandığı başlık yayılımlı korpus üzerinde sözcüksel eşleşmeyle otomatik üretilmiştir (döngüsellik riski). Dosyadaki `κ = 0.9863` iki otomatik kural arasındadır ve değerlendiriciler arası uyum olarak raporlanamaz. Bu sayılar makalede **yalnızca uzman etiketlemesiyle yeniden hesaplandıktan sonra** kullanılmalıdır. Bölüm 1 (indeks denetimi) bu sorundan etkilenmez.

---

## 1. İndeks hijyeni ve kaynak izlenebilirliği denetimi (`results/e3/provenance_audit.json`)

| Bulgu | Değer |
|---|---:|
| Jenerik `"PDF Görüntüle"` başlıklı parça | 1.279 / 3.056 (%41,85) |
| Menü/navigasyon artığı olarak işaretlenen parça | 53 |
| Birebir MD5 kopya grubu / fazladan kopya parça | 44 / 54 |
| Alfabetik oranı < 0,50 (bozuk PDF kodlaması şüphesi) | 243 (%7,95) |
| Kazımada 50.000 karakterde kesilmiş belge | 148 / 956 |
| `documents.json` içinde `date` / `url` bulunan belge | 909 / 956 (%95,1) |
| `chunks.json` içinde `date` / `url` / `indexed_at` alanı bulunan parça | **0 / 3.056** |
| Metinde `Madde N` kalıbı geçen parça (regex ile kurtarılabilir) | 2.196 (%71,9) |
| Metinde kanun numarası kalıbı geçen parça | 1.304 (%42,7) |

**Gözlemler:**
1. **Başlık çakışması:** `RAGService.search` aynı başlıktan en fazla `max(1, top_k // 2)` parça döndürür; `search_multi` tekilleştirmeyi `(title, chunk_index)` ile yapar. Yüzlerce farklı PDF aynı `"PDF Görüntüle"` başlığını taşıdığından, bu PDF'lerin parçaları birbirini bastırır/ezer.
2. **Türkçe `İ` tokenizasyon hatası (doğrulandı):** Üretim `tfidf.pkl` vektörleyicisi (`lowercase=True`, `token_pattern=(?u)\b\w\w+\b`) `"İDARİ İHALE İLAN İŞ İL YARGILAMA"` girdisini `['dari', 'hale', 'lan', 'yargilama']` olarak ayrıştırır: Python `str.lower()` `İ`'yi `i + U+0307` dizisine çevirir, regex birleştirici noktada keser; `İŞ`/`İL` tamamen düşer; `I` → `i` olur (`yargılama` ile eşleşmez).
3. **Kaynak meta verisi kaybı:** `scripts/build_index.py`, `documents.json` içinde mevcut olan `url` ve `date` alanlarını parçalara aktarmaz; `indexed_at` hiç üretilmez. Dolayısıyla üretim sistemi bir retrieval sonucunda yayım tarihi, kaynak URL'si veya indeksleme tarihi **gösteremez** (§5.1 gereksinimi karşılanmıyor).

**§5.1 için önerilen şema iyileştirmesi (uygulanmadı, plan):** Her parçaya `chunk_id` (kararlı kimlik), `source_url`, `publish_date`, `indexed_at`, `law_no` (belge düzeyinden), `article_refs` (regex) ve `content_md5` alanları eklenmeli; `"PDF Görüntüle"` başlıkları belge ilk satırından türetilen başlıkla değiştirilmeli; `search`/`search_multi` tekilleştirmesi `chunk_id` veya `content_md5` ile yapılmalı. Uygulanmazsa makalede sınırlılık olarak belirtilmelidir.

---

## 2. Geri getirme karşılaştırması (48 cevaplanabilir sorgu, otomatik qrels)

`results/e3/retrieval_metrics.json`. GA: 2.000 tekrarlı bootstrap %95. Δ ve $p$: R1'e karşı eşleştirilmiş bootstrap farkı; $p = 2\min(P(\Delta \ge 0), P(\Delta \le 0))$ (permütasyon testi değildir). 2.000 örneklemin hiçbiri ters işaretli değilse $p<0{,}001$ yazılmıştır.

| Kod | Yöntem | Recall@5 [%95 GA] | Recall@10 | Hit@5 | Hit@10 | MRR@10 [%95 GA] | nDCG@10 [%95 GA] | Dup@10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| R1 | Üretim TF-IDF (`RAGService` davranışı) | 0,4735 [0,379–0,575] | 0,6081 | 0,9375 | 0,9375 | 0,8142 [0,717–0,898] | 0,6667 [0,586–0,745] | 0,0438 |
| R2 | TF-IDF + MD5 tekilleştirme, başlık bastırma yok | 0,4770 [0,382–0,576] | 0,6081 | 0,9375 | 0,9375 | 0,8142 [0,722–0,901] | 0,6744 [0,589–0,752] | 0 |
| R3 | TF-IDF + Türkçe küçük harf + başlık/kanun no yayılımı | 0,4926 [0,404–0,583] | 0,6668 | 0,9792 | 0,9792 | 0,8889 [0,819–0,955] | 0,7460 [0,673–0,814] | 0 |
| R4 | BM25 ($k_1=1{,}5$, $b=0{,}75$) + R3 ön işleme | 0,5490 [0,451–0,647] | 0,7167 | 0,9792 | 0,9792 | 0,9201 [0,851–0,976] | 0,7908 [0,724–0,853] | 0 |
| R5 | R4 + Türkçe ek budama (önek belirteçleri) | **0,5786** [0,484–0,674] | **0,7472** | 0,9792 | 0,9792 | **0,9340** [0,868–0,979] | **0,8128** [0,750–0,870] | 0 |
| R6 | Hibrit RRF (R3 + R4) | 0,4926 [0,401–0,589] | 0,6740 | 0,9792 | **1,0000** | 0,9329 [0,874–0,986] | 0,7684 [0,699–0,833] | 0 |

**R1'e göre farklar:**

| Kod | ΔRecall@5 ($p$) | ΔMRR@10 ($p$) | ΔnDCG@10 [%95 GA] ($p$) |
|---|---:|---:|---:|
| R2 | +0,0035 (0,741) | 0,0000 (tanımsız — tüm farklar sıfır) | +0,0077 [0,002–0,015] (<0,001) |
| R3 | +0,0191 (0,325) | +0,0747 (0,011) | +0,0793 [0,043–0,117] (<0,001) |
| R4 | +0,0755 (0,002) | +0,1059 (0,008) | +0,1241 [0,070–0,180] (<0,001) |
| R5 | +0,1051 (<0,001) | +0,1198 (0,004) | +0,1462 [0,091–0,206] (<0,001) |
| R6 | +0,0191 (0,615) | +0,1186 (0,003) | +0,1017 [0,051–0,154] (0,001) |

**Yorum (koşullu):** Otomatik qrels altında, Türkçe-duyarlı ön işleme ve BM25 sıralama kalitesini (MRR, nDCG) R1'e göre artırmaktadır; R5 tüm metriklerde en yüksek değeri verir. Ancak qrels'in başlık yayılımlı korpus üzerinde sözcüksel olarak üretilmiş olması, R3–R6 lehine sistematik yanlılık yaratabilir. Bu farklar insan etiketiyle doğrulanmadan "R5 üretim sistemini %X iyileştirir" biçiminde raporlanmamalıdır.

**Bilinen ölçüm sınırlılıkları:**
- `experiments/e3_rag_eval.py` eskiden gecikmeyi `time.time()` ile ölçüyordu; Windows'ta çözünürlük ~1 ms olduğundan medyanlar 0, p95 değerleri ~1 ms çıkmıştı. **Betik `time.perf_counter()` kullanacak şekilde düzeltildi** (commit sonrası); `results/e3/*` içindeki mevcut gecikme değerleri eski koşudan kaldığından geçerli gecikme için E3 yeniden üretilmelidir. Yine de alt-milisaniye tek-sorgu gecikmeleri raporlanmamalıdır.
- R2'nin MRR@10 $p$ değeri eski betikte 2,0 çıkıyordu (tüm farklar 0 iken `2·min(...)` üst sınırlandırılmamıştı). **Betikte `min(1.0, 2·min(...))` ile düzeltildi**; `retrieval_metrics.json` içindeki 2,0 değeri yeniden üretilene kadar eski kalır ve tanımsız (p=1,0) kabul edilmelidir.

---

## 3. Cevaplanamaz sorgular ve kanıta dayalı çekimser kalma (`results/e3/unsupported_behavior.json`)

### 3.1. Skor eşiği
- Üretimdeki `MIN_SCORE = 0,05` eşiğinde 12 cevaplanamaz sorgunun **12'si** (%100) en az bir parça döndürür.
- top-1 skoruna göre en iyi Youden eşiği: R1 için $\tau^*=0{,}182$, $J=0{,}250$; R3 için $\tau^*=0{,}182$, $J=0{,}396$. Yalnızca sözcüksel benzerlik skoruyla cevaplanabilir/cevaplanamaz ayrımı zayıftır.

### 3.2. LLM davranışı (`gemma4:12b`, 8 cevaplanabilir + 8 cevaplanamaz sorgu)

| İstem | Cevaplanabilirde eşleşme döndürme | Cevaplanamazda çekimser kalma | Cevaplanamazda eşleşme uydurma |
|---|---:|---:|---:|
| Kısıtsız (üretim `LegislationAgent` istemine benzer) | 8/8 | 0/8 | 8/8 |
| Kanıta dayalı çekimser kalma istemi | 8/8 | 7/8 | 1/8 |

**Sınırlılıklar:** Örneklem çok küçüktür (her kolda $n=8$; 7/8 için Wilson %95 GA ≈ [0,53–0,98]). "Cevaplanabilirde eşleşme döndürme" yalnızca boş olmayan bir `matches` listesi demektir; döndürülen mevzuatın doğruluğu ayrıca puanlanmamıştır. Çekimser kalma istemi ayrıca $\tau^*=0{,}14$ altındaki skorlar için sert bir eşik kuralı içerir (BM25 ham skoru ile TF-IDF kosinüs eşiği aynı ölçekte değildir; bu eşik pratikte etkisiz olabilir). Gecikme ölçülmemiştir.

---

## 4. Makale için sonuç

- **Doğrudan raporlanabilir:** Bölüm 1 (indeks denetimi, `İ` hatası, meta veri kaybı) ve Bölüm 3.1 (sabit eşiğin yetersizliği).
- **Ön bulgu olarak, sınırlılıkla birlikte:** Bölüm 3.2 (küçük örneklem).
- **Uzman etiketlemesi olmadan raporlanmamalı:** Bölüm 2'deki mutlak değerler ve yöntem farkları.
