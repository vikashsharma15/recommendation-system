import logging
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter.
    Every log line is valid JSON — easy to parse in Render/Datadog/ELK.
    """

    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
        }

        if isinstance(record.msg, dict):
            log.update(record.msg)
        else:
            log["message"] = record.getMessage()

        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)

        return json.dumps(log)


def setup_logging(level: str = "INFO") -> None:
    """Call once at startup — replaces basicConfig."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers = [handler]

    # Suppress noisy third-party loggers
    for noisy in ["uvicorn.access", "httpx", "sentence_transformers"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)