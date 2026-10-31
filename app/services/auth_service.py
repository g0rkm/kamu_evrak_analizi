import hashlib
import json
import os
import secrets
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional


class AuthService:
    """Basit rol tabanli yetkilendirme servisi.
    
    Roller: admin, yonetici, memur, izleyici
    - admin: Tum islemler (sistem yonetimi dahil)
    - yonetici: Kayit yonetimi + rapor goruntuleme
    - memur: Kayit olusturma, goruntuleme, duzenleme
    - izleyici: Sadece goruntuleme
    """

    ROLES = {
        "admin": {"level": 100, "description": "Tam yetki"},
        "yonetici": {"level": 75, "description": "Kayit yonetimi ve raporlama"},
        "memur": {"level": 50, "description": "Kayit islemleri"},
        "izleyici": {"level": 25, "description": "Salt okunur erisim"},
    }

    PERMISSIONS = {
        "record.create": 50,
        "record.read": 25,
        "record.update": 50,
        "record.delete": 75,
        "record.export": 50,
        "report.view": 75,
        "report.create": 75,
        "system.admin": 100,
        "system.backup": 100,
        "system.audit": 75,
        "template.manage": 75,
        "notification.manage": 75,
    }

    def __init__(self, storage_dir: str):
        self._dir = storage_dir
        os.makedirs(self._dir, exist_ok=True)
        self._file = os.path.join(self._dir, "users.json")
        self._tokens_file = os.path.join(self._dir, "tokens.json")
        self._lock = threading.Lock()
        self._seed_defaults()

    def _seed_defaults(self):
        users = self._load_users()
        if "admin" not in users:
            self.create_user("admin", "admin123", role="admin", full_name="Sistem Yöneticisi")
        if "kullanici" not in users:
            self.create_user("kullanici", "kamu123", role="memur", full_name="Standart Kullanıcı")

    def _load_users(self) -> dict:
        if not os.path.exists(self._file):
            return {}
        with open(self._file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_users(self, users: dict):
        with self._lock:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2, ensure_ascii=False)

    def _load_tokens(self) -> dict:
        if not os.path.exists(self._tokens_file):
            return {}
        with open(self._tokens_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_tokens(self, tokens: dict):
        with self._lock:
            with open(self._tokens_file, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def create_user(self, username: str, password: str, role: str = "memur", full_name: str = "") -> dict:
        """Yeni kullanici olusturur."""
        if role not in self.ROLES:
            raise ValueError(f"Gecersiz rol: {role}")
        users = self._load_users()
        if username in users:
            raise ValueError(f"Kullanici zaten var: {username}")
        users[username] = {
            "username": username,
            "password_hash": self._hash_password(password),
            "role": role,
            "full_name": full_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
            "last_login": None,
        }
        self._save_users(users)
        return {"username": username, "role": role, "full_name": full_name}

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Kullaniciyi dogrular ve token dondurur."""
        users = self._load_users()
        user = users.get(username)
        if not user or not user.get("active"):
            return None
        if user["password_hash"] != self._hash_password(password):
            return None
        user["last_login"] = datetime.now(timezone.utc).isoformat()
        self._save_users(users)
        token = secrets.token_hex(32)
        tokens = self._load_tokens()
        tokens[token] = {
            "username": username,
            "role": user["role"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
        }
        self._save_tokens(tokens)
        return token

    def validate_token(self, token: str) -> Optional[dict]:
        """Token'i dogrular ve kullanici bilgisini dondurur."""
        tokens = self._load_tokens()
        info = tokens.get(token)
        if not info:
            return None
        if datetime.fromisoformat(info["expires_at"]) < datetime.now(timezone.utc):
            del tokens[token]
            self._save_tokens(tokens)
            return None
        return {"username": info["username"], "role": info["role"]}

    def has_permission(self, role: str, permission: str) -> bool:
        """Rolun izni olup olmadigini kontrol eder."""
        role_info = self.ROLES.get(role)
        if not role_info:
            return False
        required_level = self.PERMISSIONS.get(permission, 100)
        return role_info["level"] >= required_level

    def list_users(self) -> list:
        """Kullanicilari listeler (parola hash'i olmadan)."""
        users = self._load_users()
        return [
            {k: v for k, v in u.items() if k != "password_hash"}
            for u in users.values()
        ]

    def deactivate_user(self, username: str) -> bool:
        """Kullaniciyi deaktif eder."""
        users = self._load_users()
        if username not in users:
            return False
        users[username]["active"] = False
        self._save_users(users)
        return True

    def revoke_token(self, token: str) -> bool:
        """Token'i iptal eder."""
        tokens = self._load_tokens()
        if token in tokens:
            del tokens[token]
            self._save_tokens(tokens)
            return True
        return False
