from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    LLM_API_KEY: str = "not-set"
    LLM_MODEL: str = "gemini-3.5-flash"
    TESSERACT_CMD: str = "tesseract"
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 20
    RAG_INDEX_DIR: str = "app/data/rag"
    RAG_TOP_K: int = 8
    RAG_CHUNK_SIZE: int = 600
    RAG_CHUNK_OVERLAP: int = 100
    HISTORY_DIR: str = "data/history"

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
