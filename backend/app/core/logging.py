import logging
import sys
import re
from typing import Any
from app.core.config import settings


# Pattern for masking sensitive tokens/passwords
SENSITIVE_PATTERNS = [
    re.compile(r'(password|passwd|pwd|secret|token|authorization|credential)[:=]\s*["\']?([^"\'\s]+)["\']?', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[A-Za-z0-9\-_\.]+', re.IGNORECASE),
]


class SensitiveDataFilter(logging.Filter):
    """Filter that strips out passwords, tokens, and credentials from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in SENSITIVE_PATTERNS:
                record.msg = pattern.sub(r'\1: [MASKED]', record.msg)
        return True


def setup_logging() -> logging.Logger:
    """Configures structured, sanitized logging for the RETIVUE backend."""
    logger = logging.getLogger("retivue")
    log_level = logging.DEBUG if settings.APP_ENV == "development" else logging.INFO
    logger.setLevel(log_level)

    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    # Configure SQLAlchemy logger to avoid echoing passwords
    sql_logger = logging.getLogger("sqlalchemy.engine")
    sql_logger.setLevel(logging.WARNING)

    return logger


logger = setup_logging()

