"""
Global AI Trust Framework (GATF")

A comprehensive framework for validating and certifying AI agents across
multiple domains and use cases. The framework provides domain-specific
validation, trust scoring, and synthetic data integration capabilities.

Key Features:
- Domain-specific validation modules
- Trust scoring and badge assignment
- Synthetic data platform integration
- Extensible architecture
- Comprehensive metrics and reporting
"""

from .core import (
    Config,
    DomainRouter,
    TrustFramework,
    get_framework,
    TrustLevel,
    BadgeType,
    TrustScore,
    TrustBadge,
    AgentProfile,
    ValidationSession,
    GATFError,
    ValidationError,
    ConfigurationError,
    DomainError
)

from .domains import (
    BaseDomain,
    ValidationResult,
    ComplianceRequirement,
    TestScenario,
    get_domain_registry
)

from .validation import (
    QualityValidator,
    UniversalMetrics,
    MetricResult,
    MetricCategory,
    ValidationOrchestrator,
    ValidationContext
)

from .synthetic_data import (
    BaseSyntheticDataConnector,
    SimpleTabularGenerator,
    BasicTextGenerator,
    MinimalTimeSeriesGenerator,
    DataQualityValidator
)

from .utils import (
    get_logger,
    get_cache,
    encrypt_data,
    decrypt_data,
    RateLimiter,
    HealthChecker
)

__all__ = [
    # Core
    'Config',
    'DomainRouter',
    'TrustFramework',
    'get_framework',
    'TrustLevel',
    'BadgeType',
    'TrustScore',
    'TrustBadge',
    'AgentProfile',
    'ValidationSession',
    'GATFError',
    'ValidationError',
    'ConfigurationError',
    'DomainError',
    
    # Domains
    'BaseDomain',
    'ValidationResult',
    'ComplianceRequirement',
    'TestScenario',
    'get_domain_registry',
    
    # Validation
    'QualityValidator',
    'UniversalMetrics',
    'MetricResult',
    'MetricCategory',
    'ValidationOrchestrator',
    'ValidationContext',
    
    # Synthetic Data
    'BaseSyntheticDataConnector',
    'SimpleTabularGenerator',
    'BasicTextGenerator',
    'MinimalTimeSeriesGenerator',
    'DataQualityValidator',
    
    # Utils
    'get_logger',
    'get_cache',
    'encrypt_data',
    'decrypt_data',
    'RateLimiter',
    'HealthChecker',
]

__version__ = '0.1.0'
__author__ = 'GATF Team'
__license__ = 'Apache 2.0'