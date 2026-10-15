from abc import ABC, abstractmethod
from typing import Any
import time
import logging

class BaseAgent(ABC):
    """Tüm agentlar için soyut temel sınıf."""
    
    def __init__(self, name: str, llm_service=None):
        self.name = name
        self.llm_service = llm_service
        self.logger = logging.getLogger(f"agent.{name}")
        self._execution_log: list[str] = []
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Agent'ın ana görevini çalıştır."""
        pass
    
    def log(self, message: str):
        """Execution log'a mesaj ekle."""
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{self.name}] {message}"
        self._execution_log.append(entry)
        self.logger.info(message)
    
    def get_logs(self) -> list[str]:
        return self._execution_log.copy()
    
    def clear_logs(self):
        self._execution_log.clear()

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """LLM servisini çağır ve yanıt döndür. Alt sınıflar bu metodu kullanır."""
        if not self.llm_service:
            raise RuntimeError(f"{self.name}: LLM servisi tanımlanmamış")
        return await self.llm_service.chat(system_prompt, user_prompt)
