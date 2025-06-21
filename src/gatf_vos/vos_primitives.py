"""
VOS Core API Primitives

This module defines the fundamental building blocks of the VOS system.
Each primitive represents a core capability that can be composed to create
complex validation and monitoring workflows.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import uuid


class PrimitiveType(Enum):
    """Types of VOS primitives."""
    DETECTION = "detection"
    CORRECTION = "correction"
    UNCERTAINTY = "uncertainty"
    COORDINATION = "coordination"
    TRUST = "trust"
    MEMORY = "memory"
    HANDOFF = "handoff"
    WORKFLOW = "workflow"
    COMPLIANCE = "compliance"
    BENCHMARK = "benchmark"


class PrimitiveStatus(Enum):
    """Status of primitive execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PrimitiveContext:
    """Context for primitive execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: Optional[str] = None
    domain: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    parent_context: Optional['PrimitiveContext'] = None
    
    def child_context(self) -> 'PrimitiveContext':
        """Create a child context."""
        return PrimitiveContext(
            agent_id=self.agent_id,
            domain=self.domain,
            session_id=self.session_id,
            metadata=self.metadata.copy(),
            parent_context=self
        )


@dataclass
class PrimitiveResult:
    """Result from primitive execution."""
    status: PrimitiveStatus
    data: Any
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: Optional[float] = None


class VOSPrimitive(ABC):
    """
    Base class for all VOS primitives.
    
    Primitives are the atomic units of functionality in VOS.
    They can be composed and orchestrated to create complex behaviors.
    """
    
    def __init__(self, name: str, primitive_type: PrimitiveType):
        self.name = name
        self.primitive_type = primitive_type
        self._callbacks: Dict[str, List[Callable]] = {}
        
    @abstractmethod
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute the primitive."""
        pass
    
    def register_callback(self, event: str, callback: Callable):
        """Register a callback for an event."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
        
    async def _trigger_callbacks(self, event: str, data: Any):
        """Trigger registered callbacks for an event."""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
                    
    def compose(self, other: 'VOSPrimitive') -> 'ComposedPrimitive':
        """Compose this primitive with another."""
        return ComposedPrimitive([self, other])


class ComposedPrimitive(VOSPrimitive):
    """A primitive composed of multiple primitives."""
    
    def __init__(self, primitives: List[VOSPrimitive]):
        super().__init__(
            name=f"Composed({', '.join(p.name for p in primitives)})",
            primitive_type=PrimitiveType.WORKFLOW
        )
        self.primitives = primitives
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute all composed primitives in sequence."""
        results = []
        combined_metrics = {}
        all_errors = []
        all_warnings = []
        
        for primitive in self.primitives:
            result = await primitive.execute(context, **kwargs)
            results.append(result)
            combined_metrics.update(result.metrics)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            
            if result.status == PrimitiveStatus.FAILED:
                return PrimitiveResult(
                    status=PrimitiveStatus.FAILED,
                    data=results,
                    errors=all_errors,
                    warnings=all_warnings,
                    metrics=combined_metrics
                )
                
        return PrimitiveResult(
            status=PrimitiveStatus.COMPLETED,
            data=results,
            errors=all_errors,
            warnings=all_warnings,
            metrics=combined_metrics
        )


class DetectionPrimitive(VOSPrimitive):
    """Base class for detection primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.DETECTION)
        
    @abstractmethod
    async def detect(self, input_data: Any, context: PrimitiveContext) -> Dict[str, Any]:
        """Perform detection on input data."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute detection primitive."""
        try:
            start_time = datetime.utcnow()
            detection_result = await self.detect(kwargs.get('input_data'), context)
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            await self._trigger_callbacks('detection_complete', detection_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=detection_result,
                duration_ms=duration_ms,
                metrics={'detection_latency_ms': duration_ms}
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class CorrectionPrimitive(VOSPrimitive):
    """Base class for correction primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.CORRECTION)
        
    @abstractmethod
    async def correct(self, detection_result: Dict[str, Any], context: PrimitiveContext) -> Dict[str, Any]:
        """Perform correction based on detection result."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute correction primitive."""
        try:
            start_time = datetime.utcnow()
            correction_result = await self.correct(kwargs.get('detection_result'), context)
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            await self._trigger_callbacks('correction_complete', correction_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=correction_result,
                duration_ms=duration_ms,
                metrics={'correction_latency_ms': duration_ms}
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class UncertaintyPrimitive(VOSPrimitive):
    """Base class for uncertainty quantification primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.UNCERTAINTY)
        
    @abstractmethod
    async def quantify(self, input_data: Any, context: PrimitiveContext) -> Dict[str, float]:
        """Quantify uncertainty in input data."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute uncertainty primitive."""
        try:
            uncertainty_scores = await self.quantify(kwargs.get('input_data'), context)
            
            await self._trigger_callbacks('uncertainty_quantified', uncertainty_scores)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=uncertainty_scores,
                metrics={'uncertainty_dimensions': len(uncertainty_scores)}
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class CoordinationPrimitive(VOSPrimitive):
    """Base class for multi-agent coordination primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.COORDINATION)
        
    @abstractmethod
    async def coordinate(self, agents: List[str], task: Dict[str, Any], context: PrimitiveContext) -> Dict[str, Any]:
        """Coordinate multiple agents for a task."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute coordination primitive."""
        try:
            coordination_result = await self.coordinate(
                kwargs.get('agents', []),
                kwargs.get('task', {}),
                context
            )
            
            await self._trigger_callbacks('coordination_complete', coordination_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=coordination_result,
                metrics={'coordinated_agents': len(kwargs.get('agents', []))}
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class TrustPrimitive(VOSPrimitive):
    """Base class for trust scoring primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.TRUST)
        
    @abstractmethod
    async def calculate_trust(self, agent_id: str, validation_results: Dict[str, Any], context: PrimitiveContext) -> float:
        """Calculate trust score for an agent."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute trust primitive."""
        try:
            trust_score = await self.calculate_trust(
                kwargs.get('agent_id'),
                kwargs.get('validation_results', {}),
                context
            )
            
            await self._trigger_callbacks('trust_calculated', {
                'agent_id': kwargs.get('agent_id'),
                'trust_score': trust_score
            })
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data={'trust_score': trust_score},
                metrics={'trust_score': trust_score}
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class MemoryPrimitive(VOSPrimitive):
    """Base class for memory management primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.MEMORY)
        
    @abstractmethod
    async def manage_memory(self, operation: str, data: Any, context: PrimitiveContext) -> Dict[str, Any]:
        """Perform memory management operation."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute memory primitive."""
        try:
            memory_result = await self.manage_memory(
                kwargs.get('operation', 'read'),
                kwargs.get('data'),
                context
            )
            
            await self._trigger_callbacks('memory_operation_complete', memory_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=memory_result
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class HandoffPrimitive(VOSPrimitive):
    """Base class for agent handoff primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.HANDOFF)
        
    @abstractmethod
    async def validate_handoff(self, from_agent: str, to_agent: str, context_data: Dict[str, Any], context: PrimitiveContext) -> Dict[str, Any]:
        """Validate agent handoff."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute handoff primitive."""
        try:
            handoff_result = await self.validate_handoff(
                kwargs.get('from_agent'),
                kwargs.get('to_agent'),
                kwargs.get('context_data', {}),
                context
            )
            
            await self._trigger_callbacks('handoff_validated', handoff_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=handoff_result
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class WorkflowPrimitive(VOSPrimitive):
    """Base class for workflow validation primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.WORKFLOW)
        
    @abstractmethod
    async def validate_workflow(self, workflow_definition: Dict[str, Any], context: PrimitiveContext) -> Dict[str, Any]:
        """Validate workflow definition and execution."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute workflow primitive."""
        try:
            workflow_result = await self.validate_workflow(
                kwargs.get('workflow_definition', {}),
                context
            )
            
            await self._trigger_callbacks('workflow_validated', workflow_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=workflow_result
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class CompliancePrimitive(VOSPrimitive):
    """Base class for compliance validation primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.COMPLIANCE)
        
    @abstractmethod
    async def validate_compliance(self, data: Any, regulations: List[str], context: PrimitiveContext) -> Dict[str, Any]:
        """Validate compliance with regulations."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute compliance primitive."""
        try:
            compliance_result = await self.validate_compliance(
                kwargs.get('data'),
                kwargs.get('regulations', []),
                context
            )
            
            await self._trigger_callbacks('compliance_validated', compliance_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=compliance_result
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )


class BenchmarkPrimitive(VOSPrimitive):
    """Base class for benchmarking primitives."""
    
    def __init__(self, name: str):
        super().__init__(name, PrimitiveType.BENCHMARK)
        
    @abstractmethod
    async def run_benchmark(self, test_suite: str, target: Any, context: PrimitiveContext) -> Dict[str, Any]:
        """Run benchmark test suite."""
        pass
        
    async def execute(self, context: PrimitiveContext, **kwargs) -> PrimitiveResult:
        """Execute benchmark primitive."""
        try:
            benchmark_result = await self.run_benchmark(
                kwargs.get('test_suite'),
                kwargs.get('target'),
                context
            )
            
            await self._trigger_callbacks('benchmark_complete', benchmark_result)
            
            return PrimitiveResult(
                status=PrimitiveStatus.COMPLETED,
                data=benchmark_result
            )
        except Exception as e:
            return PrimitiveResult(
                status=PrimitiveStatus.FAILED,
                data=None,
                errors=[str(e)]
            )