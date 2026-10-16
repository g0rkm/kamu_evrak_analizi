"""OpenAI-uyumlu LLM API servisi (retry destekli)."""
import asyncio
import httpx
import json
import logging
import re

from app.config import get_settings

logger = logging.getLogger("llm_service")


class LLMService:
    """OpenAI-uyumlu LLM API servisi."""

    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2

    def __init__(self):
        settings = get_settings()
        self.api_base = settings.LLM_API_BASE
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.client = httpx.AsyncClient(timeout=180.0)
        self._total_requests = 0
        self._total_tokens = 0

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Tek bir chat completion istegi gonder, yanit metnini dondur. Retry destekli."""
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.post(url, json=payload, headers=headers)

                if response.status_code == 429 or response.status_code >= 500:
                    wait = self.RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(f"HTTP {response.status_code}, {wait}s sonra tekrar denenecek (deneme {attempt + 1}/{self.MAX_RETRIES})")
                    await asyncio.sleep(wait)
                    last_error = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response
                    )
                    continue

                response.raise_for_status()
                data = response.json()

                usage = data.get("usage", {})
                if usage:
                    self._total_requests += 1
                    tokens = usage.get("total_tokens", 0)
                    self._total_tokens += tokens
                    logger.debug(f"Token kullanimi: {tokens} (toplam: {self._total_tokens})")

                return data["choices"][0]["message"]["content"]

            except httpx.TimeoutException:
                wait = self.RETRY_BACKOFF_BASE ** (attempt + 1)
                logger.warning(f"Timeout, {wait}s sonra tekrar denenecek (deneme {attempt + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(wait)
                last_error = httpx.TimeoutException("LLM istegi zaman asimina ugradi")

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 or e.response.status_code >= 500:
                    wait = self.RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(f"HTTP {e.response.status_code}, {wait}s sonra tekrar denenecek")
                    await asyncio.sleep(wait)
                    last_error = e
                else:
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("LLM istegi basarisiz oldu")

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Chat completion istegi gonder, yaniti JSON olarak parse et."""
        raw = await self.chat(system_prompt, user_prompt)
        cleaned = raw.strip()

        if "```" in cleaned:
            fence_pattern = re.compile(r'```(?:json)?\s*\n?(.*?)\n?\s*```', re.DOTALL)
            match = fence_pattern.search(cleaned)
            if match:
                cleaned = match.group(1).strip()

        if not cleaned.startswith("{") and not cleaned.startswith("["):
            start_brace = cleaned.find("{")
            start_bracket = cleaned.find("[")

            if start_brace == -1 and start_bracket == -1:
                raise ValueError(f"JSON bulunamadi. LLM yaniti: {raw[:500]}")

            if start_bracket == -1 or (start_brace != -1 and start_brace < start_bracket):
                start = start_brace
                end = cleaned.rfind("}") + 1
            else:
                start = start_bracket
                end = cleaned.rfind("]") + 1

            if end <= start:
                raise ValueError(f"Gecersiz JSON yapisi. LLM yaniti: {raw[:500]}")

            cleaned = cleaned[start:end]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse hatasi: {e}. Temizlenmis metin: {cleaned[:500]}")

    def get_usage_stats(self) -> dict:
        """Token kullanim istatistiklerini dondur."""
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
        }

    async def close(self):
        await self.client.aclose()
