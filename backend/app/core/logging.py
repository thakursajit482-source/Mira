import logging
import sys
from typing import Optional

from backend.app.core.config import settings

_LOGGING_INITIALIZED = False


def setup_logging(log_level: Optional[str] = None) -> None:
    """Initialize structured server logging with appropriate log level and formatting."""
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    level_str = (log_level or settings.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if re-initialized
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers = [handler]

    # Configure uvicorn and sqlalchemy loggers
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    if not settings.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _LOGGING_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """Retrieve a configured logger by component name."""
    if not _LOGGING_INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
