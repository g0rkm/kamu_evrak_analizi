# KVKK ve Güvenlik Çerçevesi — Makale Notları (Faz 7)

> **Kaynak:** JOINSSR hakem raporu §2, §5.2, §5.3. **İlke:** Mutlak güvenlik/uyum iddiası yok; her iddia ölçülmüş bir orana veya açık bir organizasyonel koşula bağlanır.

## 1. Deneysel dayanak (E5)
- **PII tespiti** ([results/e5/pii_eval.json](../results/e5/pii_eval.json)): Precision 0,88 / Recall 0,94; ölçülen yanlış pozitif (plaka, SGK regex'i) ve yanlış negatif (`+90 5xx` telefon) vardır. Maskeleme güvenilirliği tespit kapsamıyla sınırlıdır (tespit edilemeyen PII maskelenemez).
- **Prompt injection** ([results/e5/injection.json](../results/e5/injection.json)): Davranış ele geçirme saldırılarının %100'ü (talimat geçersiz kılma, `</evrak>` etiket kırma, JSON kırma, yanlış yönlendirme) azaltıldı; **sistem istemi sızdırma saldırısı başarılı oldu** (genel azaltma %85,7).

## 2. Yerel işlemenin sınırı (§2)
Yerel Ollama (`gemma4:12b`) kullanımı evrak içeriğinin üçüncü taraf bulut API'lerine gönderilmesi riskini azaltır; ancak bu, uçtan uca güvenlik veya KVKK uyumu anlamına **gelmez**. Gizlilik şunlara bağlıdır:
- `LLM_API_BASE` ayarının yerel uç noktayla (`localhost:11434`) sınırlı olması — yapılandırma uzak bir uç noktaya çevrilirse veri dışarı akar;
- kurum ağ politikasının dış trafiği denetlemesi.

## 3. Veri saklama, erişim ve loglar (§5.3)
Uygulama kalıcı veri üretir; bunlar KVKK açısından ayrıca yönetilmelidir:
- **Analiz geçmişi** (`data/history/`): analiz edilen evrakların çıktıları — kişisel veri içerebilir; saklama süresi, şifreleme ve rol tabanlı erişim kurum politikasıyla tanımlanmalı.
- **Loglar** (`data/logs/`) ve **denetim kaydı** (`app/core/audit_middleware.py`): hassas içerik sızmasını önlemek için maskeleme/erişim denetimi gerekli.
- **Yedekler** (`data/backups/`): aynı saklama/şifreleme politikalarına tabi olmalı.
- **Yüklenen dosyalar** (`uploads/`): varsayılan olarak analizden sonra silinir (`KEEP_UPLOADS`), ancak bu yapılandırılabilir.

## 4. Makalede kullanılacak ifade
- "PII/KVKK koruması sağlar" **değil** → "TC/IBAN/telefon/e-posta vb. için biçim tabanlı tespit uygulanmıştır; ölçülen precision/recall ve yanlış pozitif/negatif oranları raporlanmıştır (E5)."
- "Prompt injection koruması sağlar" **değil** → "Adversarial kümede davranış ele geçirme saldırılarının tamamı, tüm saldırıların %85,7'si azaltılmıştır; sistem istemi gizliliği ayrı önlem gerektirir."
- Yerel model, mahremiyet riskini **azaltır**; kurumsal güvenlik ve KVKK uyumu organizasyonel/teknik ek tedbirlerle (saklama, erişim, ağ, şifreleme) tamamlanmalıdır.
