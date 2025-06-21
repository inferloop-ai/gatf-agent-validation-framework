"""
Synthetic Data Generators

This module provides various synthetic data generators for testing AI agents.
"""

from .simple_tabular_generator import SimpleTabularGenerator
from .basic_text_generator import BasicTextGenerator
from .minimal_time_series_generator import (
    MinimalTimeSeriesGenerator,
    TimeSeriesPattern
)

__all__ = [
    'SimpleTabularGenerator',
    'BasicTextGenerator',
    'MinimalTimeSeriesGenerator',
    'TimeSeriesPattern',
]

# Additional generators will be added in Phase 2-3 based on domain needs