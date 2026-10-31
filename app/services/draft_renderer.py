from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Dict

from app.models.draft import DraftResponse
from app.models.analysis import AnalysisResult

if TYPE_CHECKING:
    from app.models.draft import RoutingDecision


class _SafeDict(defaultdict):
    def __init__(self, *args, **kwargs):
        super().__init__(str, *args, **kwargs)

    def __missing__(self, key: str) -> str:
        return ""


def _load_templates() -> dict[str, str]:
    try:
        path = Path(__file__).resolve().parent.parent / "data" / "templates.json"
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        templates = {}
        for item in data:
            if "id" in item and "template" in item:
                templates[item["id"]] = item["template"]
        return templates
    except Exception:
        return {}


def render_draft(
    draft: DraftResponse,
    analysis: AnalysisResult | None = None,
    routing: "RoutingDecision | None" = None,
    *,
    sayi: str | None = None,
    tarih: str | None = None,
    kurum_adi: str | None = None,
    birim_adi: str | None = None,
) -> str:
    templates = _load_templates()
    template_str = templates.get(draft.draft_type) or templates.get("ust_yazi")

    resolved_kurum = kurum_adi or "[Kurum Adı]"
    resolved_birim = birim_adi or "[Birim Adı]"
    resolved_sayi = sayi or f"E-{datetime.now().year}-{hashlib.md5(((draft.subject or '') + (draft.body or '')).encode('utf-8')).hexdigest()[:6].upper()}"
    resolved_tarih = tarih or datetime.now().strftime("%d.%m.%Y")
    resolved_konu = draft.subject.strip() if draft.subject else "[Konu]"
    resolved_govde = draft.body.strip() if draft.body else "[Yazı metni]"
    resolved_imza = "[Ad Soyad]"
    resolved_unvan = "[Unvan]"

    alici = ""
    if routing and routing.target_unit:
        alici = routing.target_unit.strip()
    alici_block = f"{alici}\n\n" if alici else ""

    ilgi_ref = ""
    if draft.formal_greeting:
        cleaned_fg = re.sub(r"^\s*ilgi\s*:\s*", "", draft.formal_greeting.strip(), flags=re.IGNORECASE)
        if cleaned_fg:
            ilgi_ref = cleaned_fg

    if not ilgi_ref and analysis and hasattr(analysis, "entities") and analysis.entities:
        tarih_val = None
        sayi_val = None
        for entity in analysis.entities:
            e_type = getattr(entity, "entity_type", None)
            e_value = getattr(entity, "value", None)
            if not e_type or not e_value:
                continue
            if e_type == "tarih" and not tarih_val:
                tarih_val = e_value.strip()
            elif e_type == "referans_no" and not sayi_val:
                sayi_val = e_value.strip()

        if tarih_val and sayi_val:
            ilgi_ref = f"{tarih_val} tarihli ve {sayi_val} sayılı yazı"
        elif tarih_val:
            ilgi_ref = f"{tarih_val} tarihli yazı"
        elif sayi_val:
            ilgi_ref = f"{sayi_val} sayılı yazı"

    ilgi_block = f"İlgi : {ilgi_ref}\n\n" if ilgi_ref else ""

    ek_block = ""
    if draft.attachments_note:
        cleaned_ek = draft.attachments_note.strip()
        if cleaned_ek:
            ek_block = f"\n\nEk : {cleaned_ek}"

    values = {
        "kurum_adi": resolved_kurum,
        "birim_adi": resolved_birim,
        "sayi": resolved_sayi,
        "tarih": resolved_tarih,
        "konu": resolved_konu,
        "alici_block": alici_block,
        "ilgi_block": ilgi_block,
        "govde": resolved_govde,
        "imza_adi": resolved_imza,
        "unvan": resolved_unvan,
        "ek_block": ek_block,
    }

    if template_str:
        try:
            safe_mapping = _SafeDict(values)
            rendered = template_str.format_map(safe_mapping)
            return rendered.strip("\n")
        except Exception:
            pass

    fallback_parts = [
        f"T.C.\n{resolved_kurum}\n{resolved_birim}",
        f"Sayı : {resolved_sayi}\nTarih: {resolved_tarih}\nKonu : {resolved_konu}",
        alici_block + ilgi_block + resolved_govde,
        "Bilgilerinize arz ederim.",
        f"{resolved_imza}\n{resolved_unvan}{ek_block}",
    ]
    return "\n\n".join([p for p in fallback_parts if p]).strip("\n")
