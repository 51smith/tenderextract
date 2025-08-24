"""Logging configuration for the application."""
import logging
import sys
from typing import Any, Dict

from ..config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with additional context."""
        # Add extra context to log record
        if hasattr(record, 'job_id'):
            record.msg = f"[Job: {record.job_id}] {record.msg}"
        
        if hasattr(record, 'user_id'):
            record.msg = f"[User: {record.user_id}] {record.msg}"
            
        return super().format(record)


def setup_logging() -> None:
    """Configure application logging."""
    # Create custom logger
    logger = logging.getLogger("tender_extraction")
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Create formatter
    formatter = StructuredFormatter(settings.log_format)
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Set up FastAPI logging
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = logger.handlers
    
    # Set up access logging
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = logger.handlers


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(f"tender_extraction.{name}")


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for adding contextual information."""
    
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any]):
        super().__init__(logger, extra)
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process the logging message and keyword arguments."""
        # Add extra context to the record, not kwargs
        return msg, kwargs


def get_contextual_logger(name: str, **context: Any) -> LoggerAdapter:
    """Get a logger with contextual information."""
    logger = get_logger(name)
    return LoggerAdapter(logger, context)