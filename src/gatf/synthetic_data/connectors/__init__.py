"""
Synthetic Data Platform Connectors

This module provides connectors for various synthetic data generation platforms.
"""

from .base_connector import (
    BaseSyntheticDataConnector,
    PlatformType,
    GenerationStatus,
    DataFormat,
    PlatformConfig,
    GenerationRequest,
    GenerationResponse,
    DataQualityReport
)

__all__ = [
    'BaseSyntheticDataConnector',
    'PlatformType',
    'GenerationStatus',
    'DataFormat',
    'PlatformConfig',
    'GenerationRequest',
    'GenerationResponse',
    'DataQualityReport',
]

# Platform-specific connectors will be added in Phase 2:
# - InferloopConnector
# - GretelConnector
# - MostlyAIConnector
# - SyntheticDataVaultConnector
# - HazyConnector
# - CustomConnector