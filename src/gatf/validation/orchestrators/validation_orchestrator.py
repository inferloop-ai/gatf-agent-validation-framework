"""
Validation Orchestrator

This module coordinates the validation pipeline, managing the flow of validation
tasks, resource allocation, result aggregation, and pipeline optimization.
"""

from typing import Dict, Any, List, Optional, Union, Callable, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from enum import Enum
import asyncio
import time
import json
import uuid
from collections import defaultdict

from ...core.exceptions import (
    ValidationError,
    PipelineError,
    SchedulingError,
    DependencyError
)
from ...domains.base_domain import ValidationResult, ValidationSeverity, BaseDomain
from ..engines.quality_validator import QualityValidator
from ..metrics.universal_metrics import UniversalMetrics, MetricResult
from ...utils.logging import get_logger, log_performance
from ...utils.caching import CacheManager

logger = get_logger(__name__)


class ValidationStage(Enum):
    """Stages in the validation pipeline."""
    INITIALIZATION = "initialization"
    PRE_VALIDATION = "pre_validation"
    DOMAIN_VALIDATION = "domain_validation"
    QUALITY_VALIDATION = "quality_validation"
    METRIC_CALCULATION = "metric_calculation"
    POST_VALIDATION = "post_validation"
    AGGREGATION = "aggregation"
    FINALIZATION = "finalization"


class ValidationStatus(Enum):
    """Status of validation tasks."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class ValidationTask:
    """Represents a single validation task."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    stage: ValidationStage = ValidationStage.INITIALIZATION
    status: ValidationStatus = ValidationStatus.PENDING
    dependencies: Set[str] = field(default_factory=set)
    validator_func: Optional[Callable] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Any] = None
    error: Optional[Exception] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get task duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if task is complete."""
        return self.status in [
            ValidationStatus.COMPLETED,
            ValidationStatus.FAILED,
            ValidationStatus.CANCELLED,
            ValidationStatus.SKIPPED
        ]


@dataclass
class ValidationPipeline:
    """Represents a validation pipeline configuration."""
    pipeline_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "default_pipeline"
    stages: List[ValidationStage] = field(default_factory=lambda: list(ValidationStage))
    parallel_stages: Set[ValidationStage] = field(default_factory=set)
    stage_timeout: Dict[ValidationStage, float] = field(default_factory=dict)
    skip_conditions: Dict[ValidationStage, Callable] = field(default_factory=dict)
    cache_stages: Set[ValidationStage] = field(default_factory=set)
    
    def __post_init__(self):
        """Initialize default timeouts."""
        default_timeouts = {
            ValidationStage.INITIALIZATION: 5.0,
            ValidationStage.PRE_VALIDATION: 10.0,
            ValidationStage.DOMAIN_VALIDATION: 30.0,
            ValidationStage.QUALITY_VALIDATION: 30.0,
            ValidationStage.METRIC_CALCULATION: 10.0,
            ValidationStage.POST_VALIDATION: 10.0,
            ValidationStage.AGGREGATION: 5.0,
            ValidationStage.FINALIZATION: 5.0
        }
        for stage, timeout in default_timeouts.items():
            if stage not in self.stage_timeout:
                self.stage_timeout[stage] = timeout


@dataclass
class ValidationContext:
    """Context for validation execution."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain_type: Optional[str] = None
    agent_output: Any = None
    expected_output: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    results: List[ValidationResult] = field(default_factory=list)
    metrics: Dict[str, MetricResult] = field(default_factory=dict)
    tasks: Dict[str, ValidationTask] = field(default_factory=dict)
    cache_enabled: bool = True
    
    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result."""
        self.results.append(result)
    
    def add_metric(self, metric_id: str, metric: MetricResult) -> None:
        """Add a metric result."""
        self.metrics[metric_id] = metric


class ValidationOrchestrator:
    """
    Orchestrates the validation pipeline execution.
    
    This class manages:
    - Pipeline configuration and execution
    - Task scheduling and dependency resolution
    - Parallel execution where applicable
    - Result aggregation and caching
    - Error handling and retries
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        """
        Initialize the validation orchestrator.
        
        Args:
            max_workers: Maximum number of parallel workers
            cache_enabled: Enable result caching
            cache_ttl: Cache time-to-live in seconds
        """
        self.max_workers = max_workers
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        
        # Components
        self.quality_validator = QualityValidator()
        self.metrics_calculator = UniversalMetrics()
        self.cache_manager = CacheManager() if cache_enabled else None
        
        # Pipeline registry
        self._pipelines: Dict[str, ValidationPipeline] = {}
        self._default_pipeline = self._create_default_pipeline()
        
        # Execution state
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running_contexts: Dict[str, ValidationContext] = {}
        
    def _create_default_pipeline(self) -> ValidationPipeline:
        """Create the default validation pipeline."""
        pipeline = ValidationPipeline(
            name="default_pipeline",
            stages=list(ValidationStage),
            parallel_stages={
                ValidationStage.DOMAIN_VALIDATION,
                ValidationStage.QUALITY_VALIDATION
            },
            cache_stages={
                ValidationStage.METRIC_CALCULATION,
                ValidationStage.AGGREGATION
            }
        )
        return pipeline
    
    def register_pipeline(self, pipeline: ValidationPipeline) -> None:
        """
        Register a custom validation pipeline.
        
        Args:
            pipeline: Pipeline configuration
        """
        self._pipelines[pipeline.name] = pipeline
        logger.info(f"Registered pipeline: {pipeline.name}")
    
    @log_performance
    def validate(
        self,
        agent_output: Any,
        domain: Optional[Union[str, BaseDomain]] = None,
        expected_output: Optional[Any] = None,
        pipeline_name: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        **options
    ) -> ValidationContext:
        """
        Execute validation pipeline.
        
        Args:
            agent_output: The agent output to validate
            domain: Domain or domain type for validation
            expected_output: Optional expected output
            pipeline_name: Name of pipeline to use
            context_metadata: Additional context metadata
            **options: Additional validation options
            
        Returns:
            Validation context with results
        """
        # Create validation context
        context = ValidationContext(
            agent_output=agent_output,
            expected_output=expected_output,
            metadata=context_metadata or {},
            options=options,
            cache_enabled=self.cache_enabled and options.get("use_cache", True)
        )
        
        # Determine domain
        if isinstance(domain, str):
            context.domain_type = domain
        elif isinstance(domain, BaseDomain):
            context.domain_type = domain.domain_type.value
        
        # Get pipeline
        pipeline = self._get_pipeline(pipeline_name)
        
        # Check cache
        cache_key = self._generate_cache_key(context, pipeline)
        if context.cache_enabled and self.cache_manager:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for validation {context.request_id}")
                return cached_result
        
        # Store running context
        self._running_contexts[context.request_id] = context
        
        try:
            # Execute pipeline
            self._execute_pipeline(context, pipeline)
            
            # Cache results
            if context.cache_enabled and self.cache_manager:
                self.cache_manager.set(cache_key, context, ttl=self.cache_ttl)
            
            return context
            
        except Exception as e:
            logger.error(f"Validation pipeline failed: {str(e)}")
            raise PipelineError(f"Validation failed: {str(e)}")
        finally:
            # Clean up
            self._running_contexts.pop(context.request_id, None)
    
    def _get_pipeline(self, pipeline_name: Optional[str]) -> ValidationPipeline:
        """Get pipeline by name or return default."""
        if pipeline_name and pipeline_name in self._pipelines:
            return self._pipelines[pipeline_name]
        return self._default_pipeline
    
    def _execute_pipeline(
        self,
        context: ValidationContext,
        pipeline: ValidationPipeline
    ) -> None:
        """
        Execute the validation pipeline.
        
        Args:
            context: Validation context
            pipeline: Pipeline configuration
        """
        # Create tasks for each stage
        for stage in pipeline.stages:
            # Check skip condition
            if stage in pipeline.skip_conditions:
                if pipeline.skip_conditions[stage](context):
                    logger.debug(f"Skipping stage {stage.value}")
                    continue
            
            # Create tasks for stage
            tasks = self._create_stage_tasks(stage, context, pipeline)
            for task in tasks:
                context.tasks[task.task_id] = task
        
        # Execute tasks respecting dependencies
        self._execute_tasks(context, pipeline)
        
        # Aggregate results
        self._aggregate_results(context)
    
    def _create_stage_tasks(
        self,
        stage: ValidationStage,
        context: ValidationContext,
        pipeline: ValidationPipeline
    ) -> List[ValidationTask]:
        """Create tasks for a validation stage."""
        tasks = []
        
        if stage == ValidationStage.INITIALIZATION:
            task = ValidationTask(
                name="initialize_validation",
                stage=stage,
                validator_func=lambda: self._initialize_validation(context)
            )
            tasks.append(task)
            
        elif stage == ValidationStage.PRE_VALIDATION:
            task = ValidationTask(
                name="pre_validation_checks",
                stage=stage,
                validator_func=lambda: self._pre_validation_checks(context)
            )
            tasks.append(task)
            
        elif stage == ValidationStage.DOMAIN_VALIDATION:
            if context.domain_type:
                task = ValidationTask(
                    name=f"domain_validation_{context.domain_type}",
                    stage=stage,
                    validator_func=lambda: self._domain_validation(context)
                )
                tasks.append(task)
                
        elif stage == ValidationStage.QUALITY_VALIDATION:
            task = ValidationTask(
                name="quality_validation",
                stage=stage,
                validator_func=lambda: self._quality_validation(context)
            )
            tasks.append(task)
            
        elif stage == ValidationStage.METRIC_CALCULATION:
            task = ValidationTask(
                name="calculate_metrics",
                stage=stage,
                validator_func=lambda: self._calculate_metrics(context),
                dependencies={t.task_id for t in context.tasks.values() 
                            if t.stage in [ValidationStage.DOMAIN_VALIDATION, 
                                         ValidationStage.QUALITY_VALIDATION]}
            )
            tasks.append(task)
            
        elif stage == ValidationStage.POST_VALIDATION:
            task = ValidationTask(
                name="post_validation_processing",
                stage=stage,
                validator_func=lambda: self._post_validation_processing(context),
                dependencies={t.task_id for t in context.tasks.values() 
                            if t.stage == ValidationStage.METRIC_CALCULATION}
            )
            tasks.append(task)
            
        elif stage == ValidationStage.AGGREGATION:
            task = ValidationTask(
                name="aggregate_results",
                stage=stage,
                validator_func=lambda: self._aggregate_stage_results(context),
                dependencies={t.task_id for t in context.tasks.values() 
                            if t.stage == ValidationStage.POST_VALIDATION}
            )
            tasks.append(task)
            
        elif stage == ValidationStage.FINALIZATION:
            task = ValidationTask(
                name="finalize_validation",
                stage=stage,
                validator_func=lambda: self._finalize_validation(context),
                dependencies={t.task_id for t in context.tasks.values() 
                            if t.stage == ValidationStage.AGGREGATION}
            )
            tasks.append(task)
        
        return tasks
    
    def _execute_tasks(
        self,
        context: ValidationContext,
        pipeline: ValidationPipeline
    ) -> None:
        """Execute tasks with dependency resolution."""
        completed_tasks = set()
        futures_to_tasks = {}
        
        while len(completed_tasks) < len(context.tasks):
            # Find tasks ready to run
            ready_tasks = []
            for task_id, task in context.tasks.items():
                if (task_id not in completed_tasks and
                    task.status == ValidationStatus.PENDING and
                    task.dependencies.issubset(completed_tasks)):
                    ready_tasks.append(task)
            
            if not ready_tasks and len(completed_tasks) < len(context.tasks):
                # Deadlock or circular dependency
                raise DependencyError("Circular dependency detected in validation pipeline")
            
            # Submit ready tasks
            for task in ready_tasks:
                # Check if stage can run in parallel
                if task.stage in pipeline.parallel_stages or len(ready_tasks) == 1:
                    future = self._executor.submit(self._execute_task, task, context, pipeline)
                    futures_to_tasks[future] = task
                    task.status = ValidationStatus.RUNNING
                else:
                    # Execute sequentially
                    self._execute_task(task, context, pipeline)
                    completed_tasks.add(task.task_id)
            
            # Wait for parallel tasks to complete
            if futures_to_tasks:
                done_futures, _ = as_completed(futures_to_tasks), set()
                for future in done_futures:
                    task = futures_to_tasks.pop(future)
                    try:
                        future.result()
                        completed_tasks.add(task.task_id)
                    except Exception as e:
                        logger.error(f"Task {task.name} failed: {str(e)}")
                        task.status = ValidationStatus.FAILED
                        task.error = e
                        completed_tasks.add(task.task_id)
    
    def _execute_task(
        self,
        task: ValidationTask,
        context: ValidationContext,
        pipeline: ValidationPipeline
    ) -> None:
        """Execute a single validation task."""
        task.start_time = datetime.utcnow()
        
        try:
            # Get timeout for stage
            timeout = pipeline.stage_timeout.get(task.stage, 30.0)
            
            # Execute with timeout
            if task.validator_func:
                # Simple timeout implementation
                start_time = time.time()
                result = task.validator_func()
                elapsed = time.time() - start_time
                
                if elapsed > timeout:
                    raise SchedulingError(f"Task {task.name} exceeded timeout ({timeout}s)")
                
                task.output_data = result
                task.status = ValidationStatus.COMPLETED
            else:
                task.status = ValidationStatus.SKIPPED
                
        except Exception as e:
            logger.error(f"Task {task.name} failed: {str(e)}")
            task.error = e
            task.status = ValidationStatus.FAILED
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = ValidationStatus.PENDING
                logger.info(f"Retrying task {task.name} (attempt {task.retry_count})")
            
        finally:
            task.end_time = datetime.utcnow()
    
    # Validation stage implementations
    def _initialize_validation(self, context: ValidationContext) -> None:
        """Initialize validation context."""
        logger.debug(f"Initializing validation {context.request_id}")
        
        # Set default options
        context.options.setdefault("strict_mode", False)
        context.options.setdefault("include_suggestions", True)
        context.options.setdefault("max_validation_time", 300)
    
    def _pre_validation_checks(self, context: ValidationContext) -> List[ValidationResult]:
        """Perform pre-validation checks."""
        results = []
        
        # Check input validity
        if context.agent_output is None:
            results.append(ValidationResult(
                check_name="input_validation",
                passed=False,
                score=0.0,
                severity=ValidationSeverity.CRITICAL,
                message="Agent output is None"
            ))
        
        # Check expected output if provided
        if context.expected_output is not None and context.agent_output is None:
            results.append(ValidationResult(
                check_name="output_presence",
                passed=False,
                score=0.0,
                severity=ValidationSeverity.HIGH,
                message="Expected output provided but agent output is None"
            ))
        
        context.results.extend(results)
        return results
    
    def _domain_validation(self, context: ValidationContext) -> List[ValidationResult]:
        """Perform domain-specific validation."""
        if not context.domain_type:
            return []
        
        try:
            # Import domain module dynamically
            from ...domains import get_domain
            
            domain = get_domain(context.domain_type)
            results = domain.validate(
                context.agent_output,
                context.expected_output,
                context.metadata
            )
            
            context.results.extend(results)
            return results
            
        except Exception as e:
            logger.error(f"Domain validation failed: {str(e)}")
            error_result = ValidationResult(
                check_name="domain_validation_error",
                passed=False,
                score=0.0,
                severity=ValidationSeverity.HIGH,
                message=f"Domain validation error: {str(e)}"
            )
            context.results.append(error_result)
            return [error_result]
    
    def _quality_validation(self, context: ValidationContext) -> List[ValidationResult]:
        """Perform quality validation."""
        # Prepare quality validation context
        quality_context = {
            **context.metadata,
            "strict_mode": context.options.get("strict_mode", False)
        }
        
        # Add performance metrics if available
        if "performance_metrics" in context.metadata:
            quality_context["performance_metrics"] = context.metadata["performance_metrics"]
        
        results = self.quality_validator.validate(
            context.agent_output,
            context.expected_output,
            quality_context
        )
        
        context.results.extend(results)
        return results
    
    def _calculate_metrics(self, context: ValidationContext) -> Dict[str, MetricResult]:
        """Calculate validation metrics."""
        # Prepare additional data for metrics
        additional_data = {
            **context.metadata,
            "domain_type": context.domain_type
        }
        
        metrics = self.metrics_calculator.calculate_metrics(
            context.results,
            additional_data
        )
        
        context.metrics.update(metrics)
        return metrics
    
    def _post_validation_processing(self, context: ValidationContext) -> None:
        """Perform post-validation processing."""
        # Add suggestions if enabled
        if context.options.get("include_suggestions", True):
            for result in context.results:
                if not result.passed and not result.suggestions:
                    # Generate generic suggestions based on check type
                    if "accuracy" in result.check_name:
                        result.suggestions.append("Consider retraining the model with more data")
                    elif "performance" in result.check_name:
                        result.suggestions.append("Optimize model inference for better performance")
                    elif "consistency" in result.check_name:
                        result.suggestions.append("Check for non-deterministic behavior in the model")
    
    def _aggregate_stage_results(self, context: ValidationContext) -> None:
        """Aggregate results from all stages."""
        # Group results by severity
        severity_counts = defaultdict(int)
        for result in context.results:
            severity_counts[result.severity] += 1
        
        # Calculate overall validation score
        total_score = sum(r.score for r in context.results)
        num_results = len(context.results)
        overall_score = total_score / num_results if num_results > 0 else 0.0
        
        # Add summary metadata
        context.metadata["validation_summary"] = {
            "total_checks": num_results,
            "passed_checks": sum(1 for r in context.results if r.passed),
            "failed_checks": sum(1 for r in context.results if not r.passed),
            "overall_score": overall_score,
            "severity_distribution": dict(severity_counts),
            "metrics_calculated": len(context.metrics)
        }
    
    def _finalize_validation(self, context: ValidationContext) -> None:
        """Finalize validation results."""
        # Calculate total validation time
        task_times = []
        for task in context.tasks.values():
            if task.duration:
                task_times.append(task.duration.total_seconds())
        
        if task_times:
            context.metadata["validation_performance"] = {
                "total_time": sum(task_times),
                "average_task_time": sum(task_times) / len(task_times),
                "num_tasks": len(context.tasks),
                "parallel_tasks": sum(1 for t in context.tasks.values() 
                                    if t.stage in self._default_pipeline.parallel_stages)
            }
        
        logger.info(f"Validation {context.request_id} completed with "
                   f"{len(context.results)} results and {len(context.metrics)} metrics")
    
    def _aggregate_results(self, context: ValidationContext) -> None:
        """Final aggregation of all results."""
        # This is called after pipeline execution
        # The actual aggregation is done in _aggregate_stage_results
        pass
    
    def _generate_cache_key(
        self,
        context: ValidationContext,
        pipeline: ValidationPipeline
    ) -> str:
        """Generate cache key for validation results."""
        # Create a deterministic key based on inputs
        key_parts = [
            "validation",
            pipeline.name,
            context.domain_type or "none",
            str(hash(json.dumps(str(context.agent_output), sort_keys=True))),
            str(hash(json.dumps(str(context.expected_output), sort_keys=True)))
        ]
        
        # Add relevant options to key
        for opt in ["strict_mode", "include_suggestions"]:
            if opt in context.options:
                key_parts.append(f"{opt}_{context.options[opt]}")
        
        return ":".join(key_parts)
    
    def get_pipeline_info(self, pipeline_name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about a pipeline."""
        pipeline = self._get_pipeline(pipeline_name)
        
        return {
            "pipeline_id": pipeline.pipeline_id,
            "name": pipeline.name,
            "stages": [s.value for s in pipeline.stages],
            "parallel_stages": [s.value for s in pipeline.parallel_stages],
            "cached_stages": [s.value for s in pipeline.cache_stages],
            "stage_timeouts": {s.value: t for s, t in pipeline.stage_timeout.items()}
        }
    
    def get_validation_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a running validation."""
        if request_id not in self._running_contexts:
            return None
        
        context = self._running_contexts[request_id]
        
        # Calculate task statistics
        task_stats = defaultdict(int)
        for task in context.tasks.values():
            task_stats[task.status.value] += 1
        
        return {
            "request_id": request_id,
            "status": "running",
            "task_statistics": dict(task_stats),
            "results_count": len(context.results),
            "metrics_count": len(context.metrics)
        }
    
    def shutdown(self) -> None:
        """Shutdown the orchestrator."""
        self._executor.shutdown(wait=True)
        logger.info("Validation orchestrator shutdown complete")