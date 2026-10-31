# E3 RAG Değerlendirme Kümesi (`queries_and_qrels.json`) — Gümüş Standart (Otomatik Etiketli)

> [!WARNING]
> **Bu küme uzman etiketli bir altın standart (gold standard) DEĞİLDİR.** Alaka etiketleri (`qrels`), `experiments/e3_rag_eval.py::build_or_load_benchmark` içindeki deterministik metin eşleştirme sezgileriyle **otomatik** üretilmiştir. Dosyadaki `cohens_kappa = 0.9863` değeri iki **insan** değerlendirici arasındaki uyumu değil, aynı başlık-alt-dizgi koşulunu paylaşan iki otomatik kuralın birbiriyle uyumunu gösterir. Bu nedenle bir değerlendiriciler arası uyum (inter-annotator agreement) kanıtı olarak **raporlanamaz**. `MAKALE_HAZIRLIK_PLANI.md` FAZ 6A adım 1'in istediği "uzman/ikinci değerlendirici" etiketlemesi henüz yapılmamıştır.

## 1. Sorgu seti

- **Dosya:** `data/eval/rag/queries_and_qrels.json`
- **Toplam sorgu:** 60
  - **Cevaplanabilir (`Q01`–`Q48`):** Sorguların çoğu kanun numarasını açıkça içeren kısa anahtar ifadelerdir (ör. `"657 Sayılı Kanun sadakat ve tarafsızlık yükümlülüğü"`). Kapsam: 657, 5018, 4734, 2886, 3071, 4982, 7201, 2577, 6698, 5393, 5302, 5216, 6085, 4483, 3628, 5176, 5070, 6245, 4857, 5510, 2547, 7245, 6325, 2709 sayılı kanunlar; CBK-1…CBK-5; 2024/7 ve 2024/14 genelgeleri; iki ikincil düzenleme (tebliğ/yönetmelik).
  - **Cevaplanamaz (`U01`–`U12`):** 6 tanesi gerçek ama indekste olduğu varsayılan dışı mevzuat (5442, 213, 193, 1136, 2918 sayılı kanunlar ve Resmi Yazışma Yönetmeliği), 6 tanesi kurgusal düzenleme adı.
  - **Not:** `U06` (Resmi Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik) için indekste gerçekten bulunmadığı elle doğrulanmamıştır; makalede kullanmadan önce kontrol edilmelidir.
- Sorgu başına `qrels` boyutu 2 ile 206 arasında değişir (çok geniş `qrels`, Recall@k değerlerini düşük gösterir).

## 2. Otomatik alaka etiketleme yöntemi (gerçekte uygulanan)

Her cevaplanabilir sorgu için `(sorgu metni, title_kw, primary_terms, secondary_terms)` dörtlüsü elle tanımlanmıştır. Ardından **başlık/kanun numarası yayılımı uygulanmış zenginleştirilmiş korpus** (`build_enriched_corpus_texts`) üzerinde:

1. `title_kw` alt dizgisi geçen ve bir `primary_term` içeren parça → derece `2`
2. `title_kw` geçen ve yalnızca bir `secondary_term` içeren parça → derece `1`
3. Hiç `primary` bulunamazsa geri çekilme (fallback) kuralları uygulanır; en son çare olarak **`[0, 1]` indeksli parçalar** derece `2` atanır (anlamsal bir dayanağı yoktur).
4. Aynı MD5 içeriğe sahip kopyalar aynı dereceyi alır.

`nDCG@10` hesabında kazanç $2^{\text{grade}}-1$ kullanılmıştır; ikili metriklerde eşik $\text{grade} \ge 1$'dir.

## 3. "κ" değerinin gerçek anlamı

`inter_annotator_agreement` alanı (`n_pairs = 2136`, `κ = 0.9863`) şu iki kural arasındadır:
- **"Annotator A":** yukarıdaki otomatik `qrels` (≥1 ise ilgili)
- **"Annotator B":** `title_kw` alt dizgisi geçiyor **ve** sorgudan en az bir içerik belirteci geçiyor

İki kural da aynı `title_kw` koşuluna dayandığından yüksek uyum yapısal olarak beklenir; bağımsız bir doğrulama değildir.

## 4. Geçerliliğe yönelik tehditler

- **Döngüsellik:** `qrels`, R3–R6 yöntemlerinin de indekslediği başlık yayılımlı korpus üzerinde sözcüksel eşleşmeyle üretilmiştir. Bu durum sözcüksel/başlık yayılımlı yöntemleri (R3–R6) sistematik olarak kayırabilir; R1'e karşı gözlenen farkların bir kısmı etiketleme yönteminden kaynaklanıyor olabilir.
- **Sorgu biçimi:** Sorgular gerçek memur sorularından değil, kanun numarası + anahtar ifade kalıbından oluşur.

## 5. Makaleye girmeden önce yapılması gereken

1. 48 cevaplanabilir sorgunun her biri için R1–R6 birleşik top-10 havuzunu (pooling) çıkarmak.
2. Havuzu en az bir alan uzmanı (tercihen iki) ile 0/1/2 ölçeğinde **kör** etiketlemek; iki insan etiketleyici varsa gerçek Cohen's κ hesaplamak.
3. E3 metriklerini bu insan etiketleriyle yeniden hesaplamak.
