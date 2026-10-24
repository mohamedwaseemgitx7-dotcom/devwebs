"""Structured JSON logging with a per-request correlation ID (logging #100, distributed tracing #102)."""

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Defence in depth: redact anything that looks like a credential even if a developer logs it by mistake.
_REDACT = [
    (re.compile(r"mongodb(\+srv)?://[^\s\"']+"), "mongodb://[REDACTED]"),
    (re.compile(r"(?i)(authorization|password|secret|token|cookie)(\"?\s*[:=]\s*\"?)[^\s\",}]+"), r"\1\2[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED_JWT]"),
]

_STD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def redact(text: str) -> str:
    for pattern, repl in _REDACT:
        text = pattern.sub(repl, text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _STD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return redact(json.dumps(payload, default=str))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # uvicorn's access log duplicates our structured request log
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("pymongo").setLevel(logging.WARNING)
