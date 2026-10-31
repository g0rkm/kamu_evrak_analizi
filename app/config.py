"""Uygulama yapılandırması (.env ve ortam değişkenlerinden okunur)."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Uygulama
    APP_NAME: str = "Kamu Evrak Analizi Sistemi"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8080
    ENVIRONMENT: str = "development"  # "development", "staging", "production"
    LOG_LEVEL: str = "INFO"  # loglama seviyesi, field_validator ile DEBUG, INFO, WARNING, ERROR, CRITICAL değerlerinden biri olmalı
    LOG_FORMAT: str = "text"  # "text" veya "json"
    LOG_FILE: str = ""
    CORS_ORIGINS: str = "*"  # virgül ile ayrılmış izin verilen origin'ler, * ise tümü

    # LLM (OpenAI uyumlu uç nokta)
    LLM_API_BASE: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "gemma4:12b"
    LLM_TIMEOUT_SECONDS: float = 180.0
    LLM_MAX_RETRIES: int = 3
    LLM_TEMPERATURE: float = 0.3
    LLM_CACHE_TTL_SECONDS: int = 3600
    LLM_NUM_CTX: int = 16384
    LLM_KEEP_ALIVE: str = "30m"
    LLM_MAX_CONCURRENT_REQUESTS: int = 2

    # OCR
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    OCR_LANGUAGE: str = "tur"

    # Girdi sınırları ve dosya saklama
    UPLOAD_DIR: str = "uploads"
    KEEP_UPLOADS: bool = False
    MAX_FILE_SIZE_MB: int = 50
    REQUEST_BODY_LIMIT_MB: int = 100
    MIN_TEXT_CHARS: int = 20
    MAX_TEXT_CHARS: int = 100_000
    MAX_BATCH_FILES: int = 10
    MAX_HISTORY_RECORDS: int = 10000
    DISK_WARNING_THRESHOLD_MB: int = 100
    ANALYSIS_TIMEOUT: int = 60
    ALLOWED_FILE_TYPES: str = 'pdf,png,jpg,jpeg,tiff,bmp'
    SESSION_TIMEOUT_MINUTES: int = 30
    MAX_TAGS_PER_RECORD: int = 20
    MAX_NOTE_LENGTH: int = 2000
    CACHE_TTL: int = 300

    # RAG
    RAG_INDEX_DIR: str = "app/data/rag"
    RAG_TOP_K: int = 8
    RAG_CHUNK_SIZE: int = 600
    RAG_CHUNK_OVERLAP: int = 100

    # Geçmiş ve arka plan işleri
    HISTORY_DIR: str = "data/history"
    MAX_CONCURRENT_JOBS: int = 2
    JOB_TTL_SECONDS: int = 3600
    PIPELINE_TIMEOUT_SECONDS: float = 300.0
    LLM_TOKEN_BUDGET: int = 0  # 0 = sınırsız; >0 = toplam token üst limiti

    # Güvenlik
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60
    TRUSTED_PROXIES: list[str] = []
    CSP_REPORT_ONLY: bool = True
    MAINTENANCE_MODE: bool = False
    ADMIN_TOKEN: str = ""
    IP_WHITELIST: str = ""  # virgül ile ayrılmış izin verilen IP listesi, boş ise tüm IP'ler
    IP_BLACKLIST: str = ""  # virgül ile ayrılmış engellenen IP listesi

    # Yeni eklenen alanlar
    MAX_TEMPLATE_COUNT: int = 100
    ENABLE_NOTIFICATIONS: bool = True
    AUTO_BACKUP_ENABLED: bool = False
    AUTO_BACKUP_INTERVAL_HOURS: int = 24

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"LOG_LEVEL {', '.join(allowed)} değerlerinden biri olmalıdır.")
        return v_upper

    @field_validator("LOG_FORMAT")
    @classmethod
    def _validate_log_format(cls, v: str) -> str:
        if v not in ("text", "json"):
            raise ValueError("LOG_FORMAT 'text' veya 'json' olmalıdır.")
        return v

    @field_validator("PIPELINE_TIMEOUT_SECONDS")
    @classmethod
    def _validate_timeout(cls, v: float) -> float:
        if v < 10:
            raise ValueError("PIPELINE_TIMEOUT_SECONDS en az 10 olmalıdır.")
        return v

    @field_validator("ANALYSIS_TIMEOUT")
    @classmethod
    def _validate_analysis_timeout(cls, v: int) -> int:
        if not (5 <= v <= 600):
            raise ValueError("ANALYSIS_TIMEOUT 5 ile 600 arasında olmalıdır.")
        return v

    @field_validator("MIN_TEXT_CHARS")
    @classmethod
    def _validate_min_text(cls, v: int) -> int:
        if v < 1:
            raise ValueError("MIN_TEXT_CHARS en az 1 olmalıdır.")
        return v

    @field_validator("MAX_TEXT_CHARS")
    @classmethod
    def _validate_max_text(cls, v: int) -> int:
        if v < 100:
            raise ValueError("MAX_TEXT_CHARS en az 100 olmalıdır.")
        return v

    @field_validator("MAX_FILE_SIZE_MB")
    @classmethod
    def _validate_max_file_size(cls, v: int) -> int:
        if not (1 <= v <= 500):
            raise ValueError("MAX_FILE_SIZE_MB 1 ile 500 arasında olmalıdır.")
        return v

    @field_validator("REQUEST_BODY_LIMIT_MB")
    @classmethod
    def _validate_request_body_limit(cls, v: int) -> int:
        if not (1 <= v <= 1000):
            raise ValueError("REQUEST_BODY_LIMIT_MB 1 ile 1000 arasında olmalıdır.")
        return v

    @field_validator("MAX_TAGS_PER_RECORD")
    @classmethod
    def _validate_max_tags(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("MAX_TAGS_PER_RECORD 1 ile 100 arasında olmalıdır.")
        return v

    @field_validator("MAX_NOTE_LENGTH")
    @classmethod
    def _validate_max_note_length(cls, v: int) -> int:
        if not (100 <= v <= 10000):
            raise ValueError("MAX_NOTE_LENGTH 100 ile 10000 arasında olmalıdır.")
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        allowed = ("development", "staging", "production")
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT {', '.join(allowed)} olmalıdır.")
        return v

    @field_validator("ALLOWED_FILE_TYPES")
    @classmethod
    def _validate_allowed_file_types(cls, v: str) -> str:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if not parts:
            raise ValueError("ALLOWED_FILE_TYPES boş olamaz.")
        for part in parts:
            if not (2 <= len(part) <= 10):
                raise ValueError("Her bir dosya uzantısının uzunluğu 2 ile 10 karakter arasında olmalıdır.")
        return v

    @field_validator("SESSION_TIMEOUT_MINUTES")
    @classmethod
    def _validate_session_timeout(cls, v: int) -> int:
        if not (1 <= v <= 1440):
            raise ValueError("SESSION_TIMEOUT_MINUTES 1 ile 1440 arasında olmalıdır.")
        return v

    @field_validator("IP_WHITELIST", "IP_BLACKLIST")
    @classmethod
    def _validate_ip_list(cls, v: str) -> str:
        if v is None:
            return ""
        v = v.strip()
        if not v:
            return ""
        parts = [p.strip() for p in v.split(",") if p.strip()]
        return ",".join(parts)

    @staticmethod
    def resolve(path: str) -> Path:
        """Göreli yolları proje köküne göre çözer."""
        candidate = Path(path)
        return candidate if candidate.is_absolute() else BASE_DIR / candidate

    @property
    def upload_path(self) -> Path:
        return self.resolve(self.UPLOAD_DIR)

    @property
    def history_path(self) -> Path:
        return self.resolve(self.HISTORY_DIR)

    @property
    def rag_index_path(self) -> Path:
        return self.resolve(self.RAG_INDEX_DIR)

    @property
    def max_file_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    return Settings()
