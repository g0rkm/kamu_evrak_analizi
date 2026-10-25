# Makale Hazırlık Görev Planı — JOINSSR Gönderimi

> **Kaynak:** `JOINSSR_guncel_hakem_raporu.docx` (Ön hakem değerlendirmesi, 25.10.2026)
> **Hedef dergi:** Journal of Smart Systems Research (JOINSSR), Sakarya Uygulamalı Bilimler Üniversitesi
> **Hakem kararı:** MAJOR REVISION — *konu uygun, mevcut sunumuyla gönderime hazır değil*
> **Branch:** `makale-hazirlik` (Develop'tan türetildi)
> **Bu dosyanın amacı:** Rapordaki her eleştiriyi, repodaki somut dosyalara ve ölçülebilir çıktılara bağlayan, adım adım uygulanabilir bir yol haritası sunmak. (Henüz hiçbir düzeltme yapılmadı — bu yalnızca plandır.)
> **İlerleme işareti:** Faz başlıklarında `[ ]` = yapılmadı, `[X]` = tamamlandı.

---

## 0. Stratejik çerçeve

### 0.1 Ana karar: kapsamı daralt
Hakem §9 ve Tablo 13'ün özü: Makaleyi **"her özelliği anlatan"** bir sistem tanıtımından çıkarıp, tek bir araştırma sorusu etrafında **ölçülebilir deneysel değerlendirmeye** dönüştür.

**Seçilen ana araştırma sorusu (Hakem Tablo 6):**
> Türkçe kamu belgelerinin kurum içi yerel bir LLM ile ön sınıflandırılmasında doğruluk, gecikme ve kaynak tüketimi nasıl bir denge oluşturur; RAG ve deterministik doğrulama (ReasoningAgent), mevzuat eşleştirmesi ve taslak güvenilirliğine ölçülebilir katkı sağlar mı?

**Birincil katkı:** Sınıflandırma + baseline karşılaştırması + ölçülebilir gecikme.
**İkincil katkı (kanıt üretilebilirse):** RAG retrieval kalitesi + ReasoningAgent ablation.
**İlke:** Deney sonucu iddiayı desteklemezse → iddiayı daralt, sonucu parlatma (Hakem §9).

### 0.2 İzlenebilirlik matrisi (hakem eleştirisi → faz → öncelik)

| Hakem maddesi | Konu | Plan fazı | Öncelik (rapor) |
|---|---|---|---|
| §3.1, Tablo 5, Tablo 7-E1 | 18 sınıf iddiası ↔ 6 sınıflı test açıklığı | Faz 1, Faz 4 | P0, P2 |
| §3.2, Tablo 7-E2 | Baseline yok | Faz 5 | P3 |
| §3.3, §6 | İki hız rakamının çelişkisi | Faz 8 | P6 |
| §3.4, §5.1, Tablo 7-E3 | RAG büyüklüğü ≠ kalite | Faz 6 | P4 |
| §3.5, §6 | 479 testin doğru yorumu | Faz 2, Faz 10 | P0 |
| §2 (yerel çalışma sınırı) | Mutlak mahremiyet iddiası | Faz 1 | P0 |
| §5.2, Tablo 7-E5 | Prompt injection kanıtı | Faz 7 | P5 |
| §5.3 | PII/KVKK ölçümü | Faz 7 | P5 |
| §5.4 | Human-in-the-loop katkısı | Faz 9 | P5 |
| §5.5 | "Çok ajanlı" adlandırma | Faz 1, Faz 10 | P1 |
| §6, Tablo 8, Tablo 7-E6 | Tekrarlanabilirlik/performans protokolü | Faz 8 | P6 |
| §4.2 | Veri kümesi & etiketleme protokolü | Faz 3 | P2 |
| Tablo 7-E4 | ReasoningAgent ablation | Faz 6 | P5 |
| §7, Tablo 9/10/11 | Konumlandırma, başlık, yapı | Faz 10 | P1 |
| §7 (JOINSSR kuralları), Tablo 12-P7 | Şablon, körleme, benzerlik, beyanlar | Faz 11 | P7 |

### 0.3 Önerilen klasör düzeni (branch içinde oluşturulacak)
```
paper/                     # Makale metni (JOINSSR Word şablonu + taslaklar)
data/eval/                 # Etiketli değerlendirme kümeleri (anonimleştirilmiş)
  ├── classification/      # E1: 18 sınıf test seti + etiket meta
  ├── rag/                 # E3: sorgu seti + ilgili parça etiketleri
  └── drafts/              # E5: taslak puanlama sayfaları
experiments/               # Deney betikleri (E1–E6) — kod Aider ile üretilecek
results/                   # Ham çıktı + tablolar + şekiller (grafik/CSV/JSON)
docs/etiketleme_protokolu.md   # Etiketleme yönergesi (Faz 3)
docs/olcum_protokolu.md        # Performans ölçüm protokolü (Faz 8)
```
> **Not:** Deney kodları proje kuralı gereği (CLAUDE.md KURAL 1) Aider + Argon ile yazılacak; bu plan her betiğin ne yapacağını ve hangi çıktıyı üreteceğini tanımlar.

---

## [X] FAZ 0 — Hazırlık ve altyapı

**Amaç:** Deney ve yazım işinin üzerine kurulacağı iskeleti kurmak.

**Adımlar:**
1. `makale-hazirlik` branch'inin Develop'tan güncel olduğunu doğrula (`git log --oneline -3`).
2. Yukarıdaki klasör düzenini oluştur (`paper/`, `data/eval/`, `experiments/`, `results/`).
3. `data/eval/`, `results/` ve ham çıktıların `.gitignore` politikası kararı: anonimleştirilmiş etiket/metrik dosyaları versiyonlanır; ham kişisel veri içeren belgeler versiyonlanmaz (Faz 3 ile uyumlu).
4. Deney ortamını dondur: `pip freeze > experiments/requirements.lock.txt`, Ollama sürümü, GPU sürücüsü/CUDA, model etiketi/quantization kaydını `docs/olcum_protokolu.md`'ye not et.

**Çıktı:** Klasör iskeleti + ortam künyesi.
**Kabul kriteri:** Ortam künyesi bir başka makinede deneyi tekrarlamaya yetecek ayrıntıda.

---

## [X] FAZ 1 — İddiaların düzeltilmesi (P0) · kod/deney gerektirmez

**Amaç:** Yanıltıcı genellemeleri kaldırmak — hakem §3.1, §2, §3.5, §5.5, Tablo 5. Bu faz **önce** yapılmalı çünkü makale iddiaları buradan türeyecek.

**Adımlar:**
1. **README — sınıflandırma iddiası (Tablo 5):**
   - `README.md` satır 8 ve 77'deki "18 evrak türü … Macro F1: 0.935" izlenimini düzelt.
   - Yeni ifade: *"6 kategorilik pilot benchmark (n=54): Macro-F1=0.935; 18 sınıfın tamamı henüz değerlendirilmedi."*
   - F1 tablosunun başına örneklem ve kapsam uyarısı ekle (Wilson GA ~%82.4–97.1, §3.1).
2. **README — mahremiyet iddiası (§2):**
   - "hiçbir evrak verisi bulut API'lerine gönderilmez" (satır 7) ve §Güvenlik bölümündeki mutlak ifadeleri yumuşat.
   - Yeni ifade: *"Yerel Ollama yapılandırmasında, uzak LLM uç noktası kapalı ve dış veri akışı ayrıca doğrulanmışsa evrak içeriği yerel işlenebilir."*
3. **README — 479 test yorumu (§3.5):**
   - Testlerin **sahte LLM** kullandığını ve gerçek model kalitesini ölçmediğini açıkça yaz; iki kanıt türünü ayır (yazılım doğrulama ↔ model/çıktı kalitesi).
4. **README — "çok ajanlı" adlandırma (§5.5):**
   - Bağımsız planlama/dinamik görev devri kanıtlanamıyorsa "ajan tabanlı çok aşamalı pipeline" ifadesine geç.
5. **Sınırlılıklar taslağı:** Hakem §8'deki 5 maddelik sınırlılık listesini `paper/limitations_notes.md` içine taslak olarak işle (makalede "Sınırlılıklar" bölümüne temel olacak).

**Çıktı:** Güncellenmiş `README.md` + `paper/limitations_notes.md`.
**Kabul kriteri:** README'de 18 sınıf / mutlak mahremiyet / test sayısı iddialarının hiçbiri kanıtsız genelleme içermiyor.
**İlgili dosyalar:** `README.md`, (yeni) `paper/limitations_notes.md`.

---

## [X] FAZ 2 — Araştırma sorusu, özgünlük ve literatür (P1)

**Amaç:** "Yazılım yaptık" anlatımından bilimsel soruya geçmek — hakem §7, Tablo 6, Tablo 12-P1.

**Adımlar:**
1. 0.1'deki araştırma sorusunu tek paragrafa indir; 2–4 açık katkı maddesi yaz (`paper/contributions.md`).
2. Son 5 yıl (2021–2026) literatür taraması: yerel/offline LLM ile belge sınıflandırma, Türkçe NLP, kamu/hukuki belge işleme, RAG tabanlı mevzuat erişimi. Her kaynağı `paper/related_work.bib` + kısa notla kaydet.
3. **Araştırma boşluğunu belgeleyerek göster:** mevcut çalışmaların neyi yapmadığını, bu çalışmanın ne eklediğini açık yaz.
4. JOINSSR örnek makalesini (Hakem [4], yüz tanıma erişim kontrolü, n=300) yöntem/raporlama biçimi açısından incele; benzer somutlukta ölçülebilir sonuç hedefi belirle.

**Çıktı:** `paper/research_question.md`, `paper/contributions.md`, `paper/related_work.bib` + notlar.
**Kabul kriteri:** Araştırma boşluğu en az 8–12 güncel kaynağa dayandırılmış; katkı iddiaları deneylerle (Faz 4–8) birebir eşleşiyor.

---

## [X] FAZ 3 — Veri kümesi ve etiketleme protokolü (P2)

**Amaç:** Ana sınıflandırma iddiasını doğrulayacak, savunulabilir bir etiketli küme kurmak — hakem §4.2, Tablo 12-P2.

**Adımlar:**
1. **Sınıfların operasyonel tanımı:** `app/core/taxonomy.py`'deki 18 türü temel al; her sınıf için ayırt edici kural/başlık/biçim ölçütlerini `docs/etiketleme_protokolu.md`'ye yaz. Özellikle "karar" ↔ "kararname" ayrımını netleştir (§4.2).
2. **Örnek toplama hedefi (Tablo 7-E1):** 18 sınıfın tamamı için sınıf başına **asgari 10–20**, mümkünse **20–30+** örnek. Kaynak: `scripts/scraper.py` + elde mevcut `app/data/scraped/documents.json` (956 belge) + gerekirse ek toplama.
3. **Meta kayıt:** Her örnek için kaynak, yayım tarihi, belge türü, metin uzunluğu (karakter/token), varsa mevzuat sürümü. Şema: `data/eval/classification/labels_schema.json`.
4. **Deduplikasyon:** Aynı belgenin farklı formatlarını / çoğaltılmış mevzuat sürümlerini temizle (sonucu şişirmesin, §4.2). Yöntem ve kaldırılan örnek sayısını raporla.
5. **Hukuki güncellik kontrolü:** Yürürlükten kalkmış/eski sürüm metinleri işaretle (§5.1 ile bağlantılı).
6. **Etiketleyiciler arası uyum:** Mümkünse ≥2 bağımsız etiketleyici + uyuşmazlık çözümü; **Cohen's kappa** raporla. Tek etiketleyici varsa bunu sınırlılık olarak yaz (§4.2).
7. **Veri sızıntısı önleme:** Prompt/kural geliştirme örnekleri ile **nihai test örneklerini ayır**; geliştirme sırasında test kümesine bakma (§4.2). Train/dev/test bölünmesini sabit `seed` ile kaydet.

**Çıktı:** `docs/etiketleme_protokolu.md`, `data/eval/classification/` (anonimleştirilmiş), bölünme ve dedup raporu.
**Kabul kriteri:** 18 sınıf temsil ediliyor; etiketleme yönergesi bir üçüncü kişinin aynı etiketi üretebileceği netlikte; dev/test ayrımı belgelenmiş.
**İlgili dosyalar:** `app/core/taxonomy.py`, `scripts/scraper.py`.

---

## [ ] FAZ 4 — E1: 18 sınıf sınıflandırma deneyi (P2)

**Amaç:** Ana sınıflandırma iddiasını 18 sınıfta doğrulamak — hakem Tablo 7-E1.

**Adımlar:**
1. `scripts/evaluate_f1.py`'yi 6 sınıftan **18 sınıfa** genişlet (veya `experiments/e1_classification.py` olarak yeniden kur). Girdi: Faz 3 test kümesi. `seed` sabit.
2. Metrikleri üret: **Macro-F1, accuracy, sınıf bazlı precision/recall/F1, karışıklık matrisi (confusion matrix).**
3. **Bootstrap güven aralığı** hesapla (Macro-F1 ve accuracy için).
4. **Hata analizi:** En sık karışan sınıf çiftlerini ve örnek hataları `results/e1/` altına çıkar.
5. Model/prompt/bağlam ayarlarını ve commit'i çıktıya göm (tekrarlanabilirlik).

**Çıktı:** `results/e1/metrics.json`, karışıklık matrisi şekli, hata örnekleri tablosu.
**Kabul kriteri:** 18 sınıfın her biri için metrik + GA raporlanıyor; sonuç README/makalede doğru kapsamla sunuluyor.
**İlgili dosyalar:** `scripts/evaluate_f1.py`, `app/agents/classifier_agent.py`, `app/core/taxonomy.py`.

---

## [ ] FAZ 5 — E2: Baseline karşılaştırmaları (P3)

**Amaç:** 0.935'in göreli değerini göstermek — hakem §3.2, Tablo 7-E2.

**Adımlar:**
1. **Baseline A — Kural/başlık tabanlı sınıflandırıcı:** Belge başlığı/anahtar kelime/biçim kurallarıyla sınıf ata (`experiments/baseline_rule.py`).
2. **Baseline B — Klasik ML:** TF-IDF + **Linear SVM** ve/veya **Lojistik Regresyon** (`experiments/baseline_ml.py`, scikit-learn zaten bağımlı).
3. **(Opsiyonel) Baseline C — Alternatif yerel LLM:** Aynı donanımda başka bir talimat-izleyen yerel model (ör. farklı bir Ollama modeli).
4. Üç/dört yöntemi **aynı test örnekleri** üzerinde çalıştır; skor farklarını ve istatistiksel anlamlılığı raporla.
5. Tüm prompt, model etiketi ve ayarları sabitleyip kaydet (§3.2).

**Çıktı:** `results/e2/baselines_comparison.csv` + karşılaştırma tablosu/şekli.
**Kabul kriteri:** Gemma 4 12B sonucu en az bir kural tabanı ve bir klasik sınıflandırıcıyla karşılaştırılmış; fark (varsa) GA ile gösterilmiş.
**İlgili dosyalar:** (yeni) `experiments/baseline_*.py`, `requirements.txt` (gerekirse).

---

## [ ] FAZ 6 — E3 + E4: RAG değerlendirmesi ve ReasoningAgent ablation (P4, P5)

**Amaç:** "956 belge/3056 parça" sayısını kalite kanıtına çevirmek ve kontrol katmanının katkısını ölçmek — hakem §3.4, §5.1, Tablo 7-E3/E4.

### 6A — RAG retrieval değerlendirmesi (E3)
**Adımlar:**
1. Mevzuat sorgu seti kur; her sorgu için **ilgili kabul edilen parçaları** uzman/ikinci değerlendiriciyle etiketle (`data/eval/rag/`).
2. Metrikler: **Recall@5, MRR@10, nDCG@10.**
3. **TF-IDF ↔ BM25** karşılaştırması (`experiments/e3_rag_eval.py`).
4. **Kaynak atfı doğruluğu:** Her retrieval sonucunda mevzuat adı, madde/numara, yayım+yürürlük tarihi, kaynak URL/kimliği, indekse alma tarihi tutuluyor mu? (§5.1) Eksikse: ya `app/services/rag_service.py` + indeks şemasına ekleme planı yaz, ya da sınırlılık olarak belgele.
5. **Desteklenmeyen yanıt davranışı:** Yeterli dayanak yoksa sistemin "yeterli dayanak bulunamadı" demesi / insana bırakması test edilsin (§5.1).

### 6B — ReasoningAgent ablation (E4)
**Adımlar:**
1. Aynı belgeleri **doğrulama ajanı açık / kapalı** iki yapılandırmada çalıştır (`experiments/e4_ablation.py`). İlgili: `app/agents/reasoning_agent.py`, `app/agents/validation_rules.py`.
2. Raporla: hata sayısı/türü, düzeltilen vs hatalı düzeltmeler, yanlış güven üretimi, işlem süresi farkı.

**Çıktı:** `results/e3/retrieval_metrics.json`, `results/e4/ablation.csv`.
**Kabul kriteri:** Retrieval kalitesi sayısal metriklerle; ReasoningAgent'ın net katkısı/sınırı ölçülmüş.
**İlgili dosyalar:** `app/services/rag_service.py`, `scripts/build_index.py`, `app/agents/legislation_agent.py`, `app/agents/reasoning_agent.py`, `app/agents/validation_rules.py`.

---

## [ ] FAZ 7 — E5(güvenlik) + PII/KVKK + Prompt injection doğrulaması (P5)

**Amaç:** Güvenlik iddialarını saldırı testleriyle kanıtlamak — hakem §5.2, §5.3, Tablo 4.

**Adımlar:**
1. **Prompt injection (§5.2):** Adversarial belge örnekleri kur — talimatı görmezden gelme, gizli prompt isteme, yanlış birime yönlendirme, çıktı biçimini bozma. **Başarı/azaltma oranını ölç** (`experiments/e5_prompt_injection.py`). İlgili: `app/core/sanitizer.py`, `<evrak>` etiket mekanizması.
   - Dil: "koruma sağlar" yerine **"saldırı başarı oranı %X'e düşürülmüştür"**.
2. **PII/KVKK (§5.3):** TC kimlik (sağlama), IBAN, telefon, e-posta tespitini etiketli örneklerle değerlendir. **Yanlış pozitif + yanlış negatif** oranlarını ölç (`experiments/e5_pii_eval.py`). İlgili: PII servisi / `/api/mask-pii`.
3. **Maskeleme sonrası sızıntı:** Taslağa maskelenmiş veri sızıp sızmadığını ayrı test et.
4. **KVKK çerçevesi (§5.3):** Veri saklama, erişim yetkisi, logların hassas bilgi içerip içermediği, yedekler, yapılandırılabilir uzak LLM uç noktası riskini makalede tartış. İlgili: `data/history/`, `data/logs/`, `data/backups/`, `app/core/audit_middleware.py`.

**Çıktı:** `results/e5/injection.json`, `results/e5/pii_eval.json` + tartışma notları.
**Kabul kriteri:** Her güvenlik iddiası bir ölçülmüş orana bağlı; mutlak güvenlik iddiası yok.
**İlgili dosyalar:** `app/core/sanitizer.py`, `app/core/security_middleware.py`, PII servisi, `app/core/audit_middleware.py`.

---

## [ ] FAZ 8 — E6: Performans ve tekrarlanabilirlik protokolü (P6)

**Amaç:** Çelişkili/tekil ölçümleri tekrarlanabilir protokole bağlamak — hakem §3.3, §6, Tablo 8, Tablo 7-E6.

**Adımlar:**
1. **İki hız rakamını ayrıştır (§3.3):** ~1.3 sn tekil sınıflandırma ile 4.36 sn pipeline çağrısının farkını deney koşuluyla açıkla (girdi uzunluğu, soğuk/sıcak model, yalnız-sınıflandırma vs orkestrasyon, tekrar sayısı).
2. **Ölçüm protokolü (`docs/olcum_protokolu.md`):** Belge uzunluk grupları (kısa/orta/uzun), tekrarlı ölçüm, soğuk başlangıç ile sıcak çağrı ayrı.
3. **İstatistik:** Ortalama **+ medyan + p95**, mümkünse %95 GA, standart sapma; başarısız/kısmi analiz sayısı.
4. **Eşzamanlılık:** `LLM_MAX_CONCURRENT_REQUESTS` değeri, aynı anda işlenen evrak sayısı, kuyruk davranışı, timeout/başarısızlık oranı.
5. **Kaynak:** Peak VRAM/RAM, farklı belge uzunluklarında kararlılık.
6. **Künye (Tablo 8):** GPU/VRAM, CPU, RAM, OS, NVIDIA sürücü/CUDA, Ollama sürümü, tam model etiketi/quantization, context length, sampling parametreleri, reasoning ayarı, JSON modu, prompt sürümü, retry davranışı.

**Çıktı:** `experiments/e6_latency.py`, `results/e6/latency.csv` + `docs/olcum_protokolu.md`.
**Kabul kriteri:** Hiçbir süre tek sıcak koşudan ortalama gibi sunulmuyor; tablo bir başkasının tekrarlayabileceği künyeyle birlikte.
**İlgili dosyalar:** `app/agents/orchestrator.py`, `app/config.py`, `scripts/evaluate_f1.py`.

---

## [ ] FAZ 9 — E5(taslak kalitesi) + Human-in-the-loop analizi (P5)

**Amaç:** Taslak güvenilirliğini ve insan denetimi katkısını veriyle göstermek — hakem §5.4, Tablo 7-E5.

**Adımlar:**
1. **Taslak kör puanlama:** 30–50 belgede, mümkünse ≥2 uzmanla, **önceden tanımlı ölçütlerle** kör puanlama: mevzuata uygunluk, olgusal doğruluk, kapsayıcılık, **desteklenmeyen iddia oranı**, kişisel veri sızıntısı. Puanlayıcılar arası uyum raporla.
2. **Human-in-the-loop (§5.4):** `data/history/` içindeki onay/düzenleme/ret kayıtlarını **etik/mahremiyet koşullarına uygun** biçimde analiz et: taslakların ne kadarı onaylandı, ne tür düzeltmeler gerekti, yanlış yönlendirmeler ne sıklıkla insan tarafından yakalandı.
   - Veri yoksa: **"insan denetimi mekanizması uygulanmıştır"** de; **"güvenilirliği artırdı"** sonucuna atlama.

**Çıktı:** `data/eval/drafts/` puanlama sayfaları, `results/draft_quality.json`, HITL analiz notu.
**Kabul kriteri:** Taslak kalitesi ölçütlere bağlı; HITL iddiası mevcut veriyle orantılı.
**İlgili dosyalar:** `app/agents/draft_agent.py`, `app/agents/routing_agent.py`, `data/history/`.

---

## [ ] FAZ 10 — Makale yazımı (P1)

**Amaç:** Kanıtları JOINSSR yapısında bir makaleye dönüştürmek — hakem §7, Tablo 9/10/11.

**Adımlar:**
1. **Başlık (Tablo 9/10):** "Çok ajanlı" yerine yerel LLM + kamu belgesi + deneysel değerlendirmeyi öne çıkar.
   - TR: *"Türkçe Yerel Büyük Dil Modeli ile Kamu Evraklarının Sınıflandırılması ve Mevzuat Destekli Ön İşlenmesi: Tasarım ve Deneysel Değerlendirme"*
   - EN: *"Classification and Legislation-Aware Preprocessing of Public-Sector Documents with a Local Large Language Model: Design and Experimental Evaluation"*
2. **Yapı (Tablo 11):** Giriş → Metodoloji → Teori/hesaplamalar (metrik tanımları) → Bulgular ve tartışma → Sonuçlar → Beyanname/etik/ekler.
3. Türkçe + İngilizce özet ve anahtar kelimeler.
4. Her bulgu bölümüne Faz 4–9 sonuçlarını (tablo+şekil) yerleştir; sınırlılıkları (Faz 1 notları) ekle.
5. Metrik tanımlarını yaz (Macro-F1, Recall@k, MRR, nDCG, p95 vb.).

**Çıktı:** `paper/manuscript_tr.docx` (+ gerekiyorsa EN), şekiller/tablolar.
**Kabul kriteri:** Her iddianın arkasında bir deney sonucu var; yapı dergi şablonuyla uyumlu.

---

## [ ] FAZ 11 — Gönderim öncesi teknik hazırlık (P7)

**Amaç:** Teknik ön kontrolde eksik belge/format nedeniyle reddi önlemek — hakem §7, Tablo 12-P7.

**Adımlar:**
1. **JOINSSR Word şablonu** [2] ile biçimle.
2. **Körleme:** İlk gönderimde yazar tanımlayıcı tüm bilgileri kaldır (anonim).
3. **Benzerlik/intihal raporu** hazırla ve yükle.
4. **Beyanlar:** Çıkar çatışması, yazar katkıları, destek/fon, gerekliyse etik kurul açıklaması.
5. **Veri/kod erişimi:** HuggingFace korpusu (`g0rkm/kamu-evrak-korpus`), repo linki, etiketleme şeması, değerlendirme betikleri, indeks sürümü, anonimleştirilmiş sonuçlar.
6. **İndeks kontrolü (§JOINSSR):** Index Copernicus, Google Scholar, Crossref, SOBIAD [3]; kariyer için TR Dizin/Scopus/WoS gerekiyorsa ilgili veri tabanından ayrıca doğrula.
7. **Eksik belge kontrol listesi:** Resmî sayfa eksik belgelerin redde yol açabileceğini belirtiyor [1,2] — son kontrol.

**Çıktı:** Şablona uygun anonim manuscript + benzerlik raporu + beyan dosyaları + veri/kod erişim notu.
**Kabul kriteri:** JOINSSR gönderim kontrol listesinin tüm maddeleri karşılanmış.

---

## Bağımlılık sırası (özet akış)

```
Faz 0 (altyapı)
  └─ Faz 1 (iddia düzeltme, P0)        ← hemen, bloklamaz
        └─ Faz 2 (araştırma sorusu/literatür, P1)
              └─ Faz 3 (veri + etiketleme, P2)   ← tüm deneylerin ön koşulu
                    ├─ Faz 4 (E1 sınıflandırma, P2)
                    │     └─ Faz 5 (E2 baseline, P3)
                    ├─ Faz 6 (E3 RAG + E4 ablation, P4/P5)
                    ├─ Faz 7 (güvenlik/PII/injection, P5)
                    ├─ Faz 8 (E6 performans, P6)
                    └─ Faz 9 (taslak + HITL, P5)
                          └─ Faz 10 (yazım, P1)
                                └─ Faz 11 (gönderim öncesi, P7)
```

## Kritik ilkeler (hakemden)
- Yeni özellik eklemek değil, **var olan özellikleri ölçmek** esastır (Tablo 13).
- Her nicel iddia bir **örneklem + koşul + istatistik** ile birlikte verilir.
- Sonuç iddiayı desteklemezse **iddia daraltılır** (§9).
- Yazılım testleri (sahte LLM) ile model kalite deneyleri (gerçek LLM) **ayrı raporlanır** (§3.5).
