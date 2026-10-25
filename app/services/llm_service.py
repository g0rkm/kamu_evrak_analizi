"""OpenAI uyumlu sohbet tamamlama uç noktası için asenkron LLM istemcisi."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time as _time
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.exceptions import CircuitBreakerOpenError, LLMAuthError, LLMError, LLMResponseError, LLMUnavailableError

logger = logging.getLogger("llm_service")

_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_GEMMA_THOUGHT_PATTERN = re.compile(r"<\|channel>thought.*?<channel\|>", re.DOTALL | re.IGNORECASE)
_json_mode_var: ContextVar[bool] = ContextVar("_json_mode_var", default=False)


class _LLMCache:
    """Basit TTL tabanlı bellek-içi LLM yanıt önbelleği."""

    def __init__(self, ttl: int = 3600) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[float, str]] = {}
        self._hits = 0
        self._misses = 0

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    @staticmethod
    def _key(model: str, system: str, user: str, temperature: float) -> str:
        raw = f"{model}|{temperature}|{system}|{user}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, model: str, system: str, user: str, temperature: float) -> str | None:
        if not self.enabled:
            return None
        key = self._key(model, system, user, temperature)
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        ts, value = entry
        if (_time.monotonic() - ts) > self._ttl:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def put(self, model: str, system: str, user: str, temperature: float, value: str) -> None:
        if not self.enabled:
            return
        key = self._key(model, system, user, temperature)
        self._store[key] = (_time.monotonic(), value)

    def deduplicate_key(self, content_hash: str, window_seconds: int = 30) -> str | None:
        """Aynı content_hash ile son window_seconds saniye içinde yapılmış bir istek olup olmadığını kontrol eder."""
        if not self.enabled:
            return None
        dedup_key = f"dedup:{content_hash}"
        entry = self._store.get(dedup_key)
        if entry is None:
            return None
        ts, cache_key = entry
        if (_time.monotonic() - ts) > window_seconds:
            del self._store[dedup_key]
            return None
        return cache_key

    def set_dedup(self, content_hash: str, cache_key: str, window_seconds: int = 30) -> None:
        """Dedup kaydını oluşturur."""
        if not self.enabled:
            return
        dedup_key = f"dedup:{content_hash}"
        self._store[dedup_key] = (_time.monotonic(), cache_key)

    def stats(self) -> dict:
        return {"cache_hits": self._hits, "cache_misses": self._misses, "cache_size": len(self._store)}

    def clear(self) -> None:
        self._store.clear()


@dataclass
class UsageStats:
    total_requests: int = 0
    total_tokens: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0


class LLMService:
    """Retry, kota (429) ve JSON ayrıştırma desteği olan LLM istemcisi.

    Uygulama boyunca tek bir örnek paylaşılır; httpx bağlantı havuzu böylece
    istekler arasında yeniden kullanılır.
    """

    class _CircuitBreaker:
        """Basit devre kesici: art arda N hatada, cooldown süresi boyunca istekleri anında reddeder."""

        def __init__(self, threshold: int = 5, cooldown: float = 60.0) -> None:
            self.threshold = threshold
            self.cooldown = cooldown
            self._failures = 0
            self._open_until: float = 0.0

        def record_success(self) -> None:
            self._failures = 0
            self._open_until = 0.0

        def record_failure(self) -> None:
            self._failures += 1
            if self._failures >= self.threshold:
                self._open_until = _time.monotonic() + self.cooldown
                logger.warning("Circuit breaker açıldı — %.0f sn boyunca LLM istekleri reddedilecek", self.cooldown)

        def check(self) -> None:
            if self._open_until and _time.monotonic() < self._open_until:
                remaining = self._open_until - _time.monotonic()
                raise CircuitBreakerOpenError(
                    f"Yapay zekâ servisi geçici olarak devre dışı. ~{remaining:.0f} sn sonra tekrar deneyin."
                )
            if self._open_until and _time.monotonic() >= self._open_until:
                self._open_until = 0.0

        @property
        def is_open(self) -> bool:
            return bool(self._open_until) and _time.monotonic() < self._open_until

        @property
        def consecutive_failures(self) -> int:
            return self._failures

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
        self._cache = _LLMCache(ttl=settings.LLM_CACHE_TTL_SECONDS)
        self._breaker = self._CircuitBreaker(threshold=max(3, self.max_retries + 1), cooldown=60.0)
        self._token_budget = settings.LLM_TOKEN_BUDGET if settings else 0
        self.num_ctx = getattr(settings, "LLM_NUM_CTX", 16384)
        self.keep_alive = getattr(settings, "LLM_KEEP_ALIVE", "30m")
        self._semaphore = asyncio.Semaphore(max(1, getattr(settings, "LLM_MAX_CONCURRENT_REQUESTS", 2)))

    @property
    def is_local(self) -> bool:
        base = self.api_base.lower()
        return any(h in base for h in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal", ":11434"))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "not-set"

    async def chat(self, system_prompt: str, user_prompt: str, *, temperature: float | None = None) -> str:
        """Tek bir sohbet isteği gönderir, yanıt metnini döndürür."""
        self._breaker.check()
        _req_start = _time.monotonic()
        if self._token_budget > 0 and self.usage.total_tokens >= self._token_budget:
            raise LLMUnavailableError(f"Token bütçesi ({self._token_budget:,} token) aşıldı. Yönetici bütçeyi artırmalıdır.".replace(",", "."))
        temp = self.temperature if temperature is None else temperature
        cached = self._cache.get(self.model, system_prompt, user_prompt, temp)
        if cached is not None:
            self.usage.cache_hits += 1
            return cached

        url = f"{self.api_base}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temp,
        }
        if _json_mode_var.get():
            payload["response_format"] = {"type": "json_object"}
        if self.is_local:
            payload["reasoning_effort"] = "none"
            payload["options"] = {"num_ctx": self.num_ctx}
            if self.keep_alive:
                payload["keep_alive"] = self.keep_alive

        from app.core.logging import request_id_var
        rid = request_id_var.get("-")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "X-Request-ID": rid}

        last_error: LLMError = LLMUnavailableError()
        for attempt in range(1, self.max_retries + 1):
            retry_after: float | None = None
            try:
                async with self._semaphore:
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
                    result = self._parse_completion(response)
                    self._cache.put(self.model, system_prompt, user_prompt, temp, result)
                    self.usage.cache_misses += 1
                    self._breaker.record_success()
                    elapsed = _time.monotonic() - _req_start
                    elapsed_ms = elapsed * 1000
                    self.usage.total_latency_ms += elapsed_ms
                    self.usage.max_latency_ms = max(self.usage.max_latency_ms, elapsed_ms)
                    if elapsed > 30:
                        logger.warning("Yavaş LLM yanıtı: %.1f sn", elapsed)
                    return result

            if attempt < self.max_retries:
                wait = retry_after if retry_after is not None else float(self.RETRY_BACKOFF_BASE ** attempt)
                wait = min(wait, self.MAX_RETRY_WAIT_SECONDS)
                logger.warning("%s — %.0f sn sonra tekrar denenecek (%d/%d)", last_error.message, wait, attempt, self.max_retries)
                await asyncio.sleep(wait)

        self._breaker.record_failure()
        raise last_error

    async def chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        """Yanıtı JSON olarak ayrıştırır; biçim bozuksa bir kez daha ister."""
        token = _json_mode_var.set(True)
        try:
            raw = await self.chat(system_prompt, user_prompt)
            try:
                return self.parse_json(raw)
            except LLMResponseError:
                logger.warning("LLM yanıtı JSON olarak ayrıştırılamadı, yeniden isteniyor")
                raw = await self.chat(system_prompt, f"{user_prompt}\n\nYanıtını YALNIZCA geçerli JSON olarak ver.")
                return self.parse_json(raw)
        finally:
            _json_mode_var.reset(token)

    @staticmethod
    def strip_thinking(raw: str) -> str:
        """Gemma 4 (<|channel>thought...<channel|>) ve Qwen/R1 (<think>...</think>) düşünme bloklarını temizler."""
        cleaned = _GEMMA_THOUGHT_PATTERN.sub("", raw)
        cleaned = _THINK_PATTERN.sub("", cleaned)
        return cleaned.strip()

    @staticmethod
    def parse_json(raw: str) -> Any:
        """Kod bloğu veya açıklama metni içindeki JSON'u ayıklayıp çözer."""
        cleaned = LLMService.strip_thinking(raw)
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
        result = asdict(self.usage)
        result.update(self._cache.stats())
        result["circuit_breaker_open"] = self._breaker.is_open
        result["consecutive_failures"] = self._breaker.consecutive_failures
        return result

    async def ping(self) -> bool:
        """LLM servisine basit bir bağlantı testi yapar."""
        try:
            response = await self.client.get(
                f"{self.api_base}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            return response.is_success
        except (httpx.TransportError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        self._cache.clear()
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
        return self.strip_thinking(content)

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
