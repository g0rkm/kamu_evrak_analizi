# PLAN 2: PII/KVKK Tespit Sistemi

## Amac
Evraklardaki kisisel verileri (TC kimlik, IBAN, telefon, e-posta, adres vb.) otomatik tespit etmek.
AGENTIX projesinden esinlenerek, ReasoningAgent'a regex tabanli PII tespit kurallari ekleyecegiz.
Ayrica taslak yazida kisisel veri sizintisi kontrolu yapacagiz (KACHOW'dan esinlenerek).

## Neden ReasoningAgent'a Ekliyoruz
- Zaten deterministic, kural tabanli calisiyor — LLM gerektirmiyor
- Pipeline'in son adiminda her seyi dogruluyor — PII kontrolu de bu mantiga uyuyor
- Validation kayitlarina dogal olarak eklenebilir

## Tespit Edilecek PII Turleri

| Tur | Regex Pattern | Ornek |
|-----|---------------|-------|
| TC Kimlik No | 11 haneli, Luhn-benzeri checksum | 12345678901 |
| IBAN | TR + 24 rakam | TR330006100519786457841326 |
| Telefon | 05xx veya +90 5xx formatı | 0532 123 45 67 |
| E-posta | standart email regex | ornek@kurum.gov.tr |
| Plaka | XX YYY NN formatı | 34 ABC 123 |

## Dosya Degisiklikleri

### 1. DEGISECEK: app/agents/reasoning_agent.py

#### 1a. PII_PATTERNS sozlugu ekle (dosya ustune):
```python
PII_PATTERNS = {
    "tc_kimlik": {
        "pattern": r'\b[1-9]\d{10}\b',
        "label": "TC Kimlik Numarasi",
        "validate": "_validate_tc_kimlik",  # checksum dogrulama
        "severity": "warning"
    },
    "iban": {
        "pattern": r'\bTR\s?\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\b',
        "label": "IBAN",
        "severity": "warning"
    },
    "telefon": {
        "pattern": r'\b(?:\+90|0)\s?[5]\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b',
        "label": "Telefon Numarasi",
        "severity": "info"
    },
    "eposta": {
        "pattern": r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
        "label": "E-posta Adresi",
        "severity": "info"
    }
}
```

#### 1b. TC Kimlik checksum dogrulama metodu ekle:
```python
@staticmethod
def _validate_tc_kimlik(value: str) -> bool:
    """TC Kimlik numarasi checksum dogrulamasi."""
    if len(value) != 11 or value[0] == '0':
        return False
    digits = [int(d) for d in value]
    # Algoritma: tek haneler toplami * 7 - cift haneler toplami mod 10 = 10. hane
    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])
    check1 = (odd_sum * 7 - even_sum) % 10
    check2 = sum(digits[0:10]) % 10
    return check1 == digits[9] and check2 == digits[10]
```

#### 1c. execute() metoduna KURAL 6 ekle (Kural 5'ten sonra):
```python
# -- KURAL 6: PII/KVKK Tespiti --
pii_findings = self._detect_pii(text)
for finding in pii_findings:
    validation.append(ValidationEntry(
        field=f"pii.{finding['type']}",
        original_value=finding['masked_value'],
        rule="pii_detection",
        severity=finding['severity']
    ))

# Taslak yazida PII sizintisi kontrolu
if draft and draft.body:
    draft_pii = self._detect_pii(draft.body)
    for finding in draft_pii:
        validation.append(ValidationEntry(
            field=f"draft_pii_leak.{finding['type']}",
            original_value=finding['masked_value'],
            rule="draft_pii_leak",
            severity="warning"
        ))
```

#### 1d. _detect_pii() metodu ekle:
```python
def _detect_pii(self, text: str) -> list[dict]:
    """Metinde kisisel veri tespiti yap."""
    findings = []
    for pii_type, config in PII_PATTERNS.items():
        matches = re.finditer(config["pattern"], text)
        for match in matches:
            value = match.group()
            # TC kimlik icin checksum dogrula
            if pii_type == "tc_kimlik":
                clean = re.sub(r'\s', '', value)
                if not self._validate_tc_kimlik(clean):
                    continue
            # Maskeleme: ilk 3 ve son 2 karakter goster, geri kalani ***
            masked = value[:3] + "***" + value[-2:] if len(value) > 5 else "***"
            findings.append({
                "type": pii_type,
                "label": config["label"],
                "masked_value": masked,
                "severity": config["severity"]
            })
    return findings
```

### 2. DEGISECEK: frontend/app.js — renderValidation fonksiyonu
PII bulgulari icin ozel renk/ikon:
- `pii.*` field'lari icin mor/turuncu badge goster
- `draft_pii_leak.*` icin kirmizi uyari goster

### 3. DEGISECEK: frontend/index.html
Dogrulama sekmesine PII ozet kutusu ekle (toplam PII sayisi, turlerine gore dagilim)

## Islem Sirasi (Aider Cagrilari)

1. `app/agents/reasoning_agent.py` guncelle (PII patterns, detect, validate, Kural 6)
2. `frontend/app.js` guncelle (PII goruntuleme)
3. `frontend/index.html` guncelle (PII ozet kutusu)
4. Test: PII iceren metin gonder, dogrulama sekmesinde tespit sonuclarini gor

## Basari Kriteri
- "TC Kimlik: 10000000146" iceren metin gondermede PII tespiti validation'da gorunmeli
- Gecersiz TC numaralari (checksum hatali) filtrelenmeli
- Taslak yazida PII varsa "draft_pii_leak" uyarisi cıkmali
- Mevcut pipeline'da regression olmamali
