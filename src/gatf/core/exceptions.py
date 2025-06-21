"""
GATF Core Exception Hierarchy

This module defines the exception hierarchy for the Global AI Trust Framework.
All custom exceptions inherit from GATFError base class.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import traceback


class GATFError(Exception):
    """Base exception class for all GATF errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        """
        Initialize GATF base error.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code for programmatic handling
            details: Additional error context and metadata
            suggestions: List of suggestions for resolving the error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.suggestions = suggestions or []
        self.timestamp = datetime.utcnow()
        self.traceback = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback if self.details.get("include_traceback") else None
        }


# Configuration Errors
class ConfigurationError(GATFError):
    """Raised when there are configuration-related errors."""
    pass


class InvalidConfigError(ConfigurationError):
    """Raised when configuration values are invalid."""
    pass


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing."""
    pass


# Domain Errors
class DomainError(GATFError):
    """Base class for domain-related errors."""
    pass


class DomainNotFoundError(DomainError):
    """Raised when a requested domain is not found."""
    
    def __init__(self, domain_name: str, available_domains: Optional[List[str]] = None):
        message = f"Domain '{domain_name}' not found"
        suggestions = []
        if available_domains:
            suggestions.append(f"Available domains: {', '.join(available_domains)}")
        super().__init__(message, suggestions=suggestions)


class DomainRegistrationError(DomainError):
    """Raised when domain registration fails."""
    pass


class InvalidDomainError(DomainError):
    """Raised when domain configuration or implementation is invalid."""
    pass


# Validation Errors
class ValidationError(GATFError):
    """Base class for validation-related errors."""
    pass


class ValidationConfigError(ValidationError):
    """Raised when validation configuration is invalid."""
    pass


class ValidationExecutionError(ValidationError):
    """Raised when validation execution fails."""
    pass


class MetricCalculationError(ValidationError):
    """Raised when metric calculation fails."""
    pass


class TestGenerationError(ValidationError):
    """Raised when test generation fails."""
    pass


# Synthetic Data Errors
class SyntheticDataError(GATFError):
    """Base class for synthetic data-related errors."""
    pass


class DataGenerationError(SyntheticDataError):
    """Raised when synthetic data generation fails."""
    pass


class DataQualityError(SyntheticDataError):
    """Raised when generated data doesn't meet quality standards."""
    
    def __init__(self, message: str, quality_metrics: Optional[Dict[str, Any]] = None):
        details = {"quality_metrics": quality_metrics} if quality_metrics else {}
        super().__init__(message, details=details)


class ConnectorError(SyntheticDataError):
    """Raised when synthetic data platform connector fails."""
    pass


class PlatformAuthenticationError(ConnectorError):
    """Raised when authentication with synthetic data platform fails."""
    pass


class PlatformAPIError(ConnectorError):
    """Raised when API calls to synthetic data platform fail."""
    
    def __init__(
        self,
        message: str,
        platform: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None
    ):
        details = {
            "platform": platform,
            "status_code": status_code,
            "response": response
        }
        super().__init__(message, details=details)


# Trust Score Errors
class TrustScoreError(GATFError):
    """Base class for trust score-related errors."""
    pass


class ScoreCalculationError(TrustScoreError):
    """Raised when trust score calculation fails."""
    pass


class BadgeAssignmentError(TrustScoreError):
    """Raised when badge assignment fails."""
    pass


class InsufficientDataError(TrustScoreError):
    """Raised when there's insufficient data for trust score calculation."""
    
    def __init__(self, message: str, required_data: Optional[List[str]] = None):
        suggestions = []
        if required_data:
            suggestions.append(f"Required data: {', '.join(required_data)}")
        super().__init__(message, suggestions=suggestions)


# API Errors
class APIError(GATFError):
    """Base class for API-related errors."""
    pass


class AuthenticationError(APIError):
    """Raised when API authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        suggestions = [
            "Check your API key or token",
            "Ensure your credentials haven't expired",
            "Verify you have the required permissions"
        ]
        super().__init__(message, error_code="AUTH_FAILED", suggestions=suggestions)


class AuthorizationError(APIError):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str, required_permission: Optional[str] = None):
        details = {"required_permission": required_permission} if required_permission else {}
        suggestions = ["Contact your administrator to request access"]
        super().__init__(message, error_code="AUTH_FORBIDDEN", details=details, suggestions=suggestions)


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit: Optional[int] = None
    ):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        if limit:
            details["rate_limit"] = limit
        suggestions = ["Wait before retrying", "Consider upgrading your plan for higher limits"]
        super().__init__(message, error_code="RATE_LIMITED", details=details, suggestions=suggestions)


class InvalidRequestError(APIError):
    """Raised when API request is invalid."""
    pass


# Resource Errors
class ResourceError(GATFError):
    """Base class for resource-related errors."""
    pass


class ResourceNotFoundError(ResourceError):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(message, error_code="NOT_FOUND")


class ResourceExhaustedError(ResourceError):
    """Raised when system resources are exhausted."""
    pass


class ResourceConflictError(ResourceError):
    """Raised when there's a conflict with existing resources."""
    pass


# Integration Errors
class IntegrationError(GATFError):
    """Base class for external integration errors."""
    pass


class CICDIntegrationError(IntegrationError):
    """Raised when CI/CD integration fails."""
    pass


class MonitoringIntegrationError(IntegrationError):
    """Raised when monitoring integration fails."""
    pass


class NotificationError(IntegrationError):
    """Raised when notification delivery fails."""
    pass


# Compliance Errors
class ComplianceError(GATFError):
    """Base class for compliance-related errors."""
    pass


class PrivacyViolationError(ComplianceError):
    """Raised when privacy requirements are violated."""
    
    def __init__(self, message: str, regulation: Optional[str] = None):
        details = {"regulation": regulation} if regulation else {}
        suggestions = [
            "Review data handling practices",
            "Ensure proper consent is obtained",
            "Implement required privacy controls"
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class RegulatoryViolationError(ComplianceError):
    """Raised when regulatory requirements are violated."""
    pass


# Orchestration Errors
class OrchestrationError(GATFError):
    """Base class for orchestration-related errors."""
    pass


class PipelineError(OrchestrationError):
    """Raised when pipeline execution fails."""
    pass


class SchedulingError(OrchestrationError):
    """Raised when task scheduling fails."""
    pass


class DependencyError(OrchestrationError):
    """Raised when dependencies are not met."""
    
    def __init__(self, message: str, missing_dependencies: Optional[List[str]] = None):
        details = {"missing_dependencies": missing_dependencies} if missing_dependencies else {}
        suggestions = ["Install missing dependencies", "Check dependency versions"]
        super().__init__(message, details=details, suggestions=suggestions)


# Utility function for re-raising with context
def raise_with_context(
    original_error: Exception,
    context: str,
    error_class: type = GATFError
) -> None:
    """
    Re-raise an exception with additional context.
    
    Args:
        original_error: The original exception
        context: Additional context about where/why the error occurred
        error_class: The GATF error class to use
    """
    raise error_class(
        f"{context}: {str(original_error)}",
        details={"original_error": str(original_error), "original_type": type(original_error).__name__}
    ) from original_error