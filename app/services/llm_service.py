"""OpenAI uyumlu sohbet tamamlama uç noktası için asenkron LLM istemcisi."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.exceptions import LLMAuthError, LLMError, LLMResponseError, LLMUnavailableError

logger = logging.getLogger("llm_service")

_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


@dataclass
class UsageStats:
    total_requests: int = 0
    total_tokens: int = 0


class LLMService:
    """Retry, kota (429) ve JSON ayrıştırma desteği olan LLM istemcisi.

    Uygulama boyunca tek bir örnek paylaşılır; httpx bağlantı havuzu böylece
    istekler arasında yeniden kullanılır.
    """

    RETRY_BACKOFF_BASE = 2
    MAX_RETRY_WAIT_SECONDS = 30.0

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        settings = settings or get_settings()
        self.api_base = settings.LLM_API_BASE.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_retries = max(1, settings.LLM_MAX_RETRIES)
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS)
        self.usage = UsageStats()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "not-set"

    async def chat(self, system_prompt: str, user_prompt: str, *, temperature: float | None = None) -> str:
        """Tek bir sohbet isteği gönderir, yanıt metnini döndürür."""
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature if temperature is None else temperature,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        last_error: LLMError = LLMUnavailableError()
        for attempt in range(1, self.max_retries + 1):
            retry_after: float | None = None
            try:
                response = await self.client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                last_error = LLMUnavailableError("Yapay zekâ servisi zamanında yanıt vermedi.")
            except httpx.TransportError:
                last_error = LLMUnavailableError("Yapay zekâ servisine bağlanılamadı. Ağ bağlantısını kontrol edin.")
            else:
                status = response.status_code
                if status in (401, 403):
                    raise LLMAuthError()
                if status in _RETRYABLE_STATUS:
                    last_error = LLMUnavailableError(self._status_message(status))
                    retry_after = self._retry_after(response)
                elif response.is_error:
                    raise LLMError(f"Yapay zekâ servisi isteği reddetti (HTTP {status}). {self._error_snippet(response)}".strip())
                else:
                    return self._parse_completion(response)

            if attempt < self.max_retries:
                wait = retry_after if retry_after is not None else float(self.RETRY_BACKOFF_BASE ** attempt)
                wait = min(wait, self.MAX_RETRY_WAIT_SECONDS)
                logger.warning("%s — %.0f sn sonra tekrar denenecek (%d/%d)", last_error.message, wait, attempt, self.max_retries)
                await asyncio.sleep(wait)

        raise last_error

    async def chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        """Yanıtı JSON olarak ayrıştırır; biçim bozuksa bir kez daha ister."""
        raw = await self.chat(system_prompt, user_prompt)
        try:
            return self.parse_json(raw)
        except LLMResponseError:
            logger.warning("LLM yanıtı JSON olarak ayrıştırılamadı, yeniden isteniyor")
            raw = await self.chat(system_prompt, f"{user_prompt}\n\nYanıtını YALNIZCA geçerli JSON olarak ver.")
            return self.parse_json(raw)

    @staticmethod
    def parse_json(raw: str) -> Any:
        """Kod bloğu veya açıklama metni içindeki JSON'u ayıklayıp çözer."""
        cleaned = raw.strip()
        if "```" in cleaned:
            match = _FENCE_PATTERN.search(cleaned)
            if match:
                cleaned = match.group(1).strip()

        if not cleaned.startswith(("{", "[")):
            start_brace, start_bracket = cleaned.find("{"), cleaned.find("[")
            if start_brace == -1 and start_bracket == -1:
                raise LLMResponseError()
            if start_bracket == -1 or (start_brace != -1 and start_brace < start_bracket):
                start, end = start_brace, cleaned.rfind("}") + 1
            else:
                start, end = start_bracket, cleaned.rfind("]") + 1
            if end <= start:
                raise LLMResponseError()
            cleaned = cleaned[start:end]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMResponseError() from exc

    def get_usage_stats(self) -> dict:
        return asdict(self.usage)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _parse_completion(self, response: httpx.Response) -> str:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError() from exc
        if not content:
            raise LLMResponseError("Yapay zekâ servisi boş yanıt döndürdü.")

        usage = data.get("usage") or {}
        self.usage.total_requests += 1
        self.usage.total_tokens += int(usage.get("total_tokens", 0) or 0)
        return content

    @staticmethod
    def _status_message(status: int) -> str:
        if status == 429:
            return "Yapay zekâ servisi istek sınırına ulaştı. Lütfen biraz sonra tekrar deneyin."
        return f"Yapay zekâ servisi geçici olarak kullanılamıyor (HTTP {status})."

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        try:
            return max(0.0, float(value)) if value else None
        except ValueError:
            return None

    @staticmethod
    def _error_snippet(response: httpx.Response) -> str:
        try:
            error = response.json().get("error", {})
            message = error.get("message") if isinstance(error, dict) else str(error)
        except (ValueError, AttributeError):
            message = response.text
        return (message or "")[:200]
