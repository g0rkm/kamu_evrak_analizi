import time, functools, logging, random
from typing import TypeVar, Callable, Any

logger = logging.getLogger(__name__)
T = TypeVar("T")

class RetryConfig:
    """Yeniden deneme yapilandirmasi."""
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0, backoff_factor: float = 2.0, jitter: bool = True, retryable_exceptions: tuple = (Exception,)):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

class RetryService:
    """Yeniden deneme servisi."""
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self._stats = {"total_calls": 0, "total_retries": 0, "total_failures": 0, "total_successes": 0}

    def _calculate_delay(self, attempt: int) -> float:
        delay = self.config.base_delay * (self.config.backoff_factor ** attempt)
        delay = min(delay, self.config.max_delay)
        if self.config.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return delay

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        self._stats["total_calls"] += 1
        last_exception = None
        for attempt in range(self.config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                self._stats["total_successes"] += 1
                if attempt > 0:
                    logger.info(f"Basarili: {func.__name__} ({attempt}. yeniden denemede)")
                return result
            except self.config.retryable_exceptions as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    self._stats["total_retries"] += 1
                    logger.warning(f"Yeniden deneme ({attempt + 1}/{self.config.max_retries}): {func.__name__} - {e} - {delay:.1f}s bekleniyor")
                    time.sleep(delay)
                else:
                    self._stats["total_failures"] += 1
                    logger.error(f"Basarisiz: {func.__name__} - {self.config.max_retries} deneme tukendi - {e}")
        raise last_exception

    async def execute_async(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        import asyncio
        self._stats["total_calls"] += 1
        last_exception = None
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                self._stats["total_successes"] += 1
                return result
            except self.config.retryable_exceptions as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    self._stats["total_retries"] += 1
                    logger.warning(f"Async yeniden deneme ({attempt + 1}/{self.config.max_retries}): {func.__name__} - {e}")
                    await asyncio.sleep(delay)
                else:
                    self._stats["total_failures"] += 1
        raise last_exception

    def stats(self) -> dict:
        return dict(self._stats)

    def reset_stats(self):
        self._stats = {"total_calls": 0, "total_retries": 0, "total_failures": 0, "total_successes": 0}


def with_retry(max_retries: int = 3, base_delay: float = 1.0, retryable_exceptions: tuple = (Exception,)):
    """Dekorator olarak yeniden deneme."""
    def decorator(func):
        config = RetryConfig(max_retries=max_retries, base_delay=base_delay, retryable_exceptions=retryable_exceptions)
        service = RetryService(config)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return service.execute(func, *args, **kwargs)
        wrapper._retry_service = service
        return wrapper
    return decorator
