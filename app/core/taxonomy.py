"""Alan sözlüğü: evrak türleri, birimler, taslak türleri ve öncelikler.

LLM prompt'ları, kural tabanlı doğrulama ve arayüz etiketleri aynı kaynaktan
beslensin diye iş sözlüğünün tamamı burada tanımlanır. Yeni bir evrak türü
eklemek için yalnızca `DOCUMENT_TYPES` listesine bir kayıt eklemek yeterlidir.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Generic, Iterable, Iterator, TypeVar

_TR_ASCII = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "â": "a", "î": "i", "û": "u",
})


def normalize_code(value: str) -> str:
    """'Resmî Yazı' -> 'resmi_yazi' gibi serbest metni kod biçimine çevirir."""
    text = (value or "").strip().replace("İ", "i").replace("I", "ı").lower()
    text = text.translate(_TR_ASCII)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


@dataclass(frozen=True)
class CatalogItem:
    code: str
    label: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DocumentType(CatalogItem):
    description: str = ""
    keywords: tuple[str, ...] = ()
    draft_types: tuple[str, ...] = ()
    default_priority: str = "normal"


@dataclass(frozen=True)
class OrgUnit(CatalogItem):
    description: str = ""
    keywords: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class DraftType(CatalogItem):
    description: str = ""


@dataclass(frozen=True)
class Priority(CatalogItem):
    rank: int = 0


T = TypeVar("T", bound=CatalogItem)


class Catalog(Generic[T]):
    """Kod ile erişilen, sıralı ve salt okunur sözlük."""

    def __init__(self, items: Iterable[T]) -> None:
        self._items: dict[str, T] = {item.code: item for item in items}
        self._aliases: dict[str, str] = {}
        for item in self._items.values():
            names = (item.code, item.label, *getattr(item, "aliases", ()))
            for name in names:
                self._aliases[normalize_code(name)] = item.code

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, code: object) -> bool:
        return code in self._items

    def get(self, code: str) -> T | None:
        return self._items.get(code)

    def codes(self) -> list[str]:
        return list(self._items)

    def label(self, code: str, default: str | None = None) -> str:
        item = self._items.get(code)
        if item:
            return item.label
        return default if default is not None else code

    def resolve(self, value: str) -> str | None:
        """Serbest metin bir değeri ('Yönetmelik', 'YONETMELIK') katalog koduna çevirir."""
        return self._aliases.get(normalize_code(value))

    def to_list(self) -> list[dict]:
        return [item.to_dict() for item in self._items.values()]


UNKNOWN_DOCUMENT_TYPE = "bilinmiyor"

DOCUMENT_TYPES: Catalog[DocumentType] = Catalog([
    DocumentType(
        "dilekce", "Dilekçe", "Vatandaş veya kurum tarafından yazılan dilekçe",
        keywords=("dilekçe", "dilekcem", "talebim", "başvurum", "rica ederim", "müracaat"),
        draft_types=("cevap_yazisi", "bilgilendirme"),
    ),
    DocumentType(
        "resmi_yazi", "Resmî Yazı", "Kurumlar arası resmî üst yazı",
        keywords=("t.c.", "sayı:", "konu:", "ilgi:", "arz ederim", "bilgilerinize"),
        draft_types=("cevap_yazisi", "ust_yazi", "bilgilendirme"),
    ),
    DocumentType(
        "talep_yazisi", "Talep Yazısı", "Bir şey talep eden resmî yazı",
        keywords=("talep ed", "temin edilmesi", "tahsis", "ödenek", "bütçe"),
        draft_types=("cevap_yazisi", "ust_yazi"),
    ),
    DocumentType(
        "bilgilendirme", "Bilgilendirme Yazısı", "Bilgilendirme amaçlı yazı",
        keywords=("bilginize", "bilgilerinize rica", "duyurulur", "bilgi edinilmesi"),
        draft_types=("bilgilendirme", "ic_yazisma"), default_priority="dusuk",
    ),
    DocumentType(
        "gorus_sorma", "Görüş Sorma", "Görüş talep eden yazı",
        keywords=("görüşünüz", "görüş bildir", "değerlendirmeniz", "mütalaa"),
        draft_types=("cevap_yazisi", "ust_yazi"),
    ),
    DocumentType(
        "sikayet", "Şikâyet", "Şikâyet içeren dilekçe veya yazı",
        keywords=("şikayet", "şikâyet", "mağdur", "haksızlık", "itiraz ediyorum"),
        draft_types=("cevap_yazisi", "bilgilendirme"), default_priority="yuksek",
    ),
    DocumentType(
        "kurum_ici", "Kurum İçi Yazışma", "Kurum içi yazışma veya not",
        keywords=("hizmet içi", "personelimiz", "birimimiz", "müdürlüğümüz"),
        draft_types=("ic_yazisma", "bilgilendirme"), default_priority="dusuk",
    ),
    DocumentType(
        "genelge", "Genelge", "Genelge veya duyuru",
        keywords=("genelge", "duyuru", "tüm birimlere", "tüm personele"),
        draft_types=("bilgilendirme", "ic_yazisma"),
    ),
    DocumentType(
        "rapor", "Rapor", "Rapor veya değerlendirme belgesi",
        keywords=("rapor", "değerlendirme raporu", "faaliyet raporu", "inceleme sonucu"),
        draft_types=("ust_yazi", "bilgilendirme"),
    ),
    DocumentType(
        "tutanak", "Tutanak", "Toplantı veya olay tutanağı",
        keywords=("tutanak", "toplantı", "katılımcılar", "gündem", "karar altına"),
        draft_types=("ust_yazi", "bilgilendirme", "ic_yazisma"),
    ),
    DocumentType(
        "yonetmelik", "Yönetmelik", "Yönetmelik (düzenleyici işlem)",
        keywords=("yönetmelik", "düzenleyici", "madde ", "hüküm", "yürürlük", "resmi gazete"),
        draft_types=("bilgilendirme", "ust_yazi"),
    ),
    DocumentType(
        "teblig", "Tebliğ", "Tebliğ veya resmî tebliğ",
        keywords=("tebliğ", "tebliği", "usul ve esaslar"),
        draft_types=("bilgilendirme", "ust_yazi"),
    ),
    DocumentType(
        "kanun", "Kanun", "Kanun metni veya kanun değişikliği",
        keywords=("kanun", "kanunu", "madde ", "fıkra", "bent", "yasalaş"),
        draft_types=("bilgilendirme", "ust_yazi"), default_priority="yuksek",
    ),
    DocumentType(
        "karar", "Karar", "Karar, kurul kararı, Cumhurbaşkanlığı kararı",
        keywords=("karar", "kararı", "kararname", "cumhurbaşkanı kararı", "kurul kararı", "atanması"),
        draft_types=("bilgilendirme", "ust_yazi", "cevap_yazisi"), default_priority="yuksek",
    ),
    DocumentType(
        "kararname", "Kararname", "Cumhurbaşkanlığı kararnamesi veya KHK",
        keywords=("cumhurbaşkanlığı kararnamesi", "kanun hükmünde kararname", "khk", "kararname"),
        draft_types=("bilgilendirme", "ust_yazi"), default_priority="yuksek",
    ),
    DocumentType(
        "ilan", "İlan", "Resmî ilan veya duyuru ilanı",
        keywords=("ilan", "ilân", "duyuru", "başvuru tarihi", "son başvuru"),
        draft_types=("bilgilendirme",), default_priority="dusuk",
    ),
    DocumentType(
        "yonerge", "Yönerge", "Yönerge, usul ve esaslar belgesi",
        keywords=("yönerge", "usul ve esaslar", "çalışma esasları"),
        draft_types=("bilgilendirme", "ic_yazisma"),
    ),
    DocumentType(
        "sozlesme", "Sözleşme", "Sözleşme, protokol veya mutabakat",
        keywords=("sözleşme", "protokol", "mutabakat", "taraflar", "imza altına"),
        draft_types=("ust_yazi", "cevap_yazisi"),
    ),
])

ORG_UNITS: Catalog[OrgUnit] = Catalog([
    OrgUnit(
        "hukuk", "Hukuk Müşavirliği", "Hukuki konular, davalar, sözleşmeler, mevzuat yorumu",
        keywords=("dava", "mahkeme", "hukuk", "sözleşme", "mevzuat", "kanun", "yönetmelik", "itiraz", "idari yargı"),
    ),
    OrgUnit(
        "insan_kaynaklari", "İnsan Kaynakları Daire Başkanlığı", "Personel işlemleri, atama, izin, özlük",
        keywords=("personel", "atama", "izin", "özlük", "sicil", "disiplin", "memur", "kadro"),
    ),
    OrgUnit(
        "strateji", "Strateji Geliştirme Daire Başkanlığı", "Bütçe, planlama, performans, istatistik",
        keywords=("bütçe", "ödenek", "planlama", "performans", "istatistik", "mali"),
    ),
    OrgUnit(
        "bilgi_teknolojileri", "Bilgi Teknolojileri Daire Başkanlığı", "BT altyapısı, yazılım, siber güvenlik",
        keywords=("yazılım", "bilişim", "siber", "sunucu", "ağ", "bilgi sistemi", "e-devlet"),
    ),
    OrgUnit(
        "idari_mali", "İdari ve Mali İşler Daire Başkanlığı", "Satın alma, ihale, lojistik, taşınır",
        keywords=("satın alma", "ihale", "lojistik", "taşınır", "demirbaş", "kira", "bakım"),
    ),
    OrgUnit(
        "basin", "Basın ve Halkla İlişkiler Müdürlüğü", "Medya, CİMER, halkla ilişkiler",
        keywords=("basın", "medya", "cimer", "halkla ilişkiler", "kamuoyu", "vatandaş başvuru"),
    ),
    OrgUnit(
        "teftis", "Teftiş Kurulu Başkanlığı", "Denetim, soruşturma, teftiş",
        keywords=("denetim", "soruşturma", "teftiş", "müfettiş", "inceleme", "usulsüzlük"),
    ),
    OrgUnit(
        "genel_mudurluk", "Genel Müdürlük (ilgili)", "Kurumun ana faaliyet alanına göre ilgili genel müdürlük",
        aliases=("Genel Müdürlük",),
    ),
])

DRAFT_TYPES: Catalog[DraftType] = Catalog([
    DraftType("ust_yazi", "Üst Yazı", "Kurumlar arası resmî üst yazı"),
    DraftType("cevap_yazisi", "Cevap Yazısı", "Gelen yazıya cevap"),
    DraftType("bilgilendirme", "Bilgilendirme Yazısı", "Bilgilendirme yazısı"),
    DraftType("ic_yazisma", "İç Yazışma", "Kurum içi yazışma"),
])

PRIORITIES: Catalog[Priority] = Catalog([
    Priority("acil", "Acil", rank=3),
    Priority("yuksek", "Yüksek", rank=2),
    Priority("normal", "Normal", rank=1),
    Priority("dusuk", "Düşük", rank=0),
])

DEFAULT_PRIORITY = "normal"

URGENT_KEYWORDS: tuple[str, ...] = (
    "acil", "ivedi", "derhal", "süre dolmak üzere", "son gün", "zamanaşımı", "mahkeme süresi",
)
