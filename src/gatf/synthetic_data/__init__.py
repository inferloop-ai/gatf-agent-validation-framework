"""
Synthetic Data Module

This module provides synthetic data generation and validation capabilities
for comprehensive AI agent testing.
"""

from .connectors.base_connector import (
    BaseSyntheticDataConnector,
    PlatformType,
    GenerationStatus,
    DataFormat,
    PlatformConfig,
    GenerationRequest,
    GenerationResponse,
    DataQualityReport
)
from .generators.simple_tabular_generator import SimpleTabularGenerator
from .generators.basic_text_generator import BasicTextGenerator
from .generators.minimal_time_series_generator import (
    MinimalTimeSeriesGenerator,
    TimeSeriesPattern
)
from .validators.data_quality_validator import (
    DataQualityValidator,
    QualityMetrics,
    ValidationRule
)

__all__ = [
    # Connectors
    'BaseSyntheticDataConnector',
    'PlatformType',
    'GenerationStatus',
    'DataFormat',
    'PlatformConfig',
    'GenerationRequest',
    'GenerationResponse',
    'DataQualityReport',
    
    # Generators
    'SimpleTabularGenerator',
    'BasicTextGenerator',
    'MinimalTimeSeriesGenerator',
    'TimeSeriesPattern',
    
    # Validators
    'DataQualityValidator',
    'QualityMetrics',
    'ValidationRule',
]

__version__ = '0.1.0'