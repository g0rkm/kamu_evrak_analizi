from datetime import datetime, timezone
import threading
from typing import Any


class SessionManager:
    def __init__(self, timeout_minutes: int = 30, max_sessions_per_user: int = 3):
        self._timeout_minutes = timeout_minutes
        self._max_sessions_per_user = max_sessions_per_user
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _is_expired(self, session: dict[str, Any]) -> bool:
        last_activity = datetime.fromisoformat(session["last_activity"])
        now = datetime.now(timezone.utc)
        elapsed_minutes = (now - last_activity).total_seconds() / 60
        return elapsed_minutes > self._timeout_minutes

    def create_session(self, token: str, username: str, role: str) -> dict[str, Any]:
        with self._lock:
            # Süresi dolmuş oturumları temizleyebiliriz ya da kullanıcı bazlı limit kontrolünden önce temizlik yapabiliriz
            now_iso = datetime.now(timezone.utc).isoformat()

            # Kullanıcıya ait aktif oturumları bul ve limit aşımını kontrol et
            user_sessions = []
            for t, sess in list(self._sessions.items()):
                if sess["username"] == username:
                    if self._is_expired(sess):
                        del self._sessions[t]
                    else:
                        user_sessions.append((t, sess))

            # Eğer limit aşıldıysa, en eski oturumu (created_at veya last_activity bazlı) sil
            if len(user_sessions) >= self._max_sessions_per_user:
                # created_at değerine göre sıralayıp en eskisini bulalım
                user_sessions.sort(key=lambda x: x[1]["created_at"])
                oldest_token, _ = user_sessions[0]
                del self._sessions[oldest_token]

            session = {
                "token": token,
                "username": username,
                "role": role,
                "created_at": now_iso,
                "last_activity": now_iso,
                "ip_address": None,
            }
            self._sessions[token] = session
            return session

    def validate_session(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            session = self._sessions.get(token)
            if not session:
                return None

            if self._is_expired(session):
                del self._sessions[token]
                return None

            # Geçerliyse last_activity güncelle
            session["last_activity"] = datetime.now(timezone.utc).isoformat()
            return session

    def end_session(self, token: str) -> bool:
        with self._lock:
            if token in self._sessions:
                del self._sessions[token]
                return True
            return False

    def update_activity(self, token: str, ip_address: str | None = None):
        with self._lock:
            session = self._sessions.get(token)
            if session and not self._is_expired(session):
                session["last_activity"] = datetime.now(timezone.utc).isoformat()
                if ip_address is not None:
                    session["ip_address"] = ip_address

    def get_active_sessions(self, username: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            active_sessions = []
            expired_tokens = []

            for token, session in self._sessions.items():
                if self._is_expired(session):
                    expired_tokens.append(token)
                else:
                    if username is None or session["username"] == username:
                        active_sessions.append(session)

            # Süresi dolanları temizle
            for token in expired_tokens:
                del self._sessions[token]

            return active_sessions

    def cleanup_expired(self) -> int:
        with self._lock:
            expired_tokens = []
            for token, session in self._sessions.items():
                if self._is_expired(session):
                    expired_tokens.append(token)

            for token in expired_tokens:
                del self._sessions[token]

            return len(expired_tokens)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            active_sessions = []
            expired_tokens = []

            for token, session in self._sessions.items():
                if self._is_expired(session):
                    expired_tokens.append(token)
                else:
                    active_sessions.append(session)

            for token in expired_tokens:
                del self._sessions[token]

            total_active = len(active_sessions)
            unique_users = len({s["username"] for s in active_sessions})

            oldest_session = None
            if active_sessions:
                # created_at değerine göre en eskisini bul
                oldest = min(active_sessions, key=lambda s: s["created_at"])
                oldest_session = oldest["created_at"]

            return {
                "total_active": total_active,
                "unique_users": unique_users,
                "oldest_session": oldest_session,
            }
