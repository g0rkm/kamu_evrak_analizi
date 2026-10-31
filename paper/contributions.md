# Makalenin Özgün Katkı Maddeleri ve Deneysel Eşleşme Matrisi (Faz 2)

> **Amaç:** Hakem Raporu §1, §7, §9 ve Tablo 6/12-P1 doğrultusunda, makalenin "Giriş" bölümünde sunulacak **4 ölçülebilir katkı iddiasını** tanımlamak ve her iddiayı Faz 4–9 deneylerine birebir bağlamak.
> **Temel İlke (Hakem §9):** Hiçbir katkı maddesi kanıtsız özellik listesine dayanmaz; deney sonucu iddiayı desteklemezse sonuç parlatılmaz, aşağıdaki **İddia Daraltma Kuralı** devreye alınır.

---

## 1. Makalenin 4 Açık Katkısı (Giriş Bölümü Taslağı)

1. **K1 — 18 Sınıflı Türkçe Kamu Evrakı Sınıflandırması ve Taban Çizgisi (Baseline) Karşılaştırması (Birincil Katkı — Faz 3, Faz 4 [E1], Faz 5 [E2]):**
   Kamu kurumlarında işlem gören 18 evrak türünü (`app/core/taxonomy.py`) kapsayan, tekilleştirilmiş (deduplicated) ve operasyonel etiketleme yönergesi belgelenmiş bir değerlendirme kümesi üzerinde, tek GPU'lu (`12 GB VRAM`) yerel `gemma4:12b (Q4_K_M)` modelinin sıfır-örnekli (zero-shot) sınıflandırma başarımı (`Macro-F1`, sınıf bazlı `Precision/Recall/F1`, `%95` bootstrap güven aralığı) ölçülmüş; başlık/anahtar kelime tabanlı kural sınıflandırıcısı ve klasik makine öğrenmesi (`TF-IDF + Linear SVM / Lojistik Regresyon`) taban çizgileriyle aynı test örnekleri üzerinde karşılaştırılarak yerel LLM'nin yapısal mevzuat ile serbest biçimli idari belgelerdeki göreli avantaj ve sınırları ortaya konulmuştur.

2. **K2 — Yerel Mevzuat Erişimi (RAG) ve Deterministik Doğrulama Katmanı (`ReasoningAgent`) Ablation Analizi (İkincil Katkı — Faz 6 [E3, E4]):**
   `956` kamu mevzuatı belgesi ve `3056` metin parçasından oluşan yerel korpus üzerinde `TF-IDF` ve `BM25` erişim yöntemlerinin parça düzeyi erişim kalitesi (`Recall@5`, `MRR@10`, `nDCG@10`) ile kaynak künyesi doğruluğu değerlendirilmiş; ayrıca üretken LLM çıktılarının ardından çalışan 6 kurallı deterministik doğrulama katmanının (`ReasoningAgent`) açık ve kapalı (*ablation*) yapılandırmalarda tutarsız birim yönlendirmesi, eksik alan, aşırı güven skoru ve kişisel veri sızıntısı hatalarını yakalama katkısı nicel olarak ölçülmüştür.

3. **K3 — Ajan Tabanlı Çok Aşamalı Pipeline'da Gecikme, Bellek ve Tekrarlanabilirlik Analizi (Birincil Katkı — Faz 8 [E6]):**
   Tekil iş istasyonu GPU'su (`NVIDIA RTX 5070 12GB VRAM`, `Ollama v0.40.8`, `LLM_MAX_CONCURRENT_REQUESTS=2`) üzerinde, soğuk başlangıç (*cold start*) ile sıcak çıkarım (*warm inference*) koşulları ve kısa/orta/uzun belge grupları ayrıştırılarak; tekil sınıflandırma çağrısı ile 6 LLM çağrılı paralel boru hattının (*pipeline*) aşama bazlı gecikme dağılımları (`ortalama`, `medyan`, `p95`, `%95 GA`), tepe VRAM tüketimi ve kısmi hata kurtarma davranışı tekrarlanabilir bir ölçüm protokolüyle raporlanmıştır.

4. **K4 — Kurum İçi Belge İşlemede İstem Enjeksiyonu, PII/KVKK Maskeleme ve İnsan Denetimi (HITL) Değerlendirmesi (Tamamlayıcı Katkı — Faz 7 [E5-Güvenlik], Faz 9 [E5-Taslak & HITL]):**
   Dışarıdan gelen evraklarda `<evrak>` etiketiyle sarmalama ve girdi sterilizasyonunun adversarial dolaylı istem enjeksiyonu (*indirect prompt injection*) saldırı başarı oranına etkisi ile kural/sağlama tabanlı kişisel veri (T.C. kimlik, IBAN, telefon, e-posta) tespitinin yanlış pozitif/negatif ve taslağa sızıntı oranları deneysel olarak ölçülmüş; üretilen resmî yazı taslaklarının uzman puanlaması ve insan denetimi (*Human-in-the-Loop*) mekanizmasının sınırları belirlenmiştir.

---

## 2. Katkı ↔ Deney ↔ İddia Daraltma Eşleşme Matrisi

| Katkı Kodu | İlgili Faz ve Deney | Üretilecek Somut Çıktı ve Metrikler | Karşılaştırma / Kontrol Koşulu | İddia Daraltma Kuralı (Sonuç Beklentiyi Desteklemezse — Hakem §9) |
|---|---|---|---|---|
| **K1** | **Faz 3, Faz 4 (`E1`), Faz 5 (`E2`)** | `results/e1/metrics.json`, `results/e2/baselines_comparison.csv`: 18 sınıf `Macro-F1`, `Accuracy`, sınıf bazlı `P/R/F1`, karışıklık matrisi, `%95` bootstrap GA. | Baseline A (Kural/Başlık) ve Baseline B (`TF-IDF + Linear SVM / LR`) (+ opsiyonel Baseline C: `qwen3:8b`). | Eğer `TF-IDF + SVM` yapısal mevzuat sınıflarında (`kanun`, `yönetmelik`, `tebliğ`) `gemma4:12b` kadar yüksek çıkarsa; "LLM her sınıfta üstündür" denmez, **"yapısal başlıklı mevzuatta hafif klasik sınıflandırıcıların yeterli olduğu, yerel LLM'nin ise başlığı belirsiz/serbest metinlerde ve çok görevli analizde katkı sağladığı"** raporlanır. |
| **K2** | **Faz 6A (`E3`), Faz 6B (`E4`)** | `results/e3/retrieval_metrics.json`, `results/e4/ablation.csv`: `Recall@5`, `MRR@10`, `nDCG@10`; `ReasoningAgent` açık/kapalı yakalanan hata sayısı, yanlış düzeltme oranı, ek süre (`~0.00 sn`). | `TF-IDF` vs. `BM25`; `ReasoningAgent` açık vs. kapalı; desteksiz sorguda "dayanak bulunamadı" davranışı. | Eğer `TF-IDF` / `BM25` kavramsal sorgularda düşük `Recall@5` verirse veya yürürlük tarihi takibi eksikse; bu durum **"kelime örtüşmesine dayalı seyrek erişimin sınırı"** olarak raporlanır ve yoğun gömme (dense embedding) / mevzuat sürümleme gelecek çalışma olarak konumlandırılır. |
| **K3** | **Faz 8 (`E6`)** | `results/e6/latency.csv`, `docs/olcum_protokolu.md`: Kısa/orta/uzun belgelerde soğuk ve sıcak koşu için `ortalama`, `SD`, `medyan`, `p95`, `%95 GA`, tepe VRAM/RAM. | Tekil `ClassifierAgent` çağrısı vs. 6 çağrılı paralel `OrchestratorAgent` akışı (`LLM_MAX_CONCURRENT_REQUESTS=2`). | Uzun belgelerde veya eşzamanlı isteklerde gecikme/timeout artarsa; sistem **"yüksek hacimli gerçek zamanlı akış motoru"** olarak değil, **"kurum içi asenkron iş kuyruğu (`JobManager`) ile çalışan ön inceleme ve taslak destek aracı"** olarak konumlandırılır. |
| **K4** | **Faz 7 (`E5-Güvenlik`), Faz 9 (`E5-Taslak & HITL`)** | `results/e5/injection.json`, `results/e5/pii_eval.json`, `results/draft_quality.json`: Saldırı başarı/azaltma `%`'si, PII `FP/FN` ve sızıntı oranı, kör taslak puanları. | Sarmalamasız ham istem vs. `<evrak>` + `sanitizer`; maskesiz vs. maskeli girdi; değerlendiriciler arası uyum. | Saldırı başarı oranı sıfırlanmazsa **"tam koruma sağlar"** yerine **"saldırı başarı oranı %X'ten %Y'ye düşürülmüştür"** denir; HITL geçmiş verisi sınırlıysa **"insan denetimi güvenilirliği artırdı"** yerine **"insan denetimi mekanizması uygulanmıştır"** ifadesi kullanılır. |
