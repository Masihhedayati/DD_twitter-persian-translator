"""
Centralized Logging Manager for Twitter Monitor Application

This module provides structured logging with multiple handlers, formatters,
and log levels for comprehensive system monitoring and debugging.
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
from dataclasses import dataclass
import traceback


@dataclass
class LogConfig:
    """Configuration for logging setup"""
    log_level: str = "INFO"
    log_dir: str = "./logs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console: bool = True
    enable_file: bool = True
    enable_json: bool = True
    enable_structured: bool = True
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging with JSON output"""
    
    def __init__(self, include_extra=True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record):
        """Format log record as structured JSON"""
        
        # Basic log data
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
            'process': record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if enabled
        if self.include_extra and hasattr(record, '__dict__'):
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                             'pathname', 'filename', 'module', 'lineno', 'funcName',
                             'created', 'msecs', 'relativeCreated', 'thread', 
                             'threadName', 'processName', 'process', 'exc_info',
                             'exc_text', 'stack_info', 'getMessage']:
                    try:
                        # Only include JSON-serializable values
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_data['extra'] = extra_fields
        
        return json.dumps(log_data, default=str)


class ComponentLogger:
    """Component-specific logger with context"""
    
    def __init__(self, component_name: str, base_logger: logging.Logger):
        self.component_name = component_name
        self.base_logger = base_logger
        self.context = {}
    
    def set_context(self, **kwargs):
        """Set persistent context for this component"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear all context"""
        self.context.clear()
    
    def _log_with_context(self, level, message, extra=None, **kwargs):
        """Log with component context"""
        log_extra = {
            'component': self.component_name,
            **self.context,
            **(extra or {}),
            **kwargs
        }
        
        # Use the appropriate logging method
        getattr(self.base_logger, level.lower())(message, extra=log_extra)
    
    def debug(self, message, **kwargs):
        self._log_with_context('DEBUG', message, **kwargs)
    
    def info(self, message, **kwargs):
        self._log_with_context('INFO', message, **kwargs)
    
    def warning(self, message, **kwargs):
        self._log_with_context('WARNING', message, **kwargs)
    
    def error(self, message, **kwargs):
        self._log_with_context('ERROR', message, **kwargs)
    
    def critical(self, message, **kwargs):
        self._log_with_context('CRITICAL', message, **kwargs)
    
    def exception(self, message, **kwargs):
        """Log exception with traceback"""
        self._log_with_context('ERROR', message, exc_info=True, **kwargs)


class LoggingManager:
    """Centralized logging manager for the application"""
    
    def __init__(self, config: LogConfig = None):
        self.config = config or LogConfig()
        self.loggers: Dict[str, ComponentLogger] = {}
        self.root_logger = None
        self.lock = threading.Lock()
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        
        # Create logs directory
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(exist_ok=True)
        
        # Setup root logger
        self.root_logger = logging.getLogger('twitter_monitor')
        self.root_logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        self.root_logger.handlers.clear()
        
        # Add console handler
        if self.config.enable_console:
            self._add_console_handler()
        
        # Add file handlers
        if self.config.enable_file:
            self._add_file_handlers()
        
        # Prevent propagation to root logger
        self.root_logger.propagate = False
    
    def _add_console_handler(self):
        """Add console handler with colored output"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Use standard formatter for console
        formatter = logging.Formatter(self.config.log_format)
        console_handler.setFormatter(formatter)
        self.root_logger.addHandler(console_handler)
    
    def _add_file_handlers(self):
        """Add rotating file handlers"""
        log_dir = Path(self.config.log_dir)
        
        # Standard log file
        app_log_file = log_dir / "app.log"
        app_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count
        )
        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(logging.Formatter(self.config.log_format))
        self.root_logger.addHandler(app_handler)
        
        # JSON structured log file (if enabled)
        if self.config.enable_json:
            json_log_file = log_dir / "app.json"
            json_handler = logging.handlers.RotatingFileHandler(
                json_log_file,
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count
            )
            json_handler.setLevel(logging.DEBUG)
            json_handler.setFormatter(StructuredFormatter())
            self.root_logger.addHandler(json_handler)
        
        # Error-only log file
        error_log_file = log_dir / "errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(self.config.log_format))
        self.root_logger.addHandler(error_handler)
    
    def get_logger(self, component_name: str) -> ComponentLogger:
        """Get or create a component-specific logger"""
        with self.lock:
            if component_name not in self.loggers:
                self.loggers[component_name] = ComponentLogger(
                    component_name, self.root_logger
                )
            return self.loggers[component_name]
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get logging statistics"""
        log_dir = Path(self.config.log_dir)
        
        stats = {
            'log_level': self.config.log_level,
            'handlers_count': len(self.root_logger.handlers),
            'component_loggers': list(self.loggers.keys()),
            'log_files': []
        }
        
        # Collect log file information
        if log_dir.exists():
            for log_file in log_dir.glob("*.log*"):
                try:
                    file_stats = log_file.stat()
                    stats['log_files'].append({
                        'name': log_file.name,
                        'size': file_stats.st_size,
                        'modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat()
                    })
                except OSError:
                    pass
        
        return stats


# Global logging manager instance
_logging_manager = None
_lock = threading.Lock()


def get_logging_manager(config: LogConfig = None) -> LoggingManager:
    """Get or create the global logging manager"""
    global _logging_manager
    
    with _lock:
        if _logging_manager is None:
            _logging_manager = LoggingManager(config)
        return _logging_manager


def get_logger(component_name: str) -> ComponentLogger:
    """Convenience function to get a component logger"""
    return get_logging_manager().get_logger(component_name)
