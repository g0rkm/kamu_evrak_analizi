"""Merkezi log yapılandırması ve request ID izleme."""
import contextvars
import logging
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def new_request_id() -> str:
    """Yeni bir istek kimliği oluşturur ve ContextVar'a atar."""
    rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    return rid


class RequestIdFilter(logging.Filter):
    """Log kayıtlarına request_id alanı ekler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


_FORMAT = "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
        handler.addFilter(RequestIdFilter())
        root.addHandler(handler)

    # httpx her isteği INFO seviyesinde loglar; API anahtarı içeren URL'ler log'a düşmesin.
    logging.getLogger("httpx").setLevel(logging.WARNING)
