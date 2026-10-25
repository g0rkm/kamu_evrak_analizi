"""Türkçe'ye duyarlı metin normalizasyonu (RAG indeks ve sorgu tarafında ortak).

Python'un varsayılan ``str.lower()`` fonksiyonu Türkçe metinleri bozar:
``"İ".lower()`` → ``"i̇"`` (i + U+0307 birleştirici nokta) ve ``"I".lower()`` → ``"i"``
(Türkçe'de doğrusu ``"ı"``). Bu, TF-IDF belirteçlemesinde ``"İDARİ"`` gibi sözcükleri
parçalayıp eşleşmeyi bozar.

``turkish_lower`` modül düzeyinde (picklable) bir fonksiyondur ve
``scripts/build_index.py`` içinde ``TfidfVectorizer(preprocessor=turkish_lower,
lowercase=False)`` olarak kullanılır. Böylece aynı normalizasyon hem indeks
oluşturmada hem de sorgu tarafında (vektörleyici pickle ile taşındığı için)
otomatik ve tutarlı biçimde uygulanır.
"""
from __future__ import annotations


def turkish_lower(text: str) -> str:
    """Türkçe harfleri doğru küçülten ``lower()``.

    Önce Türkçe'ye özgü ``İ`` → ``i`` ve ``I`` → ``ı`` eşlemelerini uygular,
    ardından genel ``str.lower()`` çağırır (``Ğ/Ü/Ş/Ö/Ç`` zaten doğru küçülür).
    """
    if not text:
        return text
    text = text.replace("İ", "i").replace("I", "ı")
    return text.lower()
