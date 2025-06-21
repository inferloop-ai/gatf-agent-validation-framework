"""
GATF Logging Utilities

This module provides comprehensive logging functionality for the GATF framework,
including structured logging, performance tracking, and audit logging.
"""

import logging
import json
import time
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union, Callable
from pathlib import Path
from contextlib import contextmanager
from functools import wraps
import structlog
from pythonjsonlogger import jsonlogger


# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


class GATFLoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for GATF with additional context"""
    
    def process(self, msg, kwargs):
        """Add GATF-specific context to log messages"""
        extra = kwargs.get('extra', {})
        extra.update({
            'framework': 'GATF',
            'timestamp': datetime.utcnow().isoformat(),
            'environment': self.extra.get('environment', 'unknown')
        })
        kwargs['extra'] = extra
        return msg, kwargs


def setup_logging(
    level: Union[str, int] = logging.INFO,
    log_file: Optional[Path] = None,
    json_format: bool = True,
    include_console: bool = True,
    environment: str = "development"
) -> logging.Logger:
    """
    Set up logging configuration for GATF
    
    Args:
        level: Logging level
        log_file: Optional path to log file
        json_format: Whether to use JSON format for logs
        include_console: Whether to include console output
        environment: Current environment (development, staging, production)
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("gatf")
    logger.setLevel(level)
    logger.handlers.clear()
    
    # Create formatters
    if json_format:
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            timestamp=True
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Console handler
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    
    # Add custom adapter
    logger = GATFLoggerAdapter(logger, {'environment': environment})
    
    return logger


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (usually module name)
    
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


@contextmanager
def log_performance(
    logger: Union[logging.Logger, structlog.BoundLogger],
    operation: str,
    **extra_context
):
    """
    Context manager for logging performance metrics
    
    Args:
        logger: Logger instance
        operation: Name of the operation being measured
        **extra_context: Additional context to log
    
    Example:
        with log_performance(logger, "validation", domain="finance"):
            # Perform validation
            pass
    """
    start_time = time.time()
    context = {
        'operation': operation,
        'start_time': datetime.utcnow().isoformat(),
        **extra_context
    }
    
    try:
        logger.info(f"Starting {operation}", **context)
        yield
        
        duration = time.time() - start_time
        context.update({
            'duration_seconds': duration,
            'status': 'success',
            'end_time': datetime.utcnow().isoformat()
        })
        logger.info(f"Completed {operation}", **context)
        
    except Exception as e:
        duration = time.time() - start_time
        context.update({
            'duration_seconds': duration,
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc(),
            'end_time': datetime.utcnow().isoformat()
        })
        logger.error(f"Failed {operation}", **context)
        raise


def performance_logger(operation: Optional[str] = None):
    """
    Decorator for logging function performance
    
    Args:
        operation: Optional operation name (defaults to function name)
    
    Example:
        @performance_logger("data_generation")
        def generate_data():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation or func.__name__
            logger = get_logger(func.__module__)
            
            with log_performance(logger, op_name, function=func.__name__):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_audit(
    logger: Union[logging.Logger, structlog.BoundLogger],
    action: str,
    user: Optional[str] = None,
    resource: Optional[str] = None,
    result: str = "success",
    **details
):
    """
    Log an audit event
    
    Args:
        logger: Logger instance
        action: Action being performed
        user: User performing the action
        resource: Resource being accessed
        result: Result of the action (success/failure)
        **details: Additional audit details
    """
    audit_entry = {
        'audit_event': True,
        'action': action,
        'user': user or 'system',
        'resource': resource,
        'result': result,
        'timestamp': datetime.utcnow().isoformat(),
        'details': details
    }
    
    if result == "success":
        logger.info(f"Audit: {action}", **audit_entry)
    else:
        logger.warning(f"Audit: {action} failed", **audit_entry)


class ValidationLogger:
    """Specialized logger for validation events"""
    
    def __init__(self, logger: Optional[structlog.BoundLogger] = None):
        self.logger = logger or get_logger("gatf.validation")
    
    def log_validation_start(self, agent_id: str, domain: str, **context):
        """Log the start of a validation"""
        self.logger.info(
            "Validation started",
            agent_id=agent_id,
            domain=domain,
            event_type="validation_start",
            **context
        )
    
    def log_validation_step(self, agent_id: str, step: str, status: str, **details):
        """Log a validation step"""
        self.logger.info(
            f"Validation step: {step}",
            agent_id=agent_id,
            step=step,
            status=status,
            event_type="validation_step",
            **details
        )
    
    def log_validation_complete(self, agent_id: str, trust_score: float, duration: float, **results):
        """Log validation completion"""
        self.logger.info(
            "Validation completed",
            agent_id=agent_id,
            trust_score=trust_score,
            duration_seconds=duration,
            event_type="validation_complete",
            **results
        )
    
    def log_validation_error(self, agent_id: str, error: Exception, step: Optional[str] = None):
        """Log validation error"""
        self.logger.error(
            "Validation error",
            agent_id=agent_id,
            step=step,
            error=str(error),
            error_type=type(error).__name__,
            traceback=traceback.format_exc(),
            event_type="validation_error"
        )


class MetricsLogger:
    """Specialized logger for metrics and monitoring"""
    
    def __init__(self, logger: Optional[structlog.BoundLogger] = None):
        self.logger = logger or get_logger("gatf.metrics")
    
    def log_metric(self, metric_name: str, value: float, unit: str = "count", **tags):
        """Log a metric value"""
        self.logger.info(
            "Metric recorded",
            metric_name=metric_name,
            value=value,
            unit=unit,
            event_type="metric",
            **tags
        )
    
    def log_counter(self, counter_name: str, increment: int = 1, **tags):
        """Log a counter increment"""
        self.logger.info(
            "Counter incremented",
            counter_name=counter_name,
            increment=increment,
            event_type="counter",
            **tags
        )
    
    def log_gauge(self, gauge_name: str, value: float, **tags):
        """Log a gauge value"""
        self.logger.info(
            "Gauge updated",
            gauge_name=gauge_name,
            value=value,
            event_type="gauge",
            **tags
        )
    
    def log_histogram(self, histogram_name: str, value: float, **tags):
        """Log a histogram value"""
        self.logger.info(
            "Histogram value",
            histogram_name=histogram_name,
            value=value,
            event_type="histogram",
            **tags
        )


# Global logger instances
_main_logger: Optional[logging.Logger] = None
_validation_logger: Optional[ValidationLogger] = None
_metrics_logger: Optional[MetricsLogger] = None


def get_main_logger() -> logging.Logger:
    """Get the main GATF logger"""
    global _main_logger
    if _main_logger is None:
        _main_logger = setup_logging()
    return _main_logger


def get_validation_logger() -> ValidationLogger:
    """Get the validation logger"""
    global _validation_logger
    if _validation_logger is None:
        _validation_logger = ValidationLogger()
    return _validation_logger


def get_metrics_logger() -> MetricsLogger:
    """Get the metrics logger"""
    global _metrics_logger
    if _metrics_logger is None:
        _metrics_logger = MetricsLogger()
    return _metrics_logger