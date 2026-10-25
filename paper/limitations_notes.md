# Makale Sınırlılıklar (Limitations / Threats to Validity) Taslağı

> **Kaynak:** JOINSSR Ön Hakem Değerlendirme Raporu (§2, §3.1, §3.5, §5.1–§5.5, §6, §8)
> **Amaç:** Makalenin *"Bulgular ve Tartışma"* ve *"Sonuçlar / Sınırlılıklar"* bölümlerinde açık, şeffaf ve bilimsel ölçülülükle raporlanacak sınırlılık maddelerini tanımlamak.
> **Temel İlke (Hakem §9):** Deney sonuçları bir iddiayı tam desteklemiyorsa sonuç parlatılmaz; iddia kanıtın kapsamına daraltılır ve kalan boşluk sınırlılık olarak açıkça yazılır.

---

## 1. Hakem Raporu §8'deki 5 Temel Sınırlılık Maddesi

### Sınırlılık 1 — Sınıflandırma Kapsamı ve Örneklem Büyüklüğü (§3.1, §8.1)
- **Hakem tespiti:** İlk mevcut benchmark'ın 54 belge ve 6 kategoriden (`genelge`, `tebliğ`, `yönetmelik`, `kanun`, `karar`, `kararname`) oluşması; elde edilen `Macro-F1 = 0.935` ve `%92.6` doğruluk (`50/54`, %95 Wilson GA: `~%82.4–%97.1`) sonucunun sistem taksonomisindeki (`app/core/taxonomy.py`) 18 evrak türünün tamamına doğrudan genellenememesi.
- **Deneysel karşılık (Faz 3 & Faz 4 — E1):** 18 sınıfı kapsayan genişletilmiş değerlendirme kümesi kurulacak ve her sınıf için precision, recall, F1 ile bootstrap güven aralığı raporlanacaktır.
- **Makalede kalıcı olarak belirtilecek sınırlılık:** Genişletilmiş kümede dahi bazı nadir idari evrak sınıflarında (ör. `tüzük`, `müzekkere`, `mazbata` veya kurum içi özel yazışmalar) kamuya açık örnek sayısı doğal olarak daha sınırlıdır; bu nedenle sınıf başı örneklem büyüklüğü ve güven aralıkları açıkça verilerek aşırı genellemeden kaçınılmıştır.

### Sınırlılık 2 — Veri Dağılımı ve Alan Kayması (Domain Shift) (§4.2, §8.2)
- **Hakem tespiti:** Kamuya açık mevzuat ve Resmî Gazete metinlerinin, vatandaşlardan veya alt birimlerden gelen gerçek dilekçe, şikâyet, tutanak ve taranmış (OCR) fiziksel evraklarla aynı dilsel dağılımı ve gürültü profilini temsil etmeyebileceği.
- **Deneysel karşılık (Faz 3):** Değerlendirme kümesinde kaynak çeşitliliği, metin uzunluğu dağılımı ve anonimleştirilmiş/sentetik idari yazışma örneklerinin kuralları `docs/etiketleme_protokolu.md` içinde belgelenecektir.
- **Makalede kalıcı olarak belirtilecek sınırlılık:** KVKK ve kurum mahremiyeti gereği gerçek vatandaş başvuruları ve kurum içi gizli yazışmalar açık veri kümesine dahil edilememektedir. Kamuya açık resmî metinler ile anonimleştirilmiş/temsilî idari evraklar üzerinde elde edilen sonuçlar, el yazısı, düşük çözünürlüklü faks/tarama (OCR hatası) veya biçimsiz vatandaş dilekçeleri içeren gerçek kurum ortamlarında ek doğrulama gerektirir.

### Sınırlılık 3 — Model, Prompt, Bağlam Uzunluğu ve Mevzuat Güncelliği Duyarlılığı (§5.1, §8.3)
- **Hakem tespiti:** LLM tabanlı sınıflandırma, mevzuat eşleştirme ve taslak üretiminin kullanılan model sürümüne (`gemma4:12b`), nicemleme düzeyine (`Q4_K_M`), sistem/kullanıcı istemlerine (prompt), bağlam penceresi uzunluğuna (`num_ctx=16384`) ve örnekleme sıcaklığına (`temperature=0.3`) duyarlı olması; ayrıca RAG indeksindeki mevzuatın yürürlük/değişiklik/ilga durumunun dinamik hukuki geçerliliği tam garanti etmemesi.
- **Deneysel karşılık (Faz 5, Faz 6, Faz 8):** Tüm model, quantization ve prompt ayarları sabitlenerek (`docs/olcum_protokolu.md`) raporlanacak; RAG retrieval kalitesi (Recall@5, MRR@10, nDCG@10) ve kaynak atfı doğruluğu ayrı ölçülecektir.
- **Makalede kalıcı olarak belirtilecek sınırlılık:**
  1. Farklı quantization düzeyleri (ör. `Q8_0`, `FP16`) veya farklı yerel model aileleri (`qwen3`, `llama3` vb.) arasında çıktı biçimi ve karar sınırları değişebilir.
  2. Statik bir tarihte indekslenen RAG mevzuat korpusu (`956` belge / `3056` parça), gerçek zamanlı mülga/değişiklik takibi yapan resmî bir hukuk bilgi sisteminin yerini tutmaz; üretilen yazı taslakları hukuki tavsiye niteliği taşımaz ve yalnızca ön hazırlık amacı taşır.

### Sınırlılık 4 — Yerel Çalışma, Güvenlik ve KVKK Uyum Sınırları (§2, §5.2, §5.3, §8.4)
- **Hakem tespiti:** Yerel model (`Ollama`) kullanmanın dış bulut API'lerine veri aktarımı riskini azaltması, ancak tek başına tam kurum güvenliğini, istem enjeksiyonu (prompt injection) bağışıklığını veya KVKK uyumunu garanti etmemesi.
- **Deneysel karşılık (Faz 7 — E5):** Adversarial prompt injection örnekleriyle saldırı azaltma oranı ve etiketli PII örnekleriyle yanlış pozitif / yanlış negatif oranları ile taslağa sızıntı oranı deneysel olarak ölçülecektir.
- **Makalede kalıcı olarak belirtilecek sınırlılık:**
  1. İçeriğin yerel kalması; `LLM_API_BASE` ayarının yerel uç noktaya (`localhost:11434`) bağlı olmasına ve sunucu ağ politikasının dış veri akışını engellemesine bağlıdır.
  2. Uygulama tarafından tutulan analiz geçmişi (`data/history/`), denetim ve uygulama logları (`data/logs/`) ile yedeklerin (`data/backups/`) saklama süresi, şifrelenmesi ve rol tabanlı erişim denetimi kurumun idari/teknik KVKK politikalarıyla tamamlanmalıdır.
  3. `<evrak>` etiket sarmalama (`app/core/sanitizer.py`) ve düzenli ifade/sağlama tabanlı PII maskeleme deterministik savunma katmanlarıdır; karmaşık dolaylı istem enjeksiyonlarına veya standart dışı yazılmış kişisel verilere karşı `%100` koruma iddiası taşımaz.

### Sınırlılık 5 — Değerlendirme Kümesi, Uzman Puanlaması, Yazılım Testleri ve Donanım Genellenebilirliği (§3.5, §5.4, §5.5, §6, §8.5)
- **Hakem tespiti:** Sentetik/anonim veri kullanımı, sınırlı sayıda etiketleyici/uzman puanlaması, tek bir donanım profilinde (RTX 5070 12GB VRAM) yapılan performans ölçümleri, sahte LLM kullanan 479 yazılım testinin kapsamı ve ajan mimarisinin sınırları.
- **Deneysel karşılık (Faz 3, Faz 6B, Faz 8, Faz 9):** Etiketleyici/puanlayıcı uyumu (veya tek etiketleyici sınırı), `ReasoningAgent` ablation sonuçları, soğuk/sıcak gecikme dağılımları (medyan, p95, GA) ve insan denetimi (HITL) kayıtları açıkça raporlanacaktır.
- **Makalede kalıcı olarak belirtilecek sınırlılık:**
  1. **Yazılım doğrulama vs. model kalitesi (§3.5):** Depodaki `479` otomatik `pytest` testi sahte (mock) LLM kullanmakta olup yalnızca yazılım mühendisliği, API sözleşmesi ve hata toleransı davranışını doğrular; dil modelinin anlamsal başarımına kanıt oluşturmaz.
  2. **Mimari kapsam (§5.5):** Sistem, otonom planlama veya dinamik görev müzakeresi yapan çok etmenli bir sistem değil, `OrchestratorAgent` denetiminde sabit aşamalı ve paralel yürütmeli **ajan tabanlı çok aşamalı bir pipeline**'dır.
  3. **Donanım ve eşzamanlılık sınırı (§6):** Bildirilen gecikme ve VRAM değerleri tek GPU'lu (`12 GB VRAM`, `LLM_MAX_CONCURRENT_REQUESTS=2`) iş istasyonu profiline aittir; yalnızca CPU kullanılan ortamlarda veya yüksek eşzamanlı kurumsal yük altında kuyruk süreleri doğrusal olmayan biçimde artacaktır.
  4. **Uzman değerlendirmesi ve HITL (§5.4):** Taslak kalitesi puanlaması sınırlı sayıda değerlendirici ve örneklem (`n=30–50`) üzerinden yürütülmekte olup, gerçek kurumsal kullanımda uzun dönemli memur onay/düzeltme davranışlarını ölçmek için saha çalışması gereklidir.

---

## 2. Makale Metni İçin Hazır Taslak Alt Bölüm (Faz 10'da Kullanılacak)

> *Aşağıdaki metin, Faz 4–9 deney sonuçlarından elde edilecek kesin sayılar (`[...]` alanları) eklendikten sonra makalenin "4.X Çalışmanın Sınırlılıkları ve Geçerliliğe Yönelik Tehditler" bölümüne doğrudan yerleştirilmek üzere hazırlanmıştır:*

### 4.X. Çalışmanın Sınırlılıkları ve Geçerliliğe Yönelik Tehditler (Threats to Validity)

Bu çalışmada sunulan tasarım ve deneysel bulgular değerlendirilirken beş temel sınırlılık dikkate alınmalıdır:

1. **Veri Kümesi Kapsamı ve Örneklem Büyüklüğü (İç ve Dış Geçerlilik):** Sistem taksonomisinde 18 evrak türü tanımlanmış olmakla birlikte, başlangıç pilot değerlendirmesi 6 mevzuat/evrak kategorisinde 54 belge (`Macro-F1 = 0.935`, doğruluk `%92.6`, %95 Wilson GA: `%82.4–%97.1`) ile sınırlıdır [Faz 4 tamamlandığında 18 sınıf sonuçları ve sınıf bazlı örneklem sayıları buraya eklenecektir]. Özellikle kamuya açık örnekleri nadir bulunan bazı idari yazışma türlerinde örneklem büyüklüğü sınırlı kalmakta, bu durum alt sınıflardaki güven aralıklarının genişlemesine yol açmaktadır.
2. **Veri Dağılımı ve Alan Kayması (Domain Shift):** Değerlendirmede kullanılan kamuya açık mevzuat ve resmî belge metinleri ile anonimleştirilmiş idari örnekler, kamu kurumlarına vatandaşlar tarafından sunulan serbest biçimli dilekçelerin, el yazısı belgelerin veya düşük kaliteli taramalardan kaynaklanan OCR gürültüsünün tüm dağılımını temsil etmemektedir. Dolayısıyla gerçek kurum içi evrak akışında gözlenecek başarım, kurumun belge profiline ve tarama kalitesine bağlı olarak farklılık gösterebilir.
3. **Model, İstem (Prompt) ve Mevzuat Güncelliği Duyarlılığı:** Sınıflandırma, içerik analizi ve taslak üretimi sonuçları; kullanılan yerel modelin mimarisine (`gemma4:12b`), nicemleme düzeyine (`Q4_K_M`), bağlam uzunluğuna (`16384` token), sıcaklık parametresine (`0.3`) ve sistem istemlerinin yapısına duyarlıdır. Ayrıca TF-IDF/BM25 tabanlı RAG bileşeni, indekslenen mevzuat korpusunun (`956` belge, `3056` parça) anlık görüntüsü üzerinde çalışmaktadır; mevzuattaki sonradan yürürlüğe giren değişikliklerin veya mülga hükümlerin otomatik hukuki geçerlilik denetimi kapsam dışıdır.
4. **Yerel İşleme, Güvenlik ve KVKK Sınırları:** Modelin yerel `Ollama` sunucusu üzerinde çalıştırılması, evrak metinlerinin üçüncü taraf bulut sağlayıcılarına gönderilmesi riskini ortadan kaldırmakla birlikte tek başına uçtan uca kurum güvenliği veya KVKK uyumu anlamına gelmez. Yerel gizlilik garantisi, `LLM_API_BASE` yapılandırmasının yerel ağla sınırlandırılmasına, dış ağ trafiğinin kurumsal güvenlik duvarıyla denetlenmesine ve uygulama tarafından oluşturulan analiz geçmişi (`data/history/`), log (`data/logs/`) ve yedek (`data/backups/`) dosyalarının erişim/saklama politikalarının doğru yapılandırılmasına bağlıdır. Benzer şekilde `<evrak>` etiketiyle sarmalama ve kural tabanlı PII maskeleme işlemleri saldırı ve sızıntı yüzeyini daraltan savunma katmanları olup mutlak bağışıklık iddiası taşımaz.
5. **Mimari Kapsam, Yazılım Testleri ve Donanım Genellenebilirliği:** Önerilen sistem, bağımsız planlama ve otonom görev devri yapan çok etmenli bir mimari değil, `OrchestratorAgent` yönetiminde çalışan **ajan tabanlı çok aşamalı bir pipeline**'dır. Depoda yer alan `479` otomatik yazılım testi sahte (mock) LLM ile yürütüldüğünden yalnızca yazılım bütünlüğünü ve hata toleransını doğrulamakta, modelin anlamsal çıktı kalitesini ölçmemektedir. Son olarak, raporlanan gecikme ve bellek tüketimi değerleri tek bir iş istasyonu GPU'su (`NVIDIA RTX 5070 12GB VRAM`, `LLM_MAX_CONCURRENT_REQUESTS=2`) üzerinde elde edilmiş olup, farklı donanım profillerinde ve yüksek eşzamanlı kullanıcı yüklerinde yeniden değerlendirilmelidir.
