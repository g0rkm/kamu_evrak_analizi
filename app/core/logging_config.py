import logging
import logging.handlers
import json
import os
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging(log_level: str = "INFO", log_dir: str = None, enable_file: bool = True):
    """Loglama yapilandirmasi - console + dosya (rotation ile)."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(console)

    if enable_file and log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(JSONFormatter())
        root.addHandler(file_handler)

    json_file = None
    if enable_file and log_dir:
        json_log = os.path.join(log_dir, "app.jsonl")
        json_handler = logging.handlers.RotatingFileHandler(
            json_log,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        json_handler.setFormatter(JSONFormatter())
        root.addHandler(json_handler)
        json_file = json_log

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return {"log_dir": log_dir, "json_file": json_file, "level": log_level}
