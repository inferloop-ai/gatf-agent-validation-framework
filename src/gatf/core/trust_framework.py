"""
Trust Framework Core

This module provides the core trust framework implementation that orchestrates
validation, scoring, and badge assignment for AI agents across different domains.
"""

from typing import Dict, Any, List, Optional, Tuple, Union, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
from collections import defaultdict

from .config import Config
from .exceptions import (
    TrustFrameworkError,
    ValidationError,
    ConfigurationError,
    DomainError
)
from .domain_router import DomainRouter
from ..domains.base_domain import BaseDomain, ValidationResult
from ..validation.orchestrators.validation_orchestrator import ValidationOrchestrator
from ..validation.metrics.universal_metrics import UniversalMetrics, MetricResult
from ..synthetic_data.connectors.base_connector import (
    BaseSyntheticDataConnector,
    GenerationRequest,
    DataFormat
)
from ..utils.logging import get_logger, log_performance
from ..utils.caching import get_cache

logger = get_logger(__name__)


class TrustLevel(Enum):
    """Trust levels for AI agents."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class BadgeType(Enum):
    """Types of trust badges."""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DOMAIN_EXPERT = "domain_expert"


@dataclass
class TrustScore:
    """Trust score for an AI agent."""
    overall_score: float  # 0-100
    domain_scores: Dict[str, float] = field(default_factory=dict)
    metric_scores: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0  # 0-1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def trust_level(self) -> TrustLevel:
        """Determine trust level based on score."""
        if self.overall_score >= 90:
            return TrustLevel.VERIFIED
        elif self.overall_score >= 75:
            return TrustLevel.HIGH
        elif self.overall_score >= 50:
            return TrustLevel.MEDIUM
        elif self.overall_score >= 25:
            return TrustLevel.LOW
        else:
            return TrustLevel.NONE


@dataclass
class TrustBadge:
    """Trust badge awarded to an AI agent."""
    badge_type: BadgeType
    domain: Optional[str] = None
    score: float = 0.0
    requirements_met: List[str] = field(default_factory=list)
    issued_date: datetime = field(default_factory=datetime.utcnow)
    expiry_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if badge is still valid."""
        if self.expiry_date:
            return datetime.utcnow() < self.expiry_date
        return True


@dataclass
class AgentProfile:
    """Profile of an AI agent being evaluated."""
    agent_id: str
    name: str
    version: Optional[str] = None
    provider: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Initialize agent ID if not provided."""
        if not self.agent_id:
            self.agent_id = str(uuid.uuid4())


@dataclass
class ValidationSession:
    """A validation session for an AI agent."""
    session_id: str
    agent_profile: AgentProfile
    test_cases: List[Dict[str, Any]] = field(default_factory=list)
    results: List[ValidationResult] = field(default_factory=list)
    metrics: Dict[str, MetricResult] = field(default_factory=dict)
    trust_score: Optional[TrustScore] = None
    badges: List[TrustBadge] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: str = "pending"
    
    def __post_init__(self):
        """Initialize session ID if not provided."""
        if not self.session_id:
            self.session_id = str(uuid.uuid4())


class TrustFramework:
    """
    Core Trust Framework for AI agent validation.
    
    This framework orchestrates the entire validation process including:
    - Domain-specific validation
    - Synthetic data generation
    - Metric calculation
    - Trust scoring
    - Badge assignment
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the Trust Framework.
        
        Args:
            config: Framework configuration
        """
        self.config = config or Config()
        self.domain_router = DomainRouter(self.config)
        self.validation_orchestrator = ValidationOrchestrator()
        self.universal_metrics = UniversalMetrics()
        self.cache = get_cache()
        
        # Badge requirements
        self._badge_requirements = self._initialize_badge_requirements()
        
        # Active sessions
        self._sessions: Dict[str, ValidationSession] = {}
        
        # Synthetic data connectors
        self._connectors: Dict[str, BaseSyntheticDataConnector] = {}
        
        logger.info("Trust Framework initialized")
    
    def _initialize_badge_requirements(self) -> Dict[BadgeType, Dict[str, Any]]:
        """Initialize badge requirements."""
        return {
            BadgeType.BRONZE: {
                "min_score": 50,
                "min_domains": 1,
                "required_metrics": ["accuracy", "consistency"],
                "min_test_cases": 10
            },
            BadgeType.SILVER: {
                "min_score": 70,
                "min_domains": 2,
                "required_metrics": ["accuracy", "consistency", "reliability"],
                "min_test_cases": 50
            },
            BadgeType.GOLD: {
                "min_score": 85,
                "min_domains": 3,
                "required_metrics": ["accuracy", "consistency", "reliability", "robustness"],
                "min_test_cases": 100
            },
            BadgeType.PLATINUM: {
                "min_score": 95,
                "min_domains": 5,
                "required_metrics": ["accuracy", "consistency", "reliability", "robustness", "fairness"],
                "min_test_cases": 500
            },
            BadgeType.DOMAIN_EXPERT: {
                "min_domain_score": 90,
                "min_test_cases_per_domain": 100,
                "required_domain_metrics": ["domain_expertise", "compliance"]
            }
        }
    
    @log_performance
    def create_validation_session(
        self,
        agent_profile: AgentProfile,
        test_suite: Optional[str] = None
    ) -> ValidationSession:
        """
        Create a new validation session.
        
        Args:
            agent_profile: Profile of the agent to validate
            test_suite: Optional predefined test suite
            
        Returns:
            Created validation session
        """
        session = ValidationSession(
            session_id=str(uuid.uuid4()),
            agent_profile=agent_profile
        )
        
        # Load test suite if specified
        if test_suite:
            session.test_cases = self._load_test_suite(test_suite)
        
        self._sessions[session.session_id] = session
        logger.info(f"Created validation session {session.session_id} for agent {agent_profile.agent_id}")
        
        return session
    
    @log_performance
    async def validate_agent(
        self,
        session_id: str,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        domains: Optional[List[str]] = None
    ) -> ValidationSession:
        """
        Validate an AI agent.
        
        Args:
            session_id: Validation session ID
            test_cases: Optional test cases (uses session test cases if not provided)
            domains: Optional list of domains to validate (uses agent domains if not provided)
            
        Returns:
            Completed validation session
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValidationError(f"Session {session_id} not found")
        
        try:
            session.status = "running"
            
            # Use provided test cases or session test cases
            cases = test_cases or session.test_cases
            if not cases:
                cases = await self._generate_test_cases(session.agent_profile, domains)
                session.test_cases = cases
            
            # Determine domains to validate
            validation_domains = domains or session.agent_profile.domains
            if not validation_domains:
                validation_domains = ["general"]
            
            # Run validation for each domain
            all_results = []
            domain_scores = {}
            
            for domain in validation_domains:
                logger.info(f"Validating domain: {domain}")
                
                # Get domain-specific test cases
                domain_cases = [c for c in cases if c.get("domain") == domain]
                if not domain_cases:
                    domain_cases = cases  # Use all cases if no domain-specific ones
                
                # Run validation
                domain_results = await self._validate_domain(
                    session,
                    domain,
                    domain_cases
                )
                
                all_results.extend(domain_results)
                
                # Calculate domain score
                domain_score = self._calculate_domain_score(domain_results)
                domain_scores[domain] = domain_score
            
            # Store results
            session.results = all_results
            
            # Calculate metrics
            session.metrics = self.universal_metrics.calculate_metrics(
                all_results,
                {"session_id": session_id}
            )
            
            # Calculate trust score
            session.trust_score = self._calculate_trust_score(
                session.metrics,
                domain_scores
            )
            
            # Assign badges
            session.badges = self._assign_badges(
                session.trust_score,
                session.metrics,
                len(cases),
                validation_domains
            )
            
            # Complete session
            session.end_time = datetime.utcnow()
            session.status = "completed"
            
            logger.info(
                f"Validation completed for session {session_id}. "
                f"Trust score: {session.trust_score.overall_score:.2f}"
            )
            
            return session
            
        except Exception as e:
            session.status = "failed"
            session.end_time = datetime.utcnow()
            logger.error(f"Validation failed for session {session_id}: {str(e)}")
            raise ValidationError(f"Validation failed: {str(e)}")
    
    async def _validate_domain(
        self,
        session: ValidationSession,
        domain: str,
        test_cases: List[Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate agent for a specific domain."""
        results = []
        
        # Get domain validator
        domain_validator = self.domain_router.get_domain(domain)
        
        for test_case in test_cases:
            try:
                # Get agent output (this would be the actual agent call in production)
                agent_output = test_case.get("agent_output")
                if not agent_output:
                    # In production, this would call the actual agent
                    agent_output = await self._get_agent_output(
                        session.agent_profile,
                        test_case.get("input")
                    )
                
                # Validate using domain validator
                case_results = domain_validator.validate(
                    agent_output,
                    test_case.get("expected_output"),
                    test_case.get("context", {})
                )
                
                results.extend(case_results)
                
            except Exception as e:
                logger.error(f"Error validating test case: {str(e)}")
                # Create error result
                results.append(ValidationResult(
                    validator_id=f"{domain}_validator",
                    passed=False,
                    score=0.0,
                    message=f"Validation error: {str(e)}",
                    severity="error",
                    metadata={"test_case": test_case}
                ))
        
        return results
    
    async def _generate_test_cases(
        self,
        agent_profile: AgentProfile,
        domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Generate test cases for validation."""
        test_cases = []
        
        # Use agent domains or provided domains
        target_domains = domains or agent_profile.domains or ["general"]
        
        for domain in target_domains:
            # Get domain-specific test scenarios
            domain_validator = self.domain_router.get_domain(domain)
            scenarios = domain_validator.get_test_scenarios()
            
            for scenario in scenarios[:10]:  # Limit to 10 per domain for now
                test_case = {
                    "domain": domain,
                    "scenario_id": scenario.scenario_id,
                    "name": scenario.name,
                    "input": scenario.input_data,
                    "expected_output": scenario.expected_output,
                    "context": scenario.context
                }
                test_cases.append(test_case)
        
        return test_cases
    
    async def _get_agent_output(
        self,
        agent_profile: AgentProfile,
        input_data: Any
    ) -> Any:
        """
        Get output from the AI agent.
        
        In production, this would make actual API calls to the agent.
        For now, returns mock data.
        """
        # Mock implementation
        return {
            "response": f"Mock response for {input_data}",
            "confidence": 0.85,
            "metadata": {
                "agent_id": agent_profile.agent_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    def _calculate_domain_score(
        self,
        results: List[ValidationResult]
    ) -> float:
        """Calculate score for a domain."""
        if not results:
            return 0.0
        
        # Calculate weighted average of scores
        total_weight = 0.0
        weighted_sum = 0.0
        
        for result in results:
            weight = 1.0
            if result.severity == "critical":
                weight = 3.0
            elif result.severity == "error":
                weight = 2.0
            elif result.severity == "warning":
                weight = 1.0
            
            weighted_sum += result.score * weight
            total_weight += weight
        
        return (weighted_sum / total_weight * 100) if total_weight > 0 else 0.0
    
    def _calculate_trust_score(
        self,
        metrics: Dict[str, MetricResult],
        domain_scores: Dict[str, float]
    ) -> TrustScore:
        """Calculate overall trust score."""
        # Extract metric scores
        metric_scores = {}
        metric_weights = {
            "accuracy": 0.25,
            "reliability": 0.20,
            "consistency": 0.20,
            "robustness": 0.15,
            "fairness": 0.10,
            "performance": 0.10
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric_name, weight in metric_weights.items():
            if metric_name in metrics:
                score = metrics[metric_name].value
                if isinstance(score, (int, float)):
                    metric_scores[metric_name] = float(score) * 100
                    weighted_sum += metric_scores[metric_name] * weight
                    total_weight += weight
        
        # Calculate overall score
        metric_component = (weighted_sum / total_weight) if total_weight > 0 else 0.0
        domain_component = sum(domain_scores.values()) / len(domain_scores) if domain_scores else 0.0
        
        # Weighted combination
        overall_score = 0.6 * metric_component + 0.4 * domain_component
        
        # Calculate confidence based on number of test cases and domains
        confidence = min(1.0, len(domain_scores) / 5.0)
        
        return TrustScore(
            overall_score=overall_score,
            domain_scores=domain_scores,
            metric_scores=metric_scores,
            confidence=confidence
        )
    
    def _assign_badges(
        self,
        trust_score: TrustScore,
        metrics: Dict[str, MetricResult],
        num_test_cases: int,
        domains: List[str]
    ) -> List[TrustBadge]:
        """Assign badges based on performance."""
        badges = []
        
        # Check general badges
        for badge_type in [BadgeType.PLATINUM, BadgeType.GOLD, BadgeType.SILVER, BadgeType.BRONZE]:
            requirements = self._badge_requirements[badge_type]
            
            # Check score requirement
            if trust_score.overall_score < requirements["min_score"]:
                continue
            
            # Check domain requirement
            if len(domains) < requirements["min_domains"]:
                continue
            
            # Check test case requirement
            if num_test_cases < requirements["min_test_cases"]:
                continue
            
            # Check metric requirements
            required_metrics = requirements["required_metrics"]
            if not all(m in metrics for m in required_metrics):
                continue
            
            # All requirements met
            badge = TrustBadge(
                badge_type=badge_type,
                score=trust_score.overall_score,
                requirements_met=[
                    f"Score >= {requirements['min_score']}",
                    f"Domains >= {requirements['min_domains']}",
                    f"Test cases >= {requirements['min_test_cases']}",
                    f"Required metrics: {', '.join(required_metrics)}"
                ],
                expiry_date=datetime.utcnow() + timedelta(days=365),
                metadata={
                    "domains": domains,
                    "test_cases": num_test_cases
                }
            )
            badges.append(badge)
            break  # Only assign highest badge
        
        # Check domain expert badges
        expert_requirements = self._badge_requirements[BadgeType.DOMAIN_EXPERT]
        for domain, score in trust_score.domain_scores.items():
            if score >= expert_requirements["min_domain_score"]:
                badge = TrustBadge(
                    badge_type=BadgeType.DOMAIN_EXPERT,
                    domain=domain,
                    score=score,
                    requirements_met=[
                        f"Domain score >= {expert_requirements['min_domain_score']}",
                        f"Domain: {domain}"
                    ],
                    expiry_date=datetime.utcnow() + timedelta(days=180),
                    metadata={"domain": domain}
                )
                badges.append(badge)
        
        return badges
    
    def _load_test_suite(self, test_suite: str) -> List[Dict[str, Any]]:
        """Load a predefined test suite."""
        # Mock implementation - would load from file/database in production
        return [
            {
                "domain": "general",
                "input": "What is 2+2?",
                "expected_output": "4",
                "context": {"type": "arithmetic"}
            }
        ]
    
    def register_synthetic_connector(
        self,
        platform: str,
        connector: BaseSyntheticDataConnector
    ) -> None:
        """
        Register a synthetic data platform connector.
        
        Args:
            platform: Platform identifier
            connector: Connector instance
        """
        self._connectors[platform] = connector
        logger.info(f"Registered synthetic data connector: {platform}")
    
    def get_session(self, session_id: str) -> Optional[ValidationSession]:
        """Get validation session by ID."""
        return self._sessions.get(session_id)
    
    def get_agent_history(
        self,
        agent_id: str,
        limit: int = 10
    ) -> List[ValidationSession]:
        """Get validation history for an agent."""
        history = []
        
        for session in self._sessions.values():
            if session.agent_profile.agent_id == agent_id:
                history.append(session)
        
        # Sort by start time (most recent first)
        history.sort(key=lambda s: s.start_time, reverse=True)
        
        return history[:limit]
    
    def export_trust_report(
        self,
        session_id: str,
        format: str = "json"
    ) -> Union[str, Dict[str, Any]]:
        """
        Export trust report for a validation session.
        
        Args:
            session_id: Session ID
            format: Output format (json, html, pdf)
            
        Returns:
            Formatted report
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValidationError(f"Session {session_id} not found")
        
        report = {
            "session_id": session.session_id,
            "agent": {
                "id": session.agent_profile.agent_id,
                "name": session.agent_profile.name,
                "version": session.agent_profile.version,
                "provider": session.agent_profile.provider
            },
            "validation_summary": {
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "status": session.status,
                "test_cases": len(session.test_cases),
                "domains": list(session.trust_score.domain_scores.keys()) if session.trust_score else []
            },
            "trust_score": {
                "overall": session.trust_score.overall_score if session.trust_score else 0,
                "trust_level": session.trust_score.trust_level.value if session.trust_score else "none",
                "confidence": session.trust_score.confidence if session.trust_score else 0,
                "domain_scores": session.trust_score.domain_scores if session.trust_score else {},
                "metric_scores": session.trust_score.metric_scores if session.trust_score else {}
            },
            "badges": [
                {
                    "type": badge.badge_type.value,
                    "domain": badge.domain,
                    "score": badge.score,
                    "issued_date": badge.issued_date.isoformat(),
                    "expiry_date": badge.expiry_date.isoformat() if badge.expiry_date else None,
                    "valid": badge.is_valid()
                }
                for badge in session.badges
            ],
            "detailed_metrics": {
                metric_name: {
                    "value": result.value,
                    "unit": result.unit,
                    "category": result.category,
                    "description": result.description
                }
                for metric_name, result in session.metrics.items()
            }
        }
        
        if format == "json":
            return json.dumps(report, indent=2)
        else:
            # Other formats would be implemented here
            return report
    
    def cleanup_sessions(self, older_than_days: int = 30) -> int:
        """
        Clean up old validation sessions.
        
        Args:
            older_than_days: Remove sessions older than this many days
            
        Returns:
            Number of sessions removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        removed = 0
        
        session_ids_to_remove = []
        for session_id, session in self._sessions.items():
            if session.start_time < cutoff_date:
                session_ids_to_remove.append(session_id)
        
        for session_id in session_ids_to_remove:
            del self._sessions[session_id]
            removed += 1
        
        logger.info(f"Cleaned up {removed} old sessions")
        return removed


# Global framework instance
_framework_instance: Optional[TrustFramework] = None


def get_framework(config: Optional[Config] = None) -> TrustFramework:
    """
    Get or create the global Trust Framework instance.
    
    Args:
        config: Optional configuration
        
    Returns:
        Trust Framework instance
    """
    global _framework_instance
    
    if _framework_instance is None:
        _framework_instance = TrustFramework(config)
    
    return _framework_instance