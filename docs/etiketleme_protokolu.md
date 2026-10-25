# Kamu Evrak Analizi — Veri Kümesi ve Operasyonel Etiketleme Protokolü (Faz 3)

> **Belge amacı:** JOINSSR makale hazırlığı kapsamında 18 sınıflı kamu evrakı değerlendirme kümesinin (`data/eval/classification/`) oluşturulması, tekilleştirilmesi (deduplikasyon), hukuki güncellik kontrolü, etiketleyiciler arası uyum (Cohen's $\kappa$) hesabı ve veri sızıntısı önleme (`dev`/`test` ayrımı) kurallarını üçüncü bir araştırmacının aynı etiketi üretebileceği açıklıkta tanımlamak (Hakem Raporu §4.2, §5.1, Tablo 7-E1, Tablo 12-P2).

---

## 1. Taksonomi ve 18 Sınıfın Operasyonel Tanımları (`app/core/taxonomy.py`)

Sistemdeki 18 evrak türü iki ana grupta toplanmaktadır: **(A) Düzenleyici İşlemler, Mevzuat ve Resmî Gazete Belgeleri** (9 sınıf) ve **(B) Kurum İçi / Kurumlar Arası İdari Yazışma, Başvuru ve Tespit Belgeleri** (9 sınıf).

### 1.1. Grup A — Düzenleyici İşlemler, Mevzuat ve Resmî Gazete Belgeleri

| Sınıf Kodu | Etiket | Operasyonel Tanım ve Normatif Kaynak | Zorunlu Yapısal / Biçimsel Ölçütler | Hariç Tutma (Negatif) Kuralı |
|---|---|---|---|---|
| `kanun` | **Kanun** | TBMM tarafından kabul edilen ve Cumhurbaşkanınca yayımlanan yasama işlemleri (asli kanunlar ve değişiklik kanunları). | `Kanun Numarası` (4 haneli sayı), `Kabul Tarihi`, `MADDE 1 –`, sonunda yürürlük ve yürütme (`"Bu Kanun hükümlerini Cumhurbaşkanı / Bakanlar Kurulu yürütür"`) maddeleri. | Bir kanuna dayanılarak çıkarılan ücret tarifeleri (`HMK Tanık Ücret Tarifesi` vb.) `kanun` değil, `teblig` olarak etiketlenir. |
| `kararname` | **Kararname** | Anayasa m. 104/17 uyarınca çıkarılan **Cumhurbaşkanlığı Kararnameleri (CBK)** ve yürürlükte kalan **Kanun Hükmünde Kararnameler (KHK)**. | Başlıkta `Cumhurbaşkanlığı Kararnamesi` (`Kararname Numarası: 1..170+`) veya `Kanun Hükmünde Kararname` (`KHK/375` vb.); madde/bölüm normatif yapısı. | Birel atama, kamulaştırma, tarife kontenjanı veya milletlerarası anlaşma onayına ilişkin `Cumhurbaşkanı Kararı` (`Karar Sayısı: 8000+`) `kararname` **değildir** (`karar` sınıfıdır). |
| `karar` | **Karar** | Cumhurbaşkanı kararları (`Karar Sayısı: ...`), bakanlık/düzenleyici kurul kararları (EPDK, HSK, Rekabet Kurulu, BDDK) ve yüksek yargı kararları (AYM, Yargıtay, Danıştay). | `Cumhurbaşkanı Kararı`, `Kurul Kararı`, `Esas Sayısı / Karar Sayısı` veya `"… karar verilmiştir."` hüküm fıkrası. | Normatif teşkilat/kadro düzenlemesi yapan `Cumhurbaşkanlığı Kararnamesi` `karar` değil, `kararname` sınıfıdır. |
| `yonetmelik` | **Yönetmelik** | Cumhurbaşkanı, bakanlıklar ve kamu tüzel kişilerince (üniversiteler, belediyeler, kurullar) kendi görev alanlarını ilgilendiren kanunların ve CBK'ların uygulanmasını sağlamak üzere çıkarılan düzenleyici işlemler (Anayasa m. 124). | Başlıkta `Yönetmelik` veya `Yönetmeliği`; `Amaç`, `Kapsam`, `Dayanak`, `Tanımlar` bölümleri ve numaralı `MADDE` dizisi. | Alt düzey uygulama/hesaplama tebliğleri (`teblig`) ve yalnızca kurum içi çalışma ilkelerini düzenleyen yönergeler (`yonerge`) hariçtir. |
| `teblig` | **Tebliğ** | Bir kanun, kararname veya yönetmeliğin uygulanma ayrıntılarını, parasal sınırlarını, kota/tarife cetvellerini veya teknik standartlarını açıklayan düzenleyici metinler. | Başlıkta `Tebliğ`, `Tebliği` (`Seri No` / `Sıra No`) veya bakanlıkça yayımlanan resmi ücret/gider `Tarifesi`. | Kurum içi bilgilendirme yazıları (`bilgilendirme`) veya genelgeler (`genelge`) hariçtir. |
| `genelge` | **Genelge** | Mevzuatın uygulanmasında birlik sağlamak, tedbirleri hatırlatmak veya idari işleyişe yön vermek üzere Cumhurbaşkanlığı, bakanlık veya üst makamlarca tüm birimlere/kurumlara gönderilen emir ve talimatlar. | `Genelge` başlığı veya `2024/7`, `2025/... Sayılı Genelge` numarası; tüm teşkilata/kurumlara hitap ve bağlayıcı uygulama talimatı. | Tek bir birime veya somut bir olaya ilişkin rutin üst yazı (`resmi_yazi`) veya salt duyuru (`bilgilendirme`) hariçtir. |
| `yonerge` | **Yönerge** | Bir yönetmeliğe veya üst mevzuata dayanılarak kurum içi çalışma usul ve esaslarını, görev dağılımını veya süreç adımlarını ayrıntılandıran metinler. | Başlıkta `Yönerge`, `Yönergesi` veya `Çalışma Usul ve Esasları`; `Amaç, Kapsam, Dayanak` + iç işleyiş maddeleri (Resmî Gazete'de yayımlanması zorunlu olmayan iç düzenleyici metin). | Resmî Gazete'de yayımlanan yönetmelik (`yonetmelik`) ve tebliğ (`teblig`) metinleri hariçtir. |
| `ilan` | **İlan** | Resmî Gazete *İlân Bölümü* veya kamu kurumlarınca yayımlanan ihale, taşınmaz satışı/kiralaması (`2886`/`4734` sayılı Kanun), personel/akademik kadro alımı ve yargı tebligat ilanları. | `İLAN` / `İLÂN`, `TAŞINMAZ SATILACAKTIR`, `İHALE İLANI`, `Mahkemesinden:`, ihale tarihi/saati, muhammen bedel, geçici teminat veya son başvuru tarihi bilgileri. | Kurum içi duyuru yazıları (`bilgilendirme`) hariçtir. |
| `sozlesme` | **Sözleşme** | Kamu kurumlarının taraf olduğu mal/hizmet/yapım alımı sözleşmeleri (`4735` sayılı Kanun), kurumlar arası iş birliği protokolleri, mutabakat zabıtları ve milletlerarası anlaşma metinleri. | `Taraflar`, `Sözleşmenin Konusu ve Bedeli`, `Süre`, `Karşılıklı Yükümlülükler`, `Uyuşmazlıkların Çözümü` ve çok taraflı imza bloğu. | Sözleşmeyi ekinde gönderen tek taraflı üst yazı (`resmi_yazi`) hariçtir. |

---

### 1.2. Grup B — Kurum İçi / Kurumlar Arası İdari Yazışma, Başvuru ve Tespit Belgeleri

| Sınıf Kodu | Etiket | Operasyonel Tanım | Zorunlu Yapısal / Biçimsel Ölçütler | Hariç Tutma (Negatif) Kuralı |
|---|---|---|---|---|
| `dilekce` | **Dilekçe** | Gerçek veya tüzel kişilerce `3071` sayılı Dilekçe Hakkı Kanunu veya `4982` sayılı Bilgi Edinme Hakkı Kanunu kapsamında bir kamu kurumuna sunulan bireysel başvuru, izin, düzeltme veya bilgi edinme yazısı. | Kurum makamına hitap (`"... Müdürlüğüne / Başkanlığına"`), birinci tekil/çoğul şahıs anlatımı, `"Gereğini arz ederim"` kapanışı; başvurucu Ad-Soyad, T.C. Kimlik (anonim), adres ve imza bloğu. | İçeriğin ana amacı bir idari eylem/işlem veya personel kusurundan yakınma/ihbar/itiraz ise `dilekce` değil, `sikayet` olarak etiketlenir. |
| `sikayet` | **Şikâyet** | Vatandaş veya personel tarafından bir kamu hizmetindeki aksaklık, mağduriyet, hukuka aykırılık, görevi ihmal veya idari işleme itiraz amacıyla sunulan şikâyet/ihbar başvurusu. | Somut bir mağduriyet, kusur, ihmal veya haksızlık iddiası; inceleme/soruşturma/mağduriyet giderimi talebi. | Herhangi bir kusur/mağduriyet iddiası içermeyen rutin izin, belge veya bilgi talebi `dilekce` sınıfıdır. |
| `resmi_yazi` | **Resmî Yazı** | Kamu kurum ve kuruluşları arasında *Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik* uyarınca gönderilen standart üst yazı, belge/dosya iletimi veya işlem cevabı. | `T.C.` başlığı, kurum/birim adı, `Sayı:`, `Konu:`, muhatap kurum, varsa `İlgi:`, resmî kapanış (`"arz ederim"` / `"rica ederim"` / `"arz ve rica ederim"`). | Ana işlevi bütçe/ödenek/malzeme istemekse `talep_yazisi`, hukuki/teknik mütalaa sormaksa `gorus_sorma`, salt duyuru iletmekse `bilgilendirme` seçilir. |
| `talep_yazisi` | **Talep Yazısı** | Bir kamu biriminin veya kurumun başka bir birim/kurumdan ödenek aktarımı, kadro/personel görevlendirmesi, taşınır/donanım tahsisi veya teknik destek istemesini konu alan resmî yazı. | Resmî yazı başlığı (`Sayı:`, `Konu:`) + somut kaynak/ödenek/tahsis/temin talebi ve gerekçesi (`"... tahsis edilmesi"`, `"... temini hususunda"`). | Vatandaşın bireysel dilekçesi (`dilekce`) veya yalnızca hukuki yorum soran yazı (`gorus_sorma`) hariçtir. |
| `bilgilendirme` | **Bilgilendirme Yazısı** | Karşı kurum veya birimden herhangi bir onay, görüş veya kaynak tahsisi talep etmeksizin; tamamlanan bir işlemi, istatistiği, etkinlik takvimini veya değişikliği bildiren yazı. | Resmî yazı formatı + eylem beklentisi olmaksızın bilgi sunumu (`"Bilgilerinize arz/rica ederim"`, `"bilgi edinilmesi hususunda"`). | Bağlayıcı genel emir/talimat içeriyorsa `genelge`, işlem/tahsis istiyorsa `talep_yazisi` seçilir. |
| `gorus_sorma` | **Görüş Sorma** | Uygulamada karşılaşılan mevzuat tereddüdü, sözleşme taslağı veya teknik/idari bir konuda Hukuk Müşavirliği, Strateji Geliştirme veya uzman bakanlıktan görüş (mütalaa) talep eden yazı. | Uyuşmazlık veya tereddüt konusu mevzuat maddesinin özeti + `"görüşünüzün bildirilmesi"`, `"mütalaa edilmesi"`, `"değerlendirilerek Başkanlığımıza bildirilmesi"` ifadesi. | Görüş istemeyip doğrudan ödenek/malzeme talep eden yazılar (`talep_yazisi`) hariçtir. |
| `kurum_ici` | **Kurum İçi Yazışma** | Aynı kurum çatısı altındaki daire başkanlıkları, şube müdürlükleri veya personel arasında yürütülen iç talimat, nöbet/görev dağılımı, hizmet içi koordinasyon notu ve iç müzekkere. | Kurum dışına çıkmayan muhatap (`"... Şube Müdürlüğüne"`, `"Birim Personeline"`), iç işleyiş konusu, kurum içi imza bloğu. | Kurumlar arası (bakanlık ↔ valilik/belediye/üniversite) yazışmalar `resmi_yazi` (veya alt türü) olarak etiketlenir. |
| `rapor` | **Rapor** | Denetim, inceleme, soruşturma, teknik değerlendirme veya dönemsal faaliyet sonuçlarını yapılandırılmış başlıklar, bulgular ve önerilerle sunan belge. | `RAPOR` başlığı veya `1. Giriş / Amaç`, `2. İnceleme ve Bulgular`, `3. Değerlendirme ve Sonuç / Öneriler` bölümleri; hazırlayan uzman/müfettiş/komisyon imzası. | Yalnızca anlık bir olayı veya toplantı kararlarını tespit eden imzalı kısa metinler `tutanak` sınıfıdır. |
| `tutanak` | **Tutanak** | Bir toplantı, komisyon oturumu, ihale zarf açımı, mal/evrak teslim-tesellümü veya maddi bir olayın/durumun katılımcılarca yerinde tespit edilip imza altına alındığı belge. | `TUTANAK` başlığı; tarih, saat, yer, katılımcılar/gündem veya tespit edilen maddi olgu; `"İşbu tutanak ... nüsha olarak düzenlenmiş ve imza altına alınmıştır"` kapanışı ve çoklu imza bloğu. | Analitik değerlendirme ve uzun dönemli politika önerisi sunan inceleme belgeleri (`rapor`) hariçtir. |

---

## 2. Kritik Sınır Çiftleri İçin Karar Ağacı (Hakem §4.2)

Etiketleme sırasında iki sınıf arasında tereddüt oluştuğunda aşağıdaki **4 öncelik kuralı** sırasıyla uygulanır:

### Kural 1 — `karar` ↔ `kararname` Ayrımı
1. Belge **Anayasa m. 104/17** kapsamında çıkarılmış bir **Cumhurbaşkanlığı Kararnamesi** (`Cumhurbaşkanlığı Kararnamesinin Sayısı: 1..170+`) veya **KHK** (`KHK/375` vb.) ise ve bakanlık/kurum teşkilatı, kadro ihdası veya genel/soyut norm ihdas ediyorsa → **`kararname`**.
2. Belge **Cumhurbaşkanı Kararı** (`Karar Sayısı: 8000–11000+` — ör. acele kamulaştırma, ithalat rejimi ek kararı, milletlerarası anlaşma onayı, atama kararı), **Kurul Kararı** (HSK, EPDK, Rekabet Kurulu) veya **Yüksek Yargı Kararı** (AYM, Yargıtay) ise → **`karar`**.

### Kural 2 — Karma Başlıklarda "İhdas Edici Ana İşlem (Head-Noun)" Kuralı (`kanun` ↔ `kararname` ↔ `teblig`)
Bir mevzuat başlığı birden fazla mevzuat türünün adını içerebilir. Bu durumda **metnin değiştirdiği veya dayandığı mevzuat değil, metnin kendisinin hukuki türü (başlığın sonundaki ana işlem terimi ve kabul makamı)** esas alınır:
- *Örnek 1 (`rg_2025-07-14_1`):* `"7553 Bazı Kanunlarda ve 375 Sayılı Kanun Hükmünde Kararnamede Değişiklik Yapılmasına Dair Kanun"` → İçinde `"Kararnamede"` geçmesine rağmen belge TBMM tarafından kabul edilen 7553 sayılı bir **Kanun**'dur → **`kanun`** (`scraper.py`'deki alt-dizgi hatası düzeltilmiştir).
- *Örnek 2 (`rg_2024-10-23_6`):* `"Hukuk Muhakemeleri Kanunu Tanık Ücret Tarifesi"` → İçinde `"Kanunu"` geçmesine rağmen belge bir kanun değil, HMK uyarınca yayımlanan ikincil bir tarife/tebliğdir → **`teblig`** (`scraper.py`'deki alt-dizgi hatası düzeltilmiştir).
- *Örnek 3:* `"… Uygulama ve Araştırma Merkezi Yönetmeliği"` → Türkçe iyelik eki ve ünsüz yumuşaması (`k → ğ`) nedeniyle `"yönetmelik"` alt-dizgisi eşleşmese dahi belge bir yönetmeliktir → **`yonetmelik`** (`scraper.py`'de `diger` altında kalan `101` yönetmelik düzeltilmiştir).

### Kural 3 — İdari Yazışmalarda "Baskın Söz Eylemi (Dominant Speech Act)" Kuralı
Kurumlar arası ve kurum içi yazışmalarda (`resmi_yazi`, `talep_yazisi`, `bilgilendirme`, `gorus_sorma`, `kurum_ici`, `dilekce`, `sikayet`) biçimsel şablon (`Sayı:`, `Konu:`) ortak olabilir. Etiketleme şu sırayla yapılır:
1. Belge gerçek/tüzel kişinin kuruma yaptığı bireysel başvuru mu?
   - Evet ve idari kusur/mağduriyet/personel şikâyeti/itiraz bildiriyorsa → **`sikayet`**.
   - Evet ve rutin talep/izin/bilgi edinme/başvuru ise → **`dilekce`**.
2. Belge aynı kurumun iç birimleri/personeli arasında mı (`Daire Başkanlığı → Şube Müdürlüğü / Personel`)?
   - Evet ve düzenleyici yönerge/tutanak/rapor değilse → **`kurum_ici`**.
3. Belge kurumlar arası resmî yazı ise son paragraftaki **baskın söz eylemine** bakılır:
   - Hukuki/teknik/mevzuat tereddüdü hakkında mütalaa/görüş isteniyorsa → **`gorus_sorma`**.
   - Ödenek, bütçe, personel, malzeme, taşınmaz tahsisi/temini isteniyorsa → **`talep_yazisi`**.
   - Karşı taraftan işlem/tahsis beklenmeksizin yalnızca bir durum/veri/takvim bildiriliyorsa → **`bilgilendirme`**.
   - Genel evrak iletimi, cevabi üst yazı veya koordinasyon yazısı ise → **`resmi_yazi`**.

---

## 3. Veri Kaynağı, Deduplikasyon ve Kalite Denetimi (Hakem §4.2)

### 3.1. `app/data/scraped/documents.json` (956 Ham Kayıt) Denetim Sonuçları
Mevcut 956 ham kaydın tamamı `experiments/build_eval_dataset.py` ile denetlenmiş ve şu kalite/tekilleştirme bulguları kayıt altına alınmıştır:
1. **Tam Sayı PDF Sarmalayıcıları (`title == "PDF Görüntüle"`):** `107` kayıt, tekil bir mevzuat belgesi olmayıp ilgili günün Resmî Gazete tam sayı PDF metnidir. Bu kayıtlar doğrudan tekil sınıf havuzundan çıkarılmış; ancak içlerindeki **`İLÂN BÖLÜMÜ`** bloklarından gerçek ihale, taşınmaz satışı ve yargı ilanları (`ilan` sınıfı için 20 benzersiz örnek) ayrıştırılmıştır.
2. **HTTP 404 ve Boş Arama Formu Kayıtları:** `6` adet `"404 - Sayfa Bulunamadı"` kaydı ile `6` adet `mevzuat.gov.tr` boş arama formu (`"T.C. CUMHURBAŞKANLIĞI MEVZUAT BİLGİ SİSTEMİ Mevzuat Türü..."`) temizlenmiştir.
3. **Bozuk PDF Fontu ve Kırpılmış Metinler:** İlk 500 karakterinde yoğun kontrol karakteri (`\x10\x07...`) barındıran bozuk PDF çıkarımları ve `< 150` karakterlik başlık koçanları elenmiştir.
4. **SHA-256 İçerik Tekilleştirmesi (Deduplikasyon):** Aynı PDF dosyasında birden fazla Anayasa Mahkemesi kararının yayımlandığı günlerde `scraper.py`'nin aynı PDF gövdesini farklı başlıklarla 6–16 kez kaydetmesi ve `mv_657` ile `mv_kanun_657` gibi mükerrer kanun çekimleri, normalize edilmiş gövde metninin `SHA-256` özetiyle tekilleştirilmiştir.

### 3.2. 18 Sınıf × 20 Örnek (`N = 360`) Küme Bileşimi
- **Toplam Örnek Sayısı:** `360` belge (18 sınıfın her birinde tam **20 benzersiz örnek**).
- **Kaynak Türü (`origin_type`) Şeffaflığı:**
  - `scraped_official`: Resmî Gazete ve Mevzuat Bilgi Sistemi'nden elde edilen gerçek mevzuat ve ilan metinleri (`kanun`, `yonetmelik`, `teblig`, `karar`, `ilan` sınıflarının tamamı ile `kararname` ve `genelge` sınıflarındaki mevcut gerçek örnekler).
  - `curated_anonymized`: KVKK ve kurum gizliliği nedeniyle kamuya açık olmayan kurum içi/kurumlar arası idari yazışma sınıfları (`dilekce`, `resmi_yazi`, `talep_yazisi`, `bilgilendirme`, `gorus_sorma`, `sikayet`, `kurum_ici`, `rapor`, `tutanak`, `yonerge`, `sozlesme` ve tamamlayıcı `genelge`/`kararname` örnekleri) için 2646 sayılı Resmî Yazışma Yönetmeliği ve 3071 sayılı Kanun standartlarına uygun olarak yapılandırılmış, **~%35 oranında zorlayıcı/sınır (boundary) örnekler** içeren anonimleştirilmiş metinler.

---

## 4. Hukuki Güncellik, Etiketleyici Uyumu ve Veri Sızıntısı Önleme

1. **Hukuki Güncellik Kontrolü (`legal_status` — Hakem §4.2, §5.1):**
   Her örnekte `legal_status` (`"yururlukte"`, `"degisiklik_metni"`, `"mulga_veya_eski_surum"`, `"idari_yazisma_uygulanmaz"`) ve `legislation_version_note` alanı zorunlu tutulmuştur. Böylece asli mevzuat ile değişiklik metinleri ve yürürlükten kalkmış/değiştirilmiş KHK hükümleri açıkça işaretlenmiştir.
2. **Etiketleme Sağlayıcılığı ve Sınırı (Hakem §4.2):**
   Veri kümesi **tek bir araştırmacı tarafından** etiketlenmiştir; **bağımsız ikinci bir insan etiketleyici kullanılmamıştır.** `curated_templates` kaynaklı 250 örnekte etiket, her şablonun ilgili sınıfı örneklemek üzere yazılmasıyla tanım gereği (by construction) belirlenmiştir. Bu nedenle **gerçek bir değerlendiriciler arası güvenilirlik (Cohen's $\kappa$) raporlanamaz.** (`annotator_primary` alanı nihai `ground_truth` ile birebir aynıdır; `annotator_secondary` ise kod tarafından üretilen otomatik/sezgisel bir tutarlılık katmanıdır — ikisi arasındaki uyum gerçek bir etiketleyici anlaşması değildir ve bu projenin önceki sürümünde yanlışlıkla "inter-annotator κ=0.8235" olarak raporlanmıştı; bu değer geçersizdir.) `data/eval/classification/dedup_and_split_report.json` artık yalnızca tek-etiketleyici olgusunu ve otomatik katman uyum oranını kaydeder. Tek etiketleyici sınırı `paper/limitations_notes.md` içinde açık bir geçerlilik tehdidi olarak belirtilmiştir.
3. **Veri Sızıntısı Önleme (`dev` / `test` Ayrımı — Hakem §4.2):**
   - Sabit `seed = 42` ile her sınıftaki 20 örnek tabakalı (stratified) olarak bölünmüştür:
     - **Geliştirme / Eğitim Kümesi (`dev.json`):** Sınıf başına `6` örnek, toplam **`108` belge (%30)**. Prompt doğrulama, kural kalibrasyonu ve Faz 5'teki klasik makine öğrenmesi (`TF-IDF + Linear SVM / Lojistik Regresyon`) modellerinin eğitimi yalnızca bu küme üzerinde yapılır.
     - **Nihai Değerlendirme Kümesi (`test.json`):** Sınıf başına `14` örnek, toplam **`252` belge (%70)**. Faz 4 (`E1`) ve Faz 5 (`E2`) nihai metrikleri yalnızca bu ayrılmış küme üzerinde ölçülür; prompt veya kural geliştirme aşamasında `test.json` sonuçlarına bakılarak geriye dönük ayar yapılmaz.
