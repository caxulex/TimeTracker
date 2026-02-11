"""
Structured Logging Configuration
Phase 3: Production Observability

Provides JSON-formatted logs in production with request_id context,
and human-readable format in development.
"""

import json
import logging
import logging.config
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

# Context variable to store request_id for the current request
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """
    Logging filter that injects request_id from contextvars into every log record.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get(None) or "no-request"  # type: ignore[attr-defined]
        return True


class JsonLogFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging in production.

    Output fields: timestamp, level, message, request_id, module, function, logger
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "no-request"),
            "module": record.module,
            "function": record.funcName,
            "logger": record.name,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Include any extra fields added via logging.info("msg", extra={...})
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "stack_info", "lineno", "funcName", "pathname",
            "filename", "module", "thread", "threadName", "process",
            "processName", "levelname", "levelno", "message", "msecs",
            "request_id", "taskName",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                try:
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        return json.dumps(log_entry, default=str)


def configure_logging(
    log_level: str = "INFO",
    environment: str = "development",
    log_format: str = "json",
) -> None:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        environment: Current environment (development, staging, production)
        log_format: Log format — 'json' for structured, anything else for human-readable
    """
    use_json = environment == "production" or log_format.lower() == "json"

    config: dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": RequestIdFilter,
            },
        },
        "formatters": {},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["request_id"],
            },
        },
        "root": {
            "level": log_level.upper(),
            "handlers": ["console"],
        },
        "loggers": {
            "uvicorn": {"level": "INFO"},
            "uvicorn.access": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "hpack": {"level": "WARNING"},
        },
    }

    if use_json:
        config["formatters"]["json"] = {
            "()": "app.logging_config.JsonLogFormatter",
        }
        config["handlers"]["console"]["formatter"] = "json"
    else:
        config["formatters"]["standard"] = {
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
        config["handlers"]["console"]["formatter"] = "standard"

    logging.config.dictConfig(config)
