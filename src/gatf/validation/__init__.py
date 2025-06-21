"""
Validation Module

This module provides comprehensive validation capabilities for AI agents
including quality validation, metric calculation, and orchestration.
"""

from .engines.quality_validator import QualityValidator
from .metrics.universal_metrics import UniversalMetrics, MetricResult, MetricCategory
from .orchestrators.validation_orchestrator import (
    ValidationOrchestrator,
    ValidationContext,
    ValidationStage,
    StageResult,
    ValidationPipeline
)

__all__ = [
    # Engines
    'QualityValidator',
    
    # Metrics
    'UniversalMetrics',
    'MetricResult',
    'MetricCategory',
    
    # Orchestrators
    'ValidationOrchestrator',
    'ValidationContext',
    'ValidationStage',
    'StageResult',
    'ValidationPipeline'
]

__version__ = '0.1.0'