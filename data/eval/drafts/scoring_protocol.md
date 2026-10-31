# Taslak Kalitesi Kör Puanlama Protokolü (Faz 9 — E5 taslak kalitesi)

> **Durum:** Puanlama **insan uzman** gerektirir; bu dosya doldurulmaya hazır protokoldür. Puanlar `data/eval/drafts/scores_*.json` olarak kaydedilir (bkz. §4 şema). Hakem §5.4: İnsan onayı mekanizması tek başına kaliteyi kanıtlamaz; ölçütler önceden tanımlanmalı, kör puanlama ve puanlayıcılar arası uyum raporlanmalıdır.

## 1. Örneklem
- **30–50 belge** (mümkünse gerçek resmî belgeler + temsilî idari örnekler karışık; `data/eval/classification/test.json` kaynaklı olabilir).
- Her belge için `DraftAgent` ile üretilen resmî yazı taslağı puanlanır.
- **Körleme:** Puanlayıcılar, taslağı üreten model/sürüm bilgisini ve birbirlerinin puanlarını görmez. Taslaklar karışık sırada sunulur.

## 2. Puanlayıcılar
- **En az 2 bağımsız uzman** (hukuk/idari yazışma bilgisi olan). Tek puanlayıcı mümkünse bu bir sınırlılık olarak yazılır.
- Puanlayıcılar arası uyum: ordinal ölçütler için **Krippendorff's α** veya ağırlıklı **Cohen's κ** raporlanır.

## 3. Ölçütler (her biri 1–5 Likert; önceden tanımlı)
| Kod | Ölçüt | 1 (kötü) | 5 (iyi) |
|---|---|---|---|
| `mevzuata_uygunluk` | Mevzuata ve usule uygunluk | aykırı/yanıltıcı | tam uygun |
| `olgusal_dogruluk` | Evrak içeriğiyle olgusal tutarlılık | hatalı/uydurma | tümüyle doğru |
| `kapsayicilik` | Gerekli unsurların kapsanması | eksik | eksiksiz |
| `dil_bicim` | Resmî dil ve biçim | bozuk | kusursuz |

Ek ikili/sayısal ölçütler (0/1 veya sayım):
- `desteklenmeyen_iddia_sayisi`: Taslakta kaynakça/evrakla desteklenmeyen ifade sayısı (düşük = iyi).
- `pii_sizintisi`: Taslakta maskelenmemiş kişisel veri var mı (0/1; `experiments/e5_pii_eval.py` ölçütleriyle çapraz kontrol).

## 4. Puanlama kaydı şeması (`data/eval/drafts/scores_<rater>.json`)
```json
{
  "rater_id": "uzman_1",
  "blinded": true,
  "scores": [
    {
      "draft_id": "<belge/taslak kimliği>",
      "mevzuata_uygunluk": 1,
      "olgusal_dogruluk": 1,
      "kapsayicilik": 1,
      "dil_bicim": 1,
      "desteklenmeyen_iddia_sayisi": 0,
      "pii_sizintisi": 0,
      "notlar": ""
    }
  ]
}
```

## 5. Raporlanacak sonuçlar (puanlama sonrası)
- Ölçüt başına ortalama ± standart sapma ve medyan; desteklenmeyen iddia oranı; PII sızıntı oranı.
- Puanlayıcılar arası uyum (α/κ).
- Örneklem küçükse (n<30) "ön bulgu" olarak işaretlenir; kesin genelleme yapılmaz.
