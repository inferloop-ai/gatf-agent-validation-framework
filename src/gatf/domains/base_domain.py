"""
Base Domain Abstract Class

This module defines the abstract base class that all domain-specific validation
modules must implement. It provides a consistent interface for domain validation,
metrics calculation, compliance checking, and test scenario generation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set, Type, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from ..core.exceptions import DomainError, ValidationError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DomainType(Enum):
    """Enumeration of supported domain types."""
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    LEGAL = "legal"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    CYBERSECURITY = "cybersecurity"
    HR = "hr"
    RESEARCH = "research"
    DEVOPS = "devops"
    CUSTOM = "custom"


class ValidationSeverity(Enum):
    """Severity levels for validation results."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    check_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    severity: ValidationSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "score": self.score,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ComplianceRequirement:
    """Represents a compliance requirement for a domain."""
    regulation: str  # e.g., "GDPR", "HIPAA", "SOX"
    requirement_id: str
    description: str
    validation_method: str
    is_mandatory: bool = True
    applicable_regions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "regulation": self.regulation,
            "requirement_id": self.requirement_id,
            "description": self.description,
            "validation_method": self.validation_method,
            "is_mandatory": self.is_mandatory,
            "applicable_regions": self.applicable_regions
        }


@dataclass
class TestScenario:
    """Represents a test scenario for domain validation."""
    scenario_id: str
    name: str
    description: str
    test_data_requirements: Dict[str, Any]
    expected_behavior: str
    validation_criteria: List[str]
    tags: List[str] = field(default_factory=list)
    priority: int = 1  # 1 (highest) to 5 (lowest)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "test_data_requirements": self.test_data_requirements,
            "expected_behavior": self.expected_behavior,
            "validation_criteria": self.validation_criteria,
            "tags": self.tags,
            "priority": self.priority
        }


@dataclass
class DomainMetric:
    """Represents a domain-specific metric."""
    metric_id: str
    name: str
    description: str
    unit: Optional[str] = None
    calculation_method: Optional[str] = None
    threshold_good: Optional[float] = None
    threshold_acceptable: Optional[float] = None
    higher_is_better: bool = True
    
    def evaluate(self, value: float) -> str:
        """Evaluate metric value against thresholds."""
        if self.threshold_good is None or self.threshold_acceptable is None:
            return "unspecified"
        
        if self.higher_is_better:
            if value >= self.threshold_good:
                return "good"
            elif value >= self.threshold_acceptable:
                return "acceptable"
            else:
                return "poor"
        else:
            if value <= self.threshold_good:
                return "good"
            elif value <= self.threshold_acceptable:
                return "acceptable"
            else:
                return "poor"


class BaseDomain(ABC):
    """
    Abstract base class for all domain-specific validation modules.
    
    This class defines the interface that all domain implementations must follow
    to ensure consistency across the framework.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the domain with optional configuration.
        
        Args:
            config: Domain-specific configuration
        """
        self.config = config or {}
        self._validators: Dict[str, Callable] = {}
        self._metrics: Dict[str, DomainMetric] = {}
        self._test_scenarios: Dict[str, TestScenario] = {}
        self._compliance_requirements: Dict[str, ComplianceRequirement] = {}
        self._initialized = False
        
    @property
    @abstractmethod
    def domain_type(self) -> DomainType:
        """Return the domain type."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human-readable domain name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a detailed description of the domain."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Return the domain module version."""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the domain module.
        
        This method should:
        - Register validators
        - Define metrics
        - Load test scenarios
        - Set up compliance requirements
        """
        pass
    
    def ensure_initialized(self) -> None:
        """Ensure the domain is initialized."""
        if not self._initialized:
            self.initialize()
            self._initialized = True
    
    @abstractmethod
    def validate(
        self,
        agent_output: Any,
        expected_output: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResult]:
        """
        Perform domain-specific validation on agent output.
        
        Args:
            agent_output: The output from the AI agent to validate
            expected_output: Optional expected output for comparison
            context: Optional context information for validation
            
        Returns:
            List of validation results
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, DomainMetric]:
        """
        Return domain-specific metrics definitions.
        
        Returns:
            Dictionary mapping metric IDs to metric definitions
        """
        pass
    
    @abstractmethod
    def calculate_metrics(
        self,
        validation_results: List[ValidationResult],
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Calculate domain-specific metrics from validation results.
        
        Args:
            validation_results: List of validation results
            additional_data: Optional additional data for metric calculation
            
        Returns:
            Dictionary mapping metric names to calculated values
        """
        pass
    
    @abstractmethod
    def get_compliance_requirements(
        self,
        region: Optional[str] = None
    ) -> List[ComplianceRequirement]:
        """
        Return applicable compliance requirements.
        
        Args:
            region: Optional region to filter requirements
            
        Returns:
            List of compliance requirements
        """
        pass
    
    @abstractmethod
    def get_test_scenarios(
        self,
        tags: Optional[List[str]] = None
    ) -> List[TestScenario]:
        """
        Return domain-specific test scenarios.
        
        Args:
            tags: Optional tags to filter scenarios
            
        Returns:
            List of test scenarios
        """
        pass
    
    def register_validator(
        self,
        name: str,
        validator_func: Callable[[Any, Optional[Any], Optional[Dict[str, Any]]], ValidationResult]
    ) -> None:
        """
        Register a validation function.
        
        Args:
            name: Name of the validator
            validator_func: Validation function
        """
        self._validators[name] = validator_func
        logger.debug(f"Registered validator '{name}' for domain {self.name}")
    
    def register_metric(self, metric: DomainMetric) -> None:
        """
        Register a domain metric.
        
        Args:
            metric: Metric definition
        """
        self._metrics[metric.metric_id] = metric
        logger.debug(f"Registered metric '{metric.name}' for domain {self.name}")
    
    def register_test_scenario(self, scenario: TestScenario) -> None:
        """
        Register a test scenario.
        
        Args:
            scenario: Test scenario definition
        """
        self._test_scenarios[scenario.scenario_id] = scenario
        logger.debug(f"Registered test scenario '{scenario.name}' for domain {self.name}")
    
    def register_compliance_requirement(self, requirement: ComplianceRequirement) -> None:
        """
        Register a compliance requirement.
        
        Args:
            requirement: Compliance requirement definition
        """
        req_key = f"{requirement.regulation}:{requirement.requirement_id}"
        self._compliance_requirements[req_key] = requirement
        logger.debug(f"Registered compliance requirement '{req_key}' for domain {self.name}")
    
    def get_validator(self, name: str) -> Optional[Callable]:
        """Get a registered validator by name."""
        return self._validators.get(name)
    
    def get_all_validators(self) -> Dict[str, Callable]:
        """Get all registered validators."""
        return self._validators.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert domain information to dictionary.
        
        Returns:
            Dictionary representation of the domain
        """
        self.ensure_initialized()
        return {
            "domain_type": self.domain_type.value,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "validators": list(self._validators.keys()),
            "metrics": {k: v.__dict__ for k, v in self._metrics.items()},
            "test_scenarios": len(self._test_scenarios),
            "compliance_requirements": len(self._compliance_requirements),
            "config": self.config
        }
    
    def validate_config(self) -> List[str]:
        """
        Validate domain configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check for required configuration keys
        required_keys = self.get_required_config_keys()
        for key in required_keys:
            if key not in self.config:
                errors.append(f"Missing required configuration key: {key}")
        
        # Validate configuration values
        validation_errors = self.validate_config_values()
        errors.extend(validation_errors)
        
        return errors
    
    def get_required_config_keys(self) -> List[str]:
        """
        Get list of required configuration keys.
        
        Override in subclasses to specify required configuration.
        
        Returns:
            List of required configuration keys
        """
        return []
    
    def validate_config_values(self) -> List[str]:
        """
        Validate configuration values.
        
        Override in subclasses to implement custom validation.
        
        Returns:
            List of validation errors
        """
        return []
    
    def get_supported_agent_types(self) -> List[str]:
        """
        Get list of supported agent types for this domain.
        
        Override in subclasses to specify supported agent types.
        
        Returns:
            List of supported agent types
        """
        return ["general"]
    
    def get_data_requirements(self) -> Dict[str, Any]:
        """
        Get data requirements for this domain.
        
        Override in subclasses to specify data requirements.
        
        Returns:
            Dictionary describing data requirements
        """
        return {
            "input_format": "any",
            "output_format": "any",
            "required_fields": [],
            "optional_fields": []
        }