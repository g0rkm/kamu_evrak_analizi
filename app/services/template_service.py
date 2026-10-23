import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional


DEFAULT_TEMPLATES = [
    {
        "id": "tpl_dilekce",
        "name": "Dilekce",
        "document_type": "dilekce",
        "description": "Standart dilekce sablonu",
        "default_tags": ["dilekce", "resmi"],
        "default_priority": "normal",
        "fields": ["gonderen", "alici", "konu", "tarih"],
        "builtin": True,
    },
    {
        "id": "tpl_rapor",
        "name": "Rapor",
        "document_type": "rapor",
        "description": "Teknik veya idari rapor sablonu",
        "default_tags": ["rapor"],
        "default_priority": "normal",
        "fields": ["baslik", "yazar", "tarih", "bolum"],
        "builtin": True,
    },
    {
        "id": "tpl_sozlesme",
        "name": "Sozlesme",
        "document_type": "sozlesme",
        "description": "Sozlesme veya protokol sablonu",
        "default_tags": ["sozlesme", "hukuki"],
        "default_priority": "high",
        "fields": ["taraflar", "konu", "tarih", "sure"],
        "builtin": True,
    },
    {
        "id": "tpl_tutanak",
        "name": "Tutanak",
        "document_type": "tutanak",
        "description": "Toplanti veya olay tutanagi sablonu",
        "default_tags": ["tutanak"],
        "default_priority": "normal",
        "fields": ["tarih", "yer", "katilimcilar", "konu"],
        "builtin": True,
    },
]


class TemplateService:
    """Evrak sablonu yonetim servisi."""

    def __init__(self, storage_dir: str):
        self._dir = storage_dir
        os.makedirs(self._dir, exist_ok=True)
        self._file = os.path.join(self._dir, "templates.json")
        self._lock = threading.Lock()
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Varsayilan sablonlari yukler."""
        templates = self._load()
        existing_ids = {t["id"] for t in templates}
        for tpl in DEFAULT_TEMPLATES:
            if tpl["id"] not in existing_ids:
                templates.append(tpl)
        self._save(templates)

    def _load(self) -> list:
        if not os.path.exists(self._file):
            return []
        with self._lock:
            with open(self._file, "r", encoding="utf-8") as f:
                return json.load(f)

    def _save(self, templates: list):
        with self._lock:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(templates, f, indent=2, ensure_ascii=False)

    def list_templates(self) -> list:
        return self._load()

    def get_template(self, template_id: str) -> Optional[dict]:
        templates = self._load()
        for t in templates:
            if t["id"] == template_id:
                return t
        return None

    def create_template(self, name: str, document_type: str, description: str = "",
                        default_tags: list = None, default_priority: str = "normal",
                        fields: list = None) -> dict:
        tpl = {
            "id": f"tpl_{uuid.uuid4().hex[:8]}",
            "name": name,
            "document_type": document_type,
            "description": description,
            "default_tags": default_tags or [],
            "default_priority": default_priority,
            "fields": fields or [],
            "builtin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        templates = self._load()
        templates.append(tpl)
        self._save(templates)
        return tpl

    def delete_template(self, template_id: str) -> bool:
        templates = self._load()
        for t in templates:
            if t["id"] == template_id:
                if t.get("builtin"):
                    return False
                templates.remove(t)
                self._save(templates)
                return True
        return False

    def update_template(self, template_id: str, updates: dict) -> Optional[dict]:
        templates = self._load()
        for t in templates:
            if t["id"] == template_id:
                if t.get("builtin"):
                    return None
                for k, v in updates.items():
                    if k not in ("id", "builtin"):
                        t[k] = v
                self._save(templates)
                return t
        return None
