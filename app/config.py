from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_API_BASE: str = "http://127.0.0.1:8000/v1"
    LLM_API_KEY: str = "dummy"
    LLM_MODEL: str = "openai/argon-4"
    TESSERACT_CMD: str = "tesseract"
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 20

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
