"""
GATF VOS (Validation Operating System) Framework

The VOS layer provides comprehensive runtime monitoring, detection, correction,
and orchestration capabilities for multi-agent AI systems.
"""

from typing import Dict, Any, List, Optional

# Version info
__version__ = "1.0.0"
__author__ = "GATF VOS Team"

# Core VOS components
from .vos_primitives import (
    VOSPrimitive,
    DetectionPrimitive,
    CorrectionPrimitive,
    UncertaintyPrimitive,
    CoordinationPrimitive,
    TrustPrimitive,
    MemoryPrimitive,
    HandoffPrimitive,
    WorkflowPrimitive,
    CompliancePrimitive,
    BenchmarkPrimitive
)

# Core orchestrator
from .core.vos_orchestrator import VOSOrchestrator
from .core.meta_orchestrator import MetaOrchestrator
from .core.event_coordinator import EventCoordinator
from .core.memory_orchestrator import MemoryOrchestrator
from .core.agent_lifecycle_manager import AgentLifecycleManager

# Runtime monitoring
from .runtime.runtime_monitor import RuntimeMonitor
from .runtime.detection.hallucination_detector import HallucinationDetector
from .runtime.detection.intent_drift_detector import IntentDriftDetector
from .runtime.detection.memory_drift_detector import MemoryDriftDetector
from .runtime.correction.correction_engine import CorrectionEngine
from .runtime.uncertainty.uncertainty_quantifier import UncertaintyQuantifier
from .runtime.coordination.multi_agent_coordinator import MultiAgentCoordinator

# HITL gateway
from .hitl.hitl_gateway import HITLGateway
from .hitl.expert_escalation import ExpertEscalation

# Learning system
from .learning.real_time_learner import RealTimeLearner
from .learning.trust_score_adapter import TrustScoreAdapter

# Benchmarking
from .benchmarking.vos_benchmarks import VOSBenchmark
from .benchmarking.multi_agent_benchmarks import MultiAgentBenchmark

# Infrastructure
from .infrastructure.vos_security import VOSSecurity
from .infrastructure.vos_monitoring import VOSMonitoring
from .infrastructure.vos_config_manager import VOSConfigManager

# CLI
from .cli.vos_cli import VOSCLI

# Core exports
__all__ = [
    # Version
    "__version__",
    "__author__",
    
    # Primitives
    "VOSPrimitive",
    "DetectionPrimitive",
    "CorrectionPrimitive",
    "UncertaintyPrimitive",
    "CoordinationPrimitive",
    "TrustPrimitive",
    "MemoryPrimitive",
    "HandoffPrimitive",
    "WorkflowPrimitive",
    "CompliancePrimitive",
    "BenchmarkPrimitive",
    
    # Core components
    "VOSOrchestrator",
    "MetaOrchestrator",
    "EventCoordinator",
    "MemoryOrchestrator",
    "AgentLifecycleManager",
    
    # Runtime
    "RuntimeMonitor",
    "HallucinationDetector",
    "IntentDriftDetector",
    "MemoryDriftDetector",
    "CorrectionEngine",
    "UncertaintyQuantifier",
    "MultiAgentCoordinator",
    
    # HITL
    "HITLGateway",
    "ExpertEscalation",
    
    # Learning
    "RealTimeLearner",
    "TrustScoreAdapter",
    
    # Benchmarking
    "VOSBenchmark",
    "MultiAgentBenchmark",
    
    # Infrastructure
    "VOSSecurity",
    "VOSMonitoring",
    "VOSConfigManager",
    
    # CLI
    "VOSCLI"
]

# Initialize VOS system on import if configured
def initialize_vos(config: Optional[Dict[str, Any]] = None) -> VOSOrchestrator:
    """
    Initialize the VOS system with optional configuration.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        VOSOrchestrator: Initialized VOS orchestrator instance
    """
    from .core.config import VOSConfig
    
    vos_config = VOSConfig(config or {})
    orchestrator = VOSOrchestrator(vos_config)
    
    return orchestrator