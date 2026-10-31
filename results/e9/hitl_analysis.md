# Faz 9 — İnsan Denetimi (Human-in-the-Loop) Analizi

**Kapsam:** FAZ 9 (`MAKALE_HAZIRLIK_PLANI.md` §5.4) · **Kaynak:** `data/history/`

## 1. Mekanizma (uygulanmış)
Sistem, her analiz kaydında kalıcı bir **inceleme durumu** tutar ([`app/models/review.py`](../../app/models/review.py)); memur kararları `PATCH /api/history/{id}/review` ile kaydedilir:

| Alan | İzinli değerler |
|---|---|
| `review.draft_status` | `pending`, `approved`, `edited`, `rejected` |
| `review.routing_status` | `pending`, `approved`, `changed` |

`HistoryRepository.stats()` bu kararların dağılımını (`by_draft_status`) toplar.

## 2. Ampirik durum (DÜRÜST)
`data/history/` içinde şu an **2 kayıt** vardır ve **ikisinde de** `draft_status = pending`, `routing_status = pending`'dir.

| Metrik | Değer |
|---|---:|
| Toplam kayıt | 2 |
| İnsan tarafından incelenmiş (≠ pending) | **0** |
| Onay / düzenleme / ret oranı | hesaplanamaz (veri yok) |

**Sonuç (Hakem §5.4):** İnsan denetimi **mekanizması uygulanmıştır** (onay/düzenle/ret + yönlendirme onay/değiştir, sunucuda kalıcı, API ile). Ancak gerçek memur karar verisi bulunmadığından **"insan denetimi güvenilirliği artırdı" iddiası kurulamaz**; bu, makalede açık bir sınırlılık olarak yazılmalıdır. Bu, hakemin §5.4'te istediği ölçülü ifadedir.

## 3. Veri üretildiğinde hesaplanacak metrikler (protokol)
Kurum içi gerçek kullanımda (veya kontrollü bir oturumda) ≥ N kayıt incelendikten sonra, etik/mahremiyet koşullarına uygun biçimde şunlar raporlanabilir:
- Taslakların onay / düzenleme / ret oranları (`by_draft_status`).
- Yönlendirmede `changed` (insan birimi değiştirdi) oranı → otomatik yönlendirmenin yakalanan hata sıklığı.
- Düzenlenen taslaklarda yapılan düzeltme türleri (nitel kodlama).
- Zaman içinde onay oranının değişimi (öğrenme/prompt iyileştirme etkisi).
> Bu metrikler yalnızca anonimleştirilmiş ve yeterli örneklemle raporlanmalı; küçük örneklemde kesin iddiadan kaçınılmalıdır.
