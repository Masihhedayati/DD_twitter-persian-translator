"""
Comprehensive Error Handling Manager for Twitter Monitor Application

This module provides centralized error handling, retry mechanisms, and recovery strategies
for all components of the Twitter monitoring system.
"""

import logging
import time
import traceback
import functools
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling"""
    LOW = "low"          # Minor issues, system continues normally
    MEDIUM = "medium"    # Recoverable errors, may affect some functionality  
    HIGH = "high"        # Serious errors, component degradation
    CRITICAL = "critical" # System-threatening errors, immediate attention needed


class ErrorCategory(Enum):
    """Error categories for specific handling strategies"""
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    DATABASE_ERROR = "database_error"
    FILE_SYSTEM_ERROR = "file_system_error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    CONFIGURATION_ERROR = "configuration_error"
    PROCESSING_ERROR = "processing_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorDetails:
    """Detailed error information for tracking and analysis"""
    error_id: str
    timestamp: datetime
    component: str
    function: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception_type: str
    traceback_info: str
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None


class ErrorHandler:
    """Comprehensive error handling and recovery manager"""
    
    def __init__(self, log_file: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.error_history: List[ErrorDetails] = []
        self.error_counts: Dict[str, int] = {}
        self.component_health: Dict[str, Dict[str, Any]] = {}
        self.log_file = log_file

    def categorize_error(self, exception: Exception, context: Dict[str, Any] = None) -> ErrorCategory:
        """Automatically categorize errors based on exception type and context"""
        exception_name = type(exception).__name__.lower()
        exception_message = str(exception).lower()
        
        # Check message content first for specific error types
        if any(keyword in exception_message for keyword in ['rate limit', 'too many requests', '429']):
            return ErrorCategory.RATE_LIMIT_ERROR
        elif any(keyword in exception_message for keyword in ['unauthorized', '401', '403']):
            return ErrorCategory.AUTHENTICATION_ERROR
        
        # API-related errors (check exception type)
        if any(keyword in exception_name for keyword in ['api', 'http', 'request']):
            return ErrorCategory.API_ERROR
        
        # Network errors
        if any(keyword in exception_name for keyword in ['connection', 'timeout', 'network']):
            return ErrorCategory.NETWORK_ERROR
        
        # Database errors (check both name and message)
        if (any(keyword in exception_name for keyword in ['database', 'sqlite', 'sql']) or
            any(keyword in exception_message for keyword in ['database', 'sqlite', 'sql'])):
            return ErrorCategory.DATABASE_ERROR
        
        # File system errors (be more specific to avoid false matches)
        if (any(keyword in exception_name for keyword in ['file', 'permission']) or
            exception_name in ['ioerror', 'oserror'] or
            any(keyword in exception_message for keyword in ['file not found', 'permission denied', 'directory'])):
            return ErrorCategory.FILE_SYSTEM_ERROR
        
        # Validation errors (be more specific)
        if any(keyword in exception_name for keyword in ['validation', 'type']):
            return ErrorCategory.VALIDATION_ERROR
        
        return ErrorCategory.UNKNOWN_ERROR

    def determine_severity(self, category: ErrorCategory, exception: Exception, context: Dict[str, Any] = None) -> ErrorSeverity:
        """Determine error severity based on category and context"""
        # Critical errors that could break the system
        critical_patterns = ['database connection', 'configuration missing']
        if any(pattern in str(exception).lower() for pattern in critical_patterns):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if category in [ErrorCategory.DATABASE_ERROR, ErrorCategory.AUTHENTICATION_ERROR]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.API_ERROR, ErrorCategory.RATE_LIMIT_ERROR]:
            return ErrorSeverity.MEDIUM
        
        # Low severity by default
        return ErrorSeverity.LOW

    def log_error(
        self,
        exception: Exception,
        component: str,
        function: str,
        context: Dict[str, Any] = None,
        custom_message: str = None
    ) -> str:
        """Log error with comprehensive details and return error ID"""
        
        error_id = f"{component}_{function}_{int(time.time())}"
        category = self.categorize_error(exception, context)
        severity = self.determine_severity(category, exception, context)
        
        error_details = ErrorDetails(
            error_id=error_id,
            timestamp=datetime.now(),
            component=component,
            function=function,
            category=category,
            severity=severity,
            message=custom_message or str(exception),
            exception_type=type(exception).__name__,
            traceback_info=traceback.format_exc(),
            context=context or {}
        )
        
        # Store error for analysis
        self.error_history.append(error_details)
        
        # Update error counts
        error_key = f"{component}_{category.value}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Log with appropriate level
        log_message = f"[{error_id}] {component}.{function}: {error_details.message}"
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # Update component health
        self._update_component_health(component, error_details)
        
        return error_id

    def _update_component_health(self, component: str, error_details: ErrorDetails):
        """Update component health metrics"""
        if component not in self.component_health:
            self.component_health[component] = {
                'last_error': None,
                'error_count_24h': 0,
                'status': 'healthy',
                'last_check': datetime.now()
            }
        
        health = self.component_health[component]
        health['last_error'] = error_details
        health['last_check'] = datetime.now()
        
        # Count errors in last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        recent_errors = [e for e in self.error_history 
                        if e.component == component and e.timestamp > cutoff]
        health['error_count_24h'] = len(recent_errors)
        
        # Determine health status
        if health['error_count_24h'] > 20:
            health['status'] = 'critical'
        elif health['error_count_24h'] > 10:
            health['status'] = 'degraded'
        elif health['error_count_24h'] > 5:
            health['status'] = 'warning'
        else:
            health['status'] = 'healthy'

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics"""
        now = datetime.now()
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)
        
        recent_errors_24h = [e for e in self.error_history if e.timestamp > cutoff_24h]
        recent_errors_1h = [e for e in self.error_history if e.timestamp > cutoff_1h]
        
        # Group by category
        errors_by_category = {}
        for error in recent_errors_24h:
            category = error.category.value
            if category not in errors_by_category:
                errors_by_category[category] = []
            errors_by_category[category].append(error)
        
        # Group by severity
        errors_by_severity = {}
        for error in recent_errors_24h:
            severity = error.severity.value
            if severity not in errors_by_severity:
                errors_by_severity[severity] = []
            errors_by_severity[severity].append(error)
        
        return {
            'total_errors': len(self.error_history),
            'errors_24h': len(recent_errors_24h),
            'errors_1h': len(recent_errors_1h),
            'errors_by_category': {k: len(v) for k, v in errors_by_category.items()},
            'errors_by_severity': {k: len(v) for k, v in errors_by_severity.items()},
            'component_health': self.component_health
        }


# Global error handler instance
global_error_handler = ErrorHandler()


# Convenience functions
def log_error(exception: Exception, component: str, function: str, context: Dict[str, Any] = None) -> str:
    """Convenience function to log errors"""
    return global_error_handler.log_error(exception, component, function, context)


def get_system_health() -> Dict[str, Any]:
    """Get overall system health status"""
    return global_error_handler.get_error_statistics()


def safe_execute(func: Callable, fallback_value: Any = None, component: str = "unknown", log_errors: bool = True):
    """Safely execute a function with error handling"""
    try:
        return func()
    except Exception as e:
        if log_errors:
            global_error_handler.log_error(e, component, func.__name__ if hasattr(func, '__name__') else 'lambda')
        return fallback_value
