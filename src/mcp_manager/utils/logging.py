"""
Enterprise-grade logging infrastructure for MCP Manager.

Provides structured logging with multiple handlers, formatters, and
configuration options suitable for production use.
"""

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

from rich.console import Console
from rich.logging import RichHandler


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "getMessage", "exc_info",
                "exc_text", "stack_info"
            }:
                log_entry[key] = value
                
        return json.dumps(log_entry, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green  
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class MCPLogger:
    """Enterprise logging manager for MCP Manager."""
    
    def __init__(self):
        self._loggers: Dict[str, logging.Logger] = {}
        self._setup_done = False
        
    def setup_logging(
        self,
        level: Union[str, int] = logging.INFO,
        log_file: Optional[Path] = None,
        format_type: str = "text",
        enable_rich: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        **kwargs: Any,
    ) -> None:
        """
        Setup logging configuration.
        
        Args:
            level: Logging level
            log_file: Path to log file (optional)
            format_type: Format type ('text', 'json')
            enable_rich: Enable Rich console output
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            **kwargs: Additional configuration options
        """
        if self._setup_done:
            return
            
        # Convert string level to int
        if isinstance(level, str):
            level = getattr(logging, level.upper())
            
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.handlers.clear()
        
        # Console handler
        if enable_rich:
            console = Console(stderr=True)
            console_handler = RichHandler(
                console=console,
                rich_tracebacks=True,
                markup=True,
                show_path=False,
            )
        else:
            console_handler = logging.StreamHandler(sys.stderr)
            if format_type == "json":
                console_handler.setFormatter(JSONFormatter())
            else:
                formatter = ColoredFormatter(
                    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                )
                console_handler.setFormatter(formatter)
                
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            
            if format_type == "json":
                file_handler.setFormatter(JSONFormatter())
            else:
                file_formatter = logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(name)s | "
                    "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
                )
                file_handler.setFormatter(file_formatter)
                
            file_handler.setLevel(level)
            root_logger.addHandler(file_handler)
            
        self._setup_done = True
        
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger instance.
        
        Args:
            name: Logger name
            
        Returns:
            Logger instance
        """
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)
            
        return self._loggers[name]


# Global logger instance
_logger_manager = MCPLogger()

# Convenience functions
setup_logging = _logger_manager.setup_logging
get_logger = _logger_manager.get_logger

# Module logger
logger = get_logger(__name__)