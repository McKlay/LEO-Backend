"""
Structured JSON logging configuration for Cloud Run.

Provides consistent, structured logging with request tracing,
performance metrics, and proper log levels.
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Optional
import traceback


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "filename": record.filename,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request_id if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    json_output: bool = True,
    include_timestamp: bool = True
) -> None:
    """
    Configure application logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Use JSON formatting (for production)
        include_timestamp: Include timestamps in logs
    """
    # Get root logger
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set logging level
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Force UTF-8 encoding for Windows compatibility with emojis
    if sys.platform == 'win32' and hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    
    # Set formatter
    if json_output:
        formatter = JSONFormatter()
    else:
        # Simple format for development
        fmt = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        formatter = logging.Formatter(fmt)
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds extra context to log records."""
    
    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Process log message with extra fields."""
        # Add extra fields from adapter context
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        
        return msg, kwargs


def create_logger_with_context(
    name: str,
    request_id: Optional[str] = None,
    **extra_context: Any
) -> LoggerAdapter:
    """
    Create a logger with additional context.
    
    Args:
        name: Logger name
        request_id: Request ID for tracing
        **extra_context: Additional context fields
        
    Returns:
        Logger adapter with context
    """
    logger = get_logger(name)
    context = {"request_id": request_id, **extra_context}
    return LoggerAdapter(logger, context)
