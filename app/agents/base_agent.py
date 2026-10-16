from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMResponseError
from app.services.llm_service import LLMService

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseAgent(ABC):
    """Tüm agentlar için soyut temel sınıf.

    Agentlar tek bir pipeline çalıştırması için oluşturulur; `log()` ile
    tuttukları kayıtlar o çalıştırmanın işlem günlüğüne aktarılır.
    """

    name: ClassVar[str] = "BaseAgent"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"agent.{self.name}")
        self._execution_log: list[str] = []

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Agent'ın ana görevini çalıştır."""

    def log(self, message: str) -> None:
        entry = f"[{time.strftime('%H:%M:%S')}] [{self.name}] {message}"
        self._execution_log.append(entry)
        self.logger.info(message)

    def get_logs(self) -> list[str]:
        return self._execution_log.copy()

    def clear_logs(self) -> None:
        self._execution_log.clear()


class LLMAgent(BaseAgent):
    """LLM çağıran agentlar için temel sınıf.

    Alt sınıflar `system_prompt` tanımlar (veya `build_system_prompt()`'u ezer)
    ve `ask_json()` / `ask_text()` ile modele soru sorar.
    """

    system_prompt: ClassVar[str] = ""
    max_input_chars: ClassVar[int] = 4000

    def __init__(self, llm_service: LLMService) -> None:
        super().__init__()
        self.llm_service = llm_service

    def build_system_prompt(self) -> str:
        return self.system_prompt

    def truncate(self, text: str, limit: int | None = None) -> str:
        return text[: limit or self.max_input_chars]

    async def ask_text(self, user_prompt: str) -> str:
        return (await self.llm_service.chat(self.build_system_prompt(), user_prompt)).strip()

    async def ask_json(self, user_prompt: str) -> dict:
        data = await self.llm_service.chat_json(self.build_system_prompt(), user_prompt)
        if not isinstance(data, dict):
            raise LLMResponseError()
        return data

    def parse_items(self, model: type[ModelT], items: Iterable[Any] | None) -> list[ModelT]:
        """LLM'in döndürdüğü listeyi modele çevirir; bozuk öğeleri atlar."""
        parsed: list[ModelT] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            try:
                parsed.append(model.model_validate(item))
            except ValidationError:
                self.log(f"Geçersiz {model.__name__} kaydı atlandı")
        return parsed
