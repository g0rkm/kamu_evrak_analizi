# E3 RAG Değerlendirme Kümesi ve Etiketleme Protokolü (`queries_and_qrels.json`)

Bu dizin, **FAZ 6 (Deney E3)** kapsamında Türk kamu mevzuatı RAG (Retrieval-Augmented Generation) alt sisteminin geri getirme (retrieval), kaynak izlenebilirliği (provenance) ve kapsam dışı sorgularda çekimser kalma (grounded abstention) başarımını ölçmek üzere oluşturulan değerlendirme veri kümesini içerir.

## 1. Veri Kümesi Özeti

- **Dosya:** `data/eval/rag/queries_and_qrels.json`
- **Toplam Sorgu Sayısı ($Q$):** `60`
  - **Kapsam İçi / Cevaplanabilir Sorgular ($Q_{\text{ans}}$):** `48` (indekslenen `3.056` mevzuat parçası / `956` belge içerisinde doğrudan normatif dayanağı bulunan sorular)
  - **Kapsam Dışı / Cevaplanamaz Sorgular ($Q_{\text{unans}}$):** `12` (indekste yer almayan kanunlar, yürürlüğe girmemiş kurgusal düzenlemeler veya kamu hukuku dışı özel hukuk/teknik konular)
- **Aday Havuzu (Pooling) ve Uzlaşma:**
  - 6 farklı geri getirme yönteminin (`R1`–`R6`) ilk 15 sonucu (`top-15`) ile kanun numarası/madde eşleşmelerinden oluşan toplam `851` `(sorgu, chunk_id)` çifti iki bağımsız değerlendirici kural seti (`Annotator A`: normatif madde/konu eşleşmesi; `Annotator B`: terim yoğunluğu ve başlık/madde doğrulaması) tarafından ikili (`ilgili >= 1` vs `ilgisiz = 0`) ve dereceli (`0, 1, 2`) olarak etiketlenmiştir.
  - **Değerlendiriciler Arası Uzlaşma (Cohen's $\kappa$):** $\kappa = 0.9863$ (`851` aday çift üzerinde).

## 2. Alaka Düzeyi Derecelendirme Ölçeği (Relevance Grading Rubric)

TREC / CLEF hukuki bilgi erişimi standartlarına uygun olarak 3 seviyeli derecelendirme kullanılmıştır:

| Derece | Etiket | Tanım |
|---|---|---|
| `2` | **Tam İlgili (Highly Relevant / Exact Provision)** | Sorguda sorulan hukuki kuralı, süreyi, yetkiyi veya istisnayı doğrudan düzenleyen kanun/CBK/yönetmelik maddesini içeren parça (`chunk`). |
| `1` | **Kısmen İlgili (Partially Relevant / Contextual)** | Aynı kanun veya düzenlemenin genel çerçevesini, tanımlarını veya bağlantılı hükümlerini içeren ancak sorunun spesifik cevabını tek başına tamamlamayan parça. |
| `0` | **İlgisiz (Non-Relevant)** | Sorgu konusuyla ilgisi olmayan, farklı bir mevzuata ait veya yalnızca şablon/başlık benzerliği taşıyan parça. |

*Not:* İkili (binary) geri getirme metriklerinde (`Recall@k`, `HitRate@k`, `MRR@10`) alaka eşiği $\text{grade} \ge 1$ olarak alınmış; sıralama kalitesi metriği `nDCG@10` hesabında ise $\text{gain} = 2^{\text{grade}} - 1$ ($\text{grade} \in \{0, 1, 2\}$) formülü kullanılmıştır.

## 3. Sorgu Kategorileri ve Dağılımı

| Kategori Kodu | Açıklama | Sorgu Sayısı | Örnek Mevzuat / Konu |
|---|---|---:|---|
| `kanun_maddesi` | Temel kamu kanunlarında spesifik madde/hüküm aramaları | 18 | 657 DMK, 4734 KİK, 5018 KMYKK, 2577 İYUK, 3071 Dilekçe K., 4982 Bilgi Edinme K., 6698 KVKK, 5326 Kabahatler K. |
| `cbk_teskilat` | Cumhurbaşkanlığı Kararnameleri ve idari teşkilat yetkileri | 10 | CBK-1, CBK-2, CBK-4, Devlet Denetleme Kurulu, Strateji ve Bütçe Başkanlığı |
| `ikincil_mevzuat` | Resmi Gazete'de yayımlanan yönetmelik, tebliğ ve kurul kararları | 12 | Resmi Yazışmalarda Uygulanacak Usul ve Esaslar, Disiplin Yönetmeliği, İhale Uygulama Yönetmelikleri |
| `vaka_senaryosu` | Kamu görevlisinin karşılaştığı somut idari işlem/süre senaryoları | 8 | Bilgi edinme cevap süresi, ihale şikayet süresi, disiplin savunma hakkı süresi, dilekçe incelenmeme halleri |
| `kapsam_disi` | İndekste bulunmayan mevzuat veya kurgusal idari düzenlemeler | 12 | 2029 Ulusal Kuantum İdare Kanunu, Uzay Madenciliği Ruhsat Yönetmeliği, Kripto Varlık Vergi Usul Tebliği vb. |

## 4. Dosya Şeması (`queries_and_qrels.json`)

```json
{
  "metadata": {
    "version": "1.0",
    "total_queries": 60,
    "answerable_queries": 48,
    "unanswerable_queries": 12,
    "cohens_kappa": 0.9863,
    "total_judged_pairs": 851
  },
  "queries": [
    {
      "query_id": "Q01",
      "category": "kanun_maddesi",
      "is_answerable": true,
      "query_text": "3071 sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun'a göre dilekçelerde bulunması zorunlu şartlar nelerdir ve hangi dilekçeler incelenemez?",
      "target_law_no": "3071",
      "qrels": {
        "12": 2,
        "13": 2,
        "14": 1
      }
    }
  ]
}
```
