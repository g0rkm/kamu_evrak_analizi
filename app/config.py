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
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # "text" veya "json"
    CORS_ORIGINS: list[str] = []

    # LLM (OpenAI uyumlu uç nokta)
    LLM_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    LLM_API_KEY: str = "not-set"
    LLM_MODEL: str = "gemini-3.5-flash"
    LLM_TIMEOUT_SECONDS: float = 180.0
    LLM_MAX_RETRIES: int = 3
    LLM_TEMPERATURE: float = 0.3
    LLM_CACHE_TTL_SECONDS: int = 3600

    # OCR
    TESSERACT_CMD: str = "tesseract"
    OCR_LANGUAGE: str = "tur"

    # Girdi sınırları ve dosya saklama
    UPLOAD_DIR: str = "uploads"
    KEEP_UPLOADS: bool = False
    MAX_FILE_SIZE_MB: int = 20
    MIN_TEXT_CHARS: int = 20
    MAX_TEXT_CHARS: int = 100_000
    MAX_BATCH_FILES: int = 10
    MAX_HISTORY_RECORDS: int = 10000

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

    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        allowed = ("development", "staging", "production")
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT {', '.join(allowed)} olmalıdır.")
        return v

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
