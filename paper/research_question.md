# Araştırma Sorusu, Literatür Taraması ve Araştırma Boşluğu Analizi (Faz 2)

> **Hedef Dergi:** Journal of Smart Systems Research (JOINSSR)
> **İlgili Hakem Maddeleri:** §3.5, §6, §7, Tablo 6, Tablo 12-P1
> **Kaynakça Dosyası:** [`paper/related_work.bib`](related_work.bib) (2021–2026 arası 14 hakemli/güncel kaynak)

---

## 1. Ana Araştırma Sorusu (Tek Paragraflık Formülasyon)

Kamu kurumlarına gelen Türkçe resmî evrak ve başvuruların veri mahremiyeti ve kurum içi ağ kısıtları altında işlenmesi problemi bağlamında bu çalışma şu temel araştırma sorusunu incelemektedir: **Tüketici/iş istasyonu sınıfı tek bir yerel GPU (`12 GB VRAM`) üzerinde 4-bit nicemlenmiş (`Q4_K_M`) açık ağırlıklı bir büyük dil modeli (`gemma4:12b`) ile yürütülen Türkçe kamu belgesi ön sınıflandırmasında, kural tabanlı ve klasik makine öğrenmesi (`TF-IDF + Linear SVM / Lojistik Regresyon`) taban çizgilerine kıyasla doğruluk (`Macro-F1`), çıkarım gecikmesi (`medyan / p95`) ve bellek tüketimi nasıl bir denge oluşturmakta; buna ek olarak yerel mevzuat erişimi (`TF-IDF / BM25 RAG`), deterministik kural doğrulama katmanı (`ReasoningAgent`) ve girdi sarmalama/maskeleme önlemleri, mevzuat eşleştirme isabetine, üretilen taslakların olgusal/hukuki tutarlılığına ve istem enjeksiyonu ile kişisel veri sızıntısı risklerinin azaltılmasına ne ölçüde katkı sağlamaktadır?**

### Alt Araştırma Soruları (Deneylerle Birebir Eşleşen Yapı)
- **AS1 (Sınıflandırma ve Taban Çizgileri — E1 & E2):** 18 kamu evrak türünü kapsayan çok sınıflı taksonomide, yerel `gemma4:12b` (`Q4_K_M`) sıfır-örnekli (zero-shot) yapılandırılmış sınıflandırma başarımı, başlık/kural tabanlı sınıflandırıcı ve `TF-IDF + Linear SVM / Lojistik Regresyon` taban çizgilerinden istatistiksel olarak anlamlı biçimde ayrışmakta mıdır; hatalar hangi belge çiftlerinde (`karar` ↔ `kararname` vb.) yoğunlaşmaktadır?
- **AS2 (Mevzuat Erişimi ve Deterministik Doğrulama — E3 & E4):** Yerel mevzuat korpusu (`956` belge, `3056` parça) üzerinde `TF-IDF` ve `BM25` erişim yöntemlerinin parça düzeyi geri çağırma (`Recall@5`, `MRR@10`, `nDCG@10`) ve kaynak künyesi doğruluğu nedir; LLM çıktıları sonrasında çalıştırılan deterministik `ReasoningAgent` doğrulama kuralları (ablation: açık vs. kapalı) tutarsız yönlendirme, güven skoru şişmesi ve eksik alan hatalarını ne oranda yakalamaktadır?
- **AS3 (Güvenlik, Taslak Kalitesi ve Donanım/Gecikme Dengesi — E5 & E6):** `<evrak>` etiketiyle sarmalama ve algoritmik PII maskeleme katmanları, adversarial dolaylı istem enjeksiyonu (indirect prompt injection) saldırı başarısını ve taslağa kişisel veri sızıntısını yüzde kaç oranında düşürmektedir; tekil sınıflandırma ile 6 LLM çağrılı paralel boru hattının (pipeline) soğuk/sıcak gecikme dağılımları (`ortalama`, `medyan`, `p95`) farklı belge uzunluklarında nasıl değişmektedir?

---

## 2. Son 5 Yıl (2021–2026) Literatür Taraması

### 2.1. Türkçe Hukuki ve İdari Belge Sınıflandırması
Türkçenin sondan eklemeli morfolojisi ve bürokratik yazışma kalıpları nedeniyle hukuki/idari metin sınıflandırması son yıllarda klasik istatistiksel yöntemlerden alana uyarlanmış Transformer ve LLM mimarilerine evrilmiştir:
- **Klasik ML ve Kodlayıcı (Encoder) Taban Çizgileri:** `LexGLUE` kıstas kümesinde (`chalkidis2022lexglue`) gösterildiği üzere, yapısal başlık ve form kalıpları taşıyan hukuki belgelerde `TF-IDF + Linear SVM`, küçük ve orta ölçekli veri kümelerinde oldukça güçlü bir taban çizgisi oluşturmaktadır. Türkçe özelinde `LegalTurk` (`zeidi2024legalturk`) ve `HUKUKBERT` (`ozturk2026hukukbert`), genel amaçlı `BERTurk` modellerini Türkçe hukuk korpusu üzerinde alana uyarlayarak çok etiketli sınıflandırma ve varlık tanıma görevlerinde başarım artışı sağlamıştır.
- **Yüksek Yargı ve Mevzuat Kıstasları:** Anayasa Mahkemesi bireysel başvuru kararlarında kabul edilebilirlik ve hak ihlali tahmini (`aydemir2025tcc`) ile 38.009 yüksek yargı ve mevzuat belgesini kapsayan `TurkishLegalBench` (`erkan2026turkishlegalbench`, özellikle mevzuat türlerini ayırt eden *TurkCanon* ve yetkili daireyi belirleyen *TurkVenue* alt görevleri) Türkçe hukuki NLP'de standartlaşmayı başlatmıştır.
- **Mevcut Eksiklik:** Bu çalışmaların tamamına yakını yüksek yargı kararlarına (Yargıtay, Danıştay, AYM) veya ince ayar (fine-tuning) gerektiren denetimli kodlayıcı modellere odaklanmaktadır; kamu kurumlarına gelen **18 farklı idari ve hukuki evrak türünü** (dilekçe, resmî yazı, genelge, tebliğ, yönetmelik, kararname, tutanak, müzekkere vb.) yerel nicemlenmiş bir üretken dil modeliyle sınıflandırıp klasik taban çizgileriyle kıyaslayan deneysel bir çalışma literatürde eksiktir.

### 2.2. Hukuki/Mevzuat Erişimi (RAG) ve Halüsinasyon Denetimi
Büyük dil modellerinin mevzuat dayanaklı metin üretiminde en kritik risk, var olmayan madde atfı ve kaynakla çelişen çıkarımlardır:
- **RAG Mimarileri ve Erişim Ölçümü:** `gao2023ragsurvey` RAG sistemlerini erişim, güçlendirme ve üretim aşamalarında sınıflandırmış; `louis2024interpretable` (*LLeQA*) ise 27.942 mevzuat maddesi üzerinde *Retrieve-then-Read* boru hattıyla madde dayanaklı uzun yanıt üretimini incelemiştir. `LegalBench-RAG` (`pipitone2024legalbenchrag`), hukuki RAG değerlendirmesinin yalnızca son yanıt üzerinden değil, doğrudan parça düzeyi erişim metrikleriyle (`Recall@k`, `Precision@k`) yapılması gerektiğini ortaya koymuştur.
- **Hukuki Halüsinasyon Kanıtı:** Stanford ekibinin ampirik çalışması (`magesh2025hallucination`), ticari RAG tabanlı hukuk araçlarının dahi `%17–%33` oranında yanlış kaynak atfı veya desteksiz iddia ürettiğini kanıtlamıştır. Benzer şekilde `LegalBench` (`guha2023legalbench`), kural hatırlama ile kural uygulama başarımlarının birbirinden farklı olduğunu göstermiştir.
- **Mevcut Eksiklik:** Türkçe mevzuat korpusu üzerinde yerel seyrek erişim yöntemlerinin (`TF-IDF` vs. `BM25`) `Recall@5`, `MRR@10`, `nDCG@10` metrikleriyle karşılaştırılması ve LLM çıktılarının deterministik bir doğrulama katmanıyla (`ReasoningAgent`) denetlenmesinin hata azaltma katkısının *ablation* (açık/kapalı) deneyiyle ölçülmesi henüz raporlanmamıştır.

### 2.3. E-Devlet Uygulamalarında Yerel (On-Premise) LLM, Nicemleme ve Güvenlik
- **E-Devlet ve Modüler LLM Mimarileri:** `papageorgiou2024egov`, e-devlet hizmetlerinde RAG ve çok aşamalı üretken yapay zekâ iş akışlarını modüler ve tekrarlanabilir bir mimaride sunmuş; ancak bulut/harici model kullanımı yerine tek GPU'lu kurum içi donanımda nicemlenmiş model gecikmesini ve deterministik kural denetimini ölçmemiştir.
- **Nicemleme (Quantization) ve Yerel Çıkarım:** `frantar2023gptq` (*GPTQ*), milyar parametreli modellerin 4-bit nicemleme ile sınırlı VRAM (`12–16 GB`) üzerinde çalıştırılabilmesinin teorik temelini kurmuştur.
- **Dolaylı İstem Enjeksiyonu (Indirect Prompt Injection):** `greshake2023notwhat`, dışarıdan gelen belgeleri özetleyen veya sınıflandıran LLM uygulamalarının belge içine gömülü talimatlarla ele geçirilebileceğini göstermiş; girdi sarmalama (`<evrak>`) ve sterilizasyon önlemlerinin adversarial örneklerle test edilmesi gerektiğini vurgulamıştır.

---

## 3. Araştırma Boşluğu (Research Gap) Matrisi

| Literatür Ekseni | Mevcut Çalışmalar (`2021–2026`) Neyi Yapıyor? | Mevcut Çalışmalar Neyi Açık Bırakıyor (Boşluk)? | Bu Çalışma Neyi Ekliyor ve Ölçüyor? |
|---|---|---|---|
| **Türkçe Hukuki / İdari Sınıflandırma** (`erkan2026turkishlegalbench`, `ozturk2026hukukbert`, `zeidi2024legalturk`, `aydemir2025tcc`) | Yüksek yargı kararlarında (AYM, Yargıtay) ihlal/suç tahmini veya denetimli `BERTurk` ince ayarı yapıyor. | Kurum içi evrak akışındaki **18 idari/mevzuat sınıfında** yerel LLM ile sıfır-örnekli sınıflandırmayı kural ve `TF-IDF+SVM` taban çizgileriyle karşılaştırmıyor. | 18 sınıflı kamu evrak taksonomisinde yerel `gemma4:12b (Q4_K_M)` modelini kural tabanlı ve `TF-IDF + Linear SVM/LR` baseline'larıyla aynı test kümesinde karşılaştırır (**E1, E2**). |
| **Mevzuat RAG ve Halüsinasyon Kontrolü** (`magesh2025hallucination`, `pipitone2024legalbenchrag`, `louis2024interpretable`) | İngilizce/Fransızca mevzuatta RAG erişimini ölçüyor ve yalnız RAG'ın halüsinasyonu (`%17–33`) tam önleyemediğini gösteriyor. | Türkçe mevzuat parçalarında `TF-IDF` ↔ `BM25` karşılaştırması ve LLM sonrası **deterministik doğrulama kurallarının (`ReasoningAgent`)** ablation etkisi eksik. | `956` belge / `3056` parçalık Türkçe mevzuat indeksinde `TF-IDF` ve `BM25`'i (`Recall@5`, `MRR@10`, `nDCG@10`) karşılaştırır; `ReasoningAgent` açık/kapalı ablation deneyi sunar (**E3, E4**). |
| **E-Devlet Yerel LLM ve Donanım/Gecikme Protokolü** (`papageorgiou2024egov`, `frantar2023gptq`) | E-devlette modüler RAG/ajan mimarisi öneriyor veya genel nicemleme başarımını ölçüyor. | Tek GPU'lu (`12 GB VRAM`) yerel ortamda **tekil sınıflandırma vs. çok aşamalı paralel pipeline** soğuk/sıcak gecikme dağılımını (`medyan`, `p95`) raporlamıyor. | Kısa/orta/uzun belgelerde soğuk başlangıç ve sıcak çıkarım altında tekil ve paralel aşama sürelerini (`medyan`, `p95`, `%95 GA`, VRAM) tekrarlanabilir protokolle ölçer (**E6**). |
| **Belge Güvenliği (Prompt Injection & KVKK/PII)** (`greshake2023notwhat`, `demirsoy2026face`) | Dolaylı istem enjeksiyonu tehdidini tanımlıyor; uygulama makalelerinde saldırı testi bekliyor. | Türkçe kamu evrakı boru hattında `<evrak>` sarmalama ve algoritmik PII maskelemenin **saldırı/sızıntı azaltma oranını** deneysel olarak ölçmüyor. | Adversarial evrak örnekleriyle istem enjeksiyonu başarı/azaltma oranını ve etiketli örneklerle PII yanlış pozitif/negatif ile taslağa sızıntı oranını ölçer (**E5**). |

---

## 4. JOINSSR Örnek Makale İncelemesi (`demirsoy2026face`) ve Somut Raporlama Hedefi

Hakem raporunda [4] referans gösterilen güncel JOINSSR makalesi (*Demirsoy vd., 2026, Cilt 7, Sayı 1, s. 30–51, `doi:10.58769/joinssr.1935127`*) yöntem ve raporlama somutluğu açısından incelenmiştir:

| Boyut | JOINSSR Örnek Makalesi (`demirsoy2026face`) | Bizim Makalemiz İçin Belirlenen Somut Eşdeğer Hedef |
|---|---|---|
| **Problem ve Sistem Tanımı** | Fiziksel erişim kontrolü için yüz tanıma + aktif canlılık tespiti + mikrodenetleyici kilit entegrasyonu. | Kurum içi kamu evrakı ön işleme için yerel LLM (`gemma4:12b`) + mevzuat RAG + deterministik doğrulama (`ReasoningAgent`) boru hattı. |
| **Değerlendirme Veri Kümesi** | Özel oluşturulmuş `n=300` görüntülük test kümesi; açık etiketleme ve senaryo ayrımı. | 18 sınıfı temsil eden, deduplikasyonu ve etiketleme protokolü belgelenmiş kamu evrakı değerlendirme kümesi (`data/eval/classification/`) + etiketli RAG sorgu ve güvenlik setleri. |
| **Klasik ML / Yöntem Karşılaştırması** | Derin yüz gömmeleri (`128-B`) üzerinde `SVM` sınıflandırma doğruluğu ve eşik analizi. | `gemma4:12b (Q4_K_M)` ile (A) Başlık/Kural tabanlı sınıflandırıcı ve (B) `TF-IDF + Linear SVM / Lojistik Regresyon` karşılaştırması (**E2**). |
| **Saldırı ve Güvenilirlik Testi** | Basılı fotoğraf ve dijital ekran (spoofing) saldırılarına karşı aktif canlılık (EAR göz kırpma) başarı oranlarının sayısal ölçümü. | (1) `ReasoningAgent` açık/kapalı ablation testi (**E4**), (2) Adversarial evraklarla dolaylı istem enjeksiyonu azaltma oranı ve PII maskeleme/sızıntı testi (**E5**). |
| **Donanım ve Gerçek Zamanlı Performans** | Kamera + gömülü donanım tepki süresi ve gerçek zamanlı çalışma doğrulaması. | `RTX 5070 (12 GB VRAM)` üzerinde soğuk/sıcak koşu, belge uzunluğu grupları ve `LLM_MAX_CONCURRENT_REQUESTS=2` altında `medyan`, `p95`, `%95 GA` gecikme ve VRAM raporu (**E6**). |

---

## 5. Yazılım Doğrulama Testleri (479 Test) ile Model Kalite Deneylerinin Ayrıştırılması (Hakem §3.5 & §6)

Hakem §3.5 ve §6 uyarınca, depodaki **479 otomatik `pytest` testi** makalede "model başarımı kanıtı" olarak sunulmayacak; aşağıdaki tabloda görüldüğü gibi **Yazılım Doğrulama (Sahte LLM)** ile **Deneysel Model Değerlendirmesi (Gerçek LLM)** açıkça ayrıştırılacaktır:

| Kanıt Katmanı | Alt Kategori / Kapsam | Test / Örnek Sayısı | Gerçek LLM (`Ollama`) Kullanımı | Yakaladığı Hata Sınıfı / Doğruladığı Özellik |
|---|---|---:|---|---|
| **A. Yazılım Doğrulama Testleri (`pytest`)** | **A1. API Sözleşmeleri, İş Akışı ve Uç Noktalar** (`tests/test_api.py` + `TestNewEndpoints`, `TestExportEndpoints` vb.) | `215` test | **Hayır** (Sahte/Mock LLM) | HTTP durum kodları, şema doğrulama, arka plan iş (`JobManager`) durum geçişleri, geçmiş ve memur inceleme (`review`) uç noktaları. |
| **A. Yazılım Doğrulama Testleri (`pytest`)** | **A2. Deterministik Doğrulama ve Ajan Kuralları** (`tests/test_reasoning.py` çekirdek kural testleri) | `134` test | **Hayır** (Sahte/Mock LLM) | `ReasoningAgent` altındaki 6 deterministik kuralın, `<\|channel>thought` temizliğinin (`strip_thinking`) ve JSON ayrıştırma/onarım mantığının birim doğrulaması. |
| **A. Yazılım Doğrulama Testleri (`pytest`)** | **A3. Güvenlik, Girdi Sterilizasyonu ve Erişim Denetimi** (`TestSanitizer*`, `TestFileValidator`, `TestRequestValidator`, `TestIPFilterMiddleware`, `TestDataEncryption`) | `55` test | **Hayır** (Sahte/Mock LLM) | Path traversal engelleme, dosya uzantı/boyut sınırı, `<evrak>` etiketi kaçışlama, IP filtreleme, istek gövdesi sınırı ve denetim izi (`AuditLogger`). |
| **A. Yazılım Doğrulama Testleri (`pytest`)** | **A4. Hata Toleransı, Önbellek ve Sistem Tanılama** (`TestRetryService`, `TestCacheService`, `TestErrorTracker`, `TestHealth*`, `TestBackup*`, `TestDiagnostics*`) | `75` test | **Hayır** (Sahte/Mock LLM) | LLM erişilemezliğinde devre kesici (`CircuitBreaker`), kısmi pipeline başarısızlığı kurtarma, TTL önbellek, yedek doğrulama ve disk/sistem sağlığı. |
| **Toplam (Katman A)** | **Yazılım Mühendisliği ve Hata Toleransı Doğrulaması** | **`479` test** | **Hayır (Tamamı Mock)** | **Yalnızca yazılım/boru hattı bütünlüğünü kanıtlar; modelin anlamsal doğruluğunu ölçmez.** |
| **B. Model ve Çıktı Kalitesi Deneyleri** | **E1–E6 Deney Paketi (`experiments/`)** | Faz 3–9 kümeleri | **Evet (`gemma4:12b Q4_K_M`)** | Gerçek yerel LLM ile 18 sınıf sınıflandırma (`Macro-F1`), baseline farkı, RAG erişim kalitesi (`Recall@5`, `MRR@10`), ablation, saldırı/PII oranları ve gecikme (`p95`). |
