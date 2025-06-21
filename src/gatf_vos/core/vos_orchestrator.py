"""
VOS Trust Framework Orchestrator

The central orchestrator that coordinates all VOS components and manages
the overall validation, monitoring, and correction pipeline.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid

from ..vos_primitives import (
    VOSPrimitive, PrimitiveContext, PrimitiveResult,
    PrimitiveStatus, PrimitiveType
)
from ...core.config import GATFConfig
from ...core.exceptions import ValidationError, ConfigurationError
from ...utils.logging import get_logger


logger = get_logger(__name__)


class OrchestrationMode(Enum):
    """Orchestration execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"
    REAL_TIME = "real_time"


@dataclass
class OrchestrationPlan:
    """Execution plan for orchestration."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: OrchestrationMode = OrchestrationMode.ADAPTIVE
    primitives: List[VOSPrimitive] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    timeout_ms: Optional[int] = None
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    """Result of orchestration execution."""
    plan_id: str
    status: PrimitiveStatus
    primitive_results: Dict[str, PrimitiveResult] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate execution duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


class VOSOrchestrator:
    """
    VOS Trust Framework Orchestrator
    
    Coordinates all VOS components including detection, correction,
    uncertainty quantification, and multi-agent coordination.
    """
    
    def __init__(self, config: GATFConfig):
        self.config = config
        self.logger = logger
        
        # Component registries
        self._primitives: Dict[str, VOSPrimitive] = {}
        self._active_plans: Dict[str, OrchestrationPlan] = {}
        self._execution_history: List[OrchestrationResult] = []
        
        # Runtime components
        self._runtime_monitor = None
        self._correction_engine = None
        self._uncertainty_quantifier = None
        self._multi_agent_coordinator = None
        self._hitl_gateway = None
        self._learning_system = None
        
        # Event handling
        self._event_handlers: Dict[str, List[Any]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        
        # State management
        self._initialized = False
        self._running = False
        
    async def initialize(self):
        """Initialize the VOS orchestrator and all components."""
        if self._initialized:
            return
            
        self.logger.info("Initializing VOS Orchestrator")
        
        try:
            # Initialize runtime components
            await self._initialize_runtime_components()
            
            # Initialize primitives
            await self._initialize_primitives()
            
            # Start event processing
            asyncio.create_task(self._process_events())
            
            self._initialized = True
            self._running = True
            
            self.logger.info("VOS Orchestrator initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize VOS Orchestrator: {e}")
            raise ConfigurationError(f"VOS initialization failed: {e}")
            
    async def _initialize_runtime_components(self):
        """Initialize runtime monitoring and detection components."""
        from ..runtime.runtime_monitor import RuntimeMonitor
        from ..runtime.correction.correction_engine import CorrectionEngine
        from ..runtime.uncertainty.uncertainty_quantifier import UncertaintyQuantifier
        from ..runtime.coordination.multi_agent_coordinator import MultiAgentCoordinator
        from ..hitl.hitl_gateway import HITLGateway
        from ..learning.real_time_learner import RealTimeLearner
        
        self._runtime_monitor = RuntimeMonitor(self.config)
        self._correction_engine = CorrectionEngine(self.config)
        self._uncertainty_quantifier = UncertaintyQuantifier(self.config)
        self._multi_agent_coordinator = MultiAgentCoordinator(self.config)
        self._hitl_gateway = HITLGateway(self.config)
        self._learning_system = RealTimeLearner(self.config)
        
        # Initialize all components
        await asyncio.gather(
            self._runtime_monitor.initialize(),
            self._correction_engine.initialize(),
            self._uncertainty_quantifier.initialize(),
            self._multi_agent_coordinator.initialize(),
            self._hitl_gateway.initialize(),
            self._learning_system.initialize()
        )
        
    async def _initialize_primitives(self):
        """Initialize and register built-in primitives."""
        # Detection primitives
        from ..runtime.detection.hallucination_detector import HallucinationDetectionPrimitive
        from ..runtime.detection.intent_drift_detector import IntentDriftDetectionPrimitive
        from ..runtime.detection.memory_drift_detector import MemoryDriftDetectionPrimitive
        
        # Register detection primitives
        self.register_primitive(HallucinationDetectionPrimitive())
        self.register_primitive(IntentDriftDetectionPrimitive())
        self.register_primitive(MemoryDriftDetectionPrimitive())
        
        # More primitives would be registered here...
        
    def register_primitive(self, primitive: VOSPrimitive):
        """Register a VOS primitive."""
        self._primitives[primitive.name] = primitive
        self.logger.debug(f"Registered primitive: {primitive.name} (type: {primitive.primitive_type})")
        
    def get_primitive(self, name: str) -> Optional[VOSPrimitive]:
        """Get a registered primitive by name."""
        return self._primitives.get(name)
        
    async def create_plan(self, 
                         primitives: List[str],
                         mode: OrchestrationMode = OrchestrationMode.ADAPTIVE,
                         dependencies: Optional[Dict[str, List[str]]] = None,
                         **kwargs) -> OrchestrationPlan:
        """Create an orchestration plan."""
        # Validate primitives exist
        primitive_objects = []
        for prim_name in primitives:
            prim = self.get_primitive(prim_name)
            if not prim:
                raise ValidationError(f"Unknown primitive: {prim_name}")
            primitive_objects.append(prim)
            
        plan = OrchestrationPlan(
            mode=mode,
            primitives=primitive_objects,
            dependencies=dependencies or {},
            **kwargs
        )
        
        self._active_plans[plan.id] = plan
        
        await self._emit_event('plan_created', {
            'plan_id': plan.id,
            'mode': mode.value,
            'primitive_count': len(primitives)
        })
        
        return plan
        
    async def execute_plan(self, plan: OrchestrationPlan, context: PrimitiveContext) -> OrchestrationResult:
        """Execute an orchestration plan."""
        self.logger.info(f"Executing orchestration plan: {plan.id} (mode: {plan.mode})")
        
        result = OrchestrationResult(
            plan_id=plan.id,
            status=PrimitiveStatus.RUNNING
        )
        
        try:
            if plan.mode == OrchestrationMode.SEQUENTIAL:
                await self._execute_sequential(plan, context, result)
            elif plan.mode == OrchestrationMode.PARALLEL:
                await self._execute_parallel(plan, context, result)
            elif plan.mode == OrchestrationMode.ADAPTIVE:
                await self._execute_adaptive(plan, context, result)
            elif plan.mode == OrchestrationMode.REAL_TIME:
                await self._execute_real_time(plan, context, result)
                
            result.status = PrimitiveStatus.COMPLETED
            
        except Exception as e:
            self.logger.error(f"Plan execution failed: {e}")
            result.status = PrimitiveStatus.FAILED
            result.errors.append(str(e))
            
        finally:
            result.end_time = datetime.utcnow()
            self._execution_history.append(result)
            
            if plan.id in self._active_plans:
                del self._active_plans[plan.id]
                
            await self._emit_event('plan_completed', {
                'plan_id': plan.id,
                'status': result.status.value,
                'duration_ms': result.duration_ms
            })
            
        return result
        
    async def _execute_sequential(self, plan: OrchestrationPlan, context: PrimitiveContext, result: OrchestrationResult):
        """Execute primitives sequentially."""
        for primitive in plan.primitives:
            prim_result = await primitive.execute(context)
            result.primitive_results[primitive.name] = prim_result
            
            if prim_result.status == PrimitiveStatus.FAILED:
                raise ValidationError(f"Primitive {primitive.name} failed: {prim_result.errors}")
                
    async def _execute_parallel(self, plan: OrchestrationPlan, context: PrimitiveContext, result: OrchestrationResult):
        """Execute primitives in parallel."""
        tasks = []
        for primitive in plan.primitives:
            task = asyncio.create_task(primitive.execute(context))
            tasks.append((primitive.name, task))
            
        for prim_name, task in tasks:
            prim_result = await task
            result.primitive_results[prim_name] = prim_result
            
    async def _execute_adaptive(self, plan: OrchestrationPlan, context: PrimitiveContext, result: OrchestrationResult):
        """Execute primitives adaptively based on results and dependencies."""
        executed = set()
        pending = set(p.name for p in plan.primitives)
        
        while pending:
            # Find primitives that can be executed
            ready = []
            for prim in plan.primitives:
                if prim.name in pending:
                    deps = plan.dependencies.get(prim.name, [])
                    if all(d in executed for d in deps):
                        ready.append(prim)
                        
            if not ready:
                raise ValidationError("Circular dependency detected in orchestration plan")
                
            # Execute ready primitives in parallel
            tasks = [(p.name, asyncio.create_task(p.execute(context))) for p in ready]
            
            for prim_name, task in tasks:
                prim_result = await task
                result.primitive_results[prim_name] = prim_result
                executed.add(prim_name)
                pending.remove(prim_name)
                
                # Adapt based on results
                if prim_result.status == PrimitiveStatus.FAILED and plan.retry_policy.get('enabled', False):
                    # Implement retry logic
                    retry_count = plan.retry_policy.get('max_retries', 3)
                    for i in range(retry_count):
                        self.logger.info(f"Retrying primitive {prim_name} (attempt {i+1}/{retry_count})")
                        retry_result = await self.get_primitive(prim_name).execute(context)
                        if retry_result.status == PrimitiveStatus.COMPLETED:
                            result.primitive_results[prim_name] = retry_result
                            break
                            
    async def _execute_real_time(self, plan: OrchestrationPlan, context: PrimitiveContext, result: OrchestrationResult):
        """Execute primitives in real-time mode with streaming."""
        # Real-time execution with sub-100ms latency targets
        timeout = plan.timeout_ms or 100  # Default 100ms timeout
        
        async def execute_with_timeout(primitive: VOSPrimitive):
            try:
                return await asyncio.wait_for(
                    primitive.execute(context),
                    timeout=timeout/1000.0
                )
            except asyncio.TimeoutError:
                return PrimitiveResult(
                    status=PrimitiveStatus.FAILED,
                    data=None,
                    errors=[f"Timeout after {timeout}ms"]
                )
                
        tasks = []
        for primitive in plan.primitives:
            task = asyncio.create_task(execute_with_timeout(primitive))
            tasks.append((primitive.name, task))
            
        for prim_name, task in tasks:
            result.primitive_results[prim_name] = await task
            
    async def validate_agent(self, agent_id: str, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive agent validation using VOS pipeline."""
        context = PrimitiveContext(
            agent_id=agent_id,
            metadata=validation_data
        )
        
        # Create adaptive validation plan
        plan = await self.create_plan(
            primitives=[
                'hallucination_detection',
                'intent_drift_detection',
                'memory_drift_detection',
                'uncertainty_quantification',
                'trust_calculation'
            ],
            mode=OrchestrationMode.ADAPTIVE,
            dependencies={
                'trust_calculation': ['hallucination_detection', 'intent_drift_detection', 'memory_drift_detection'],
                'uncertainty_quantification': ['hallucination_detection']
            }
        )
        
        # Execute validation
        result = await self.execute_plan(plan, context)
        
        # Process results
        validation_result = {
            'agent_id': agent_id,
            'status': result.status.value,
            'trust_score': None,
            'detections': {},
            'corrections': {},
            'uncertainties': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Extract results from primitives
        for prim_name, prim_result in result.primitive_results.items():
            if prim_result.status == PrimitiveStatus.COMPLETED:
                if 'detection' in prim_name:
                    validation_result['detections'][prim_name] = prim_result.data
                elif 'trust' in prim_name:
                    validation_result['trust_score'] = prim_result.data.get('trust_score')
                elif 'uncertainty' in prim_name:
                    validation_result['uncertainties'] = prim_result.data
                    
        # Apply corrections if needed
        if any(d.get('issues_found', False) for d in validation_result['detections'].values()):
            correction_plan = await self.create_plan(
                primitives=['correction_engine'],
                mode=OrchestrationMode.REAL_TIME
            )
            correction_result = await self.execute_plan(correction_plan, context)
            validation_result['corrections'] = correction_result.primitive_results.get('correction_engine', {}).data
            
        return validation_result
        
    async def monitor_multi_agent_system(self, agent_ids: List[str], monitoring_config: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor a multi-agent system."""
        context = PrimitiveContext(
            metadata={
                'agent_ids': agent_ids,
                'monitoring_config': monitoring_config
            }
        )
        
        # Create monitoring plan
        plan = await self.create_plan(
            primitives=[
                'multi_agent_coordinator',
                'workflow_validator',
                'handoff_validator',
                'goal_alignment_validator'
            ],
            mode=OrchestrationMode.PARALLEL
        )
        
        # Execute monitoring
        result = await self.execute_plan(plan, context)
        
        return {
            'system_status': result.status.value,
            'agent_count': len(agent_ids),
            'monitoring_results': {
                name: res.data for name, res in result.primitive_results.items()
                if res.status == PrimitiveStatus.COMPLETED
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
    def register_event_handler(self, event_type: str, handler: Any):
        """Register an event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        
    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to registered handlers."""
        await self._event_queue.put({
            'type': event_type,
            'data': data,
            'timestamp': datetime.utcnow()
        })
        
    async def _process_events(self):
        """Process events from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                
                handlers = self._event_handlers.get(event['type'], [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        self.logger.error(f"Error in event handler: {e}")
                        
            except asyncio.TimeoutError:
                continue
                
    async def shutdown(self):
        """Shutdown the VOS orchestrator."""
        self.logger.info("Shutting down VOS Orchestrator")
        
        self._running = False
        
        # Shutdown all components
        shutdown_tasks = []
        
        if self._runtime_monitor:
            shutdown_tasks.append(self._runtime_monitor.shutdown())
        if self._correction_engine:
            shutdown_tasks.append(self._correction_engine.shutdown())
        if self._uncertainty_quantifier:
            shutdown_tasks.append(self._uncertainty_quantifier.shutdown())
        if self._multi_agent_coordinator:
            shutdown_tasks.append(self._multi_agent_coordinator.shutdown())
        if self._hitl_gateway:
            shutdown_tasks.append(self._hitl_gateway.shutdown())
        if self._learning_system:
            shutdown_tasks.append(self._learning_system.shutdown())
            
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        self._initialized = False
        self.logger.info("VOS Orchestrator shutdown complete")
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics."""
        return {
            'active_plans': len(self._active_plans),
            'registered_primitives': len(self._primitives),
            'execution_history_size': len(self._execution_history),
            'primitives_by_type': self._get_primitives_by_type(),
            'recent_executions': self._get_recent_executions()
        }
        
    def _get_primitives_by_type(self) -> Dict[str, int]:
        """Count primitives by type."""
        counts = {}
        for primitive in self._primitives.values():
            prim_type = primitive.primitive_type.value
            counts[prim_type] = counts.get(prim_type, 0) + 1
        return counts
        
    def _get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution summaries."""
        recent = self._execution_history[-limit:]
        return [
            {
                'plan_id': r.plan_id,
                'status': r.status.value,
                'duration_ms': r.duration_ms,
                'primitive_count': len(r.primitive_results),
                'error_count': len(r.errors)
            }
            for r in recent
        ]