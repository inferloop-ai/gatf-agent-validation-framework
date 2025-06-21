"""
Universal Metrics Module

This module defines cross-domain metrics that can be applied to any AI agent
validation scenario. These metrics provide a standardized way to measure
agent performance across different domains.
"""

from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import numpy as np
from statistics import mean, stdev, median
import json

from ...core.exceptions import MetricCalculationError
from ...domains.base_domain import ValidationResult, ValidationSeverity
from ...utils.logging import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of universal metrics."""
    ACCURACY = "accuracy"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    CONSISTENCY = "consistency"
    COMPLETENESS = "completeness"
    RELEVANCE = "relevance"
    SAFETY = "safety"
    EFFICIENCY = "efficiency"
    ROBUSTNESS = "robustness"
    FAIRNESS = "fairness"


@dataclass
class MetricDefinition:
    """Definition of a universal metric."""
    metric_id: str
    name: str
    type: MetricType
    description: str
    unit: Optional[str] = None
    range_min: float = 0.0
    range_max: float = 1.0
    higher_is_better: bool = True
    aggregation_method: str = "mean"  # mean, median, min, max, sum
    
    def normalize_value(self, value: float) -> float:
        """Normalize value to 0-1 range."""
        if self.range_min == self.range_max:
            return 0.0
        normalized = (value - self.range_min) / (self.range_max - self.range_min)
        return max(0.0, min(1.0, normalized))


@dataclass
class MetricResult:
    """Result of a metric calculation."""
    metric_id: str
    value: float
    normalized_value: float
    confidence: float = 1.0
    sample_size: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "value": self.value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class UniversalMetrics:
    """
    Universal metrics calculator for cross-domain agent validation.
    
    This class provides standard metrics that can be applied across
    all domains to ensure consistent evaluation.
    """
    
    def __init__(self):
        """Initialize universal metrics."""
        self._metric_definitions: Dict[str, MetricDefinition] = {}
        self._custom_calculators: Dict[str, Callable] = {}
        self._initialize_standard_metrics()
        
    def _initialize_standard_metrics(self) -> None:
        """Initialize standard universal metrics."""
        # Accuracy metrics
        self.register_metric(MetricDefinition(
            metric_id="accuracy_score",
            name="Accuracy Score",
            type=MetricType.ACCURACY,
            description="Overall accuracy of agent outputs",
            unit="percentage",
            range_min=0.0,
            range_max=100.0
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="precision",
            name="Precision",
            type=MetricType.ACCURACY,
            description="Ratio of correct positive predictions",
            unit="ratio"
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="recall",
            name="Recall",
            type=MetricType.ACCURACY,
            description="Ratio of correctly identified positives",
            unit="ratio"
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="f1_score",
            name="F1 Score",
            type=MetricType.ACCURACY,
            description="Harmonic mean of precision and recall",
            unit="ratio"
        ))
        
        # Performance metrics
        self.register_metric(MetricDefinition(
            metric_id="response_time",
            name="Response Time",
            type=MetricType.PERFORMANCE,
            description="Average time to generate response",
            unit="seconds",
            range_min=0.0,
            range_max=60.0,
            higher_is_better=False
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="throughput",
            name="Throughput",
            type=MetricType.PERFORMANCE,
            description="Requests processed per second",
            unit="requests/second",
            range_min=0.0,
            range_max=1000.0
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="resource_efficiency",
            name="Resource Efficiency",
            type=MetricType.EFFICIENCY,
            description="Efficiency of resource utilization",
            unit="ratio"
        ))
        
        # Reliability metrics
        self.register_metric(MetricDefinition(
            metric_id="success_rate",
            name="Success Rate",
            type=MetricType.RELIABILITY,
            description="Percentage of successful validations",
            unit="percentage",
            range_min=0.0,
            range_max=100.0
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="error_rate",
            name="Error Rate",
            type=MetricType.RELIABILITY,
            description="Percentage of errors encountered",
            unit="percentage",
            range_min=0.0,
            range_max=100.0,
            higher_is_better=False
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="availability",
            name="Availability",
            type=MetricType.RELIABILITY,
            description="System availability percentage",
            unit="percentage",
            range_min=0.0,
            range_max=100.0
        ))
        
        # Consistency metrics
        self.register_metric(MetricDefinition(
            metric_id="consistency_score",
            name="Consistency Score",
            type=MetricType.CONSISTENCY,
            description="Consistency across multiple runs",
            unit="ratio"
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="determinism_score",
            name="Determinism Score",
            type=MetricType.CONSISTENCY,
            description="Degree of deterministic behavior",
            unit="ratio"
        ))
        
        # Completeness metrics
        self.register_metric(MetricDefinition(
            metric_id="completeness_score",
            name="Completeness Score",
            type=MetricType.COMPLETENESS,
            description="Completeness of agent outputs",
            unit="ratio"
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="coverage_score",
            name="Coverage Score",
            type=MetricType.COMPLETENESS,
            description="Test coverage percentage",
            unit="percentage",
            range_min=0.0,
            range_max=100.0
        ))
        
        # Safety metrics
        self.register_metric(MetricDefinition(
            metric_id="safety_score",
            name="Safety Score",
            type=MetricType.SAFETY,
            description="Overall safety assessment",
            unit="ratio"
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="hallucination_rate",
            name="Hallucination Rate",
            type=MetricType.SAFETY,
            description="Rate of hallucinated outputs",
            unit="percentage",
            range_min=0.0,
            range_max=100.0,
            higher_is_better=False
        ))
        
        # Robustness metrics
        self.register_metric(MetricDefinition(
            metric_id="robustness_score",
            name="Robustness Score",
            type=MetricType.ROBUSTNESS,
            description="Robustness against adversarial inputs",
            unit="ratio"
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="stability_score",
            name="Stability Score",
            type=MetricType.ROBUSTNESS,
            description="Stability under varying conditions",
            unit="ratio"
        ))
        
        # Fairness metrics
        self.register_metric(MetricDefinition(
            metric_id="fairness_score",
            name="Fairness Score",
            type=MetricType.FAIRNESS,
            description="Overall fairness assessment",
            unit="ratio"
        ))
        
        self.register_metric(MetricDefinition(
            metric_id="bias_score",
            name="Bias Score",
            type=MetricType.FAIRNESS,
            description="Degree of bias in outputs",
            unit="ratio",
            higher_is_better=False
        ))
    
    def register_metric(self, metric_def: MetricDefinition) -> None:
        """
        Register a metric definition.
        
        Args:
            metric_def: Metric definition to register
        """
        self._metric_definitions[metric_def.metric_id] = metric_def
        logger.debug(f"Registered metric: {metric_def.name}")
    
    def register_custom_calculator(
        self,
        metric_id: str,
        calculator: Callable[[List[ValidationResult], Dict[str, Any]], float]
    ) -> None:
        """
        Register a custom metric calculator.
        
        Args:
            metric_id: ID of the metric
            calculator: Function to calculate the metric
        """
        self._custom_calculators[metric_id] = calculator
        logger.debug(f"Registered custom calculator for metric: {metric_id}")
    
    def calculate_metrics(
        self,
        validation_results: List[ValidationResult],
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, MetricResult]:
        """
        Calculate all applicable metrics from validation results.
        
        Args:
            validation_results: List of validation results
            additional_data: Optional additional data for calculations
            
        Returns:
            Dictionary mapping metric IDs to results
        """
        metrics = {}
        additional_data = additional_data or {}
        
        # Calculate accuracy metrics
        metrics.update(self._calculate_accuracy_metrics(validation_results))
        
        # Calculate performance metrics
        if "performance_data" in additional_data:
            metrics.update(self._calculate_performance_metrics(
                validation_results,
                additional_data["performance_data"]
            ))
        
        # Calculate reliability metrics
        metrics.update(self._calculate_reliability_metrics(validation_results))
        
        # Calculate consistency metrics
        if "consistency_data" in additional_data:
            metrics.update(self._calculate_consistency_metrics(
                validation_results,
                additional_data["consistency_data"]
            ))
        
        # Calculate completeness metrics
        metrics.update(self._calculate_completeness_metrics(validation_results))
        
        # Calculate safety metrics
        metrics.update(self._calculate_safety_metrics(validation_results))
        
        # Calculate custom metrics
        for metric_id, calculator in self._custom_calculators.items():
            try:
                value = calculator(validation_results, additional_data)
                if metric_id in self._metric_definitions:
                    metric_def = self._metric_definitions[metric_id]
                    normalized_value = metric_def.normalize_value(value)
                else:
                    normalized_value = value
                
                metrics[metric_id] = MetricResult(
                    metric_id=metric_id,
                    value=value,
                    normalized_value=normalized_value,
                    sample_size=len(validation_results)
                )
            except Exception as e:
                logger.error(f"Custom metric calculation failed for {metric_id}: {str(e)}")
        
        return metrics
    
    def _calculate_accuracy_metrics(
        self,
        validation_results: List[ValidationResult]
    ) -> Dict[str, MetricResult]:
        """Calculate accuracy-related metrics."""
        metrics = {}
        
        if not validation_results:
            return metrics
        
        # Overall accuracy score
        accuracy_scores = [r.score for r in validation_results if r.check_name == "accuracy_validation"]
        if accuracy_scores:
            accuracy_value = mean(accuracy_scores) * 100
            metrics["accuracy_score"] = MetricResult(
                metric_id="accuracy_score",
                value=accuracy_value,
                normalized_value=accuracy_value / 100,
                confidence=min(1.0, len(accuracy_scores) / 10),  # Confidence based on sample size
                sample_size=len(accuracy_scores)
            )
        
        # Calculate precision/recall if classification data available
        true_positives = sum(1 for r in validation_results if r.passed and r.details.get("expected_positive", False))
        false_positives = sum(1 for r in validation_results if r.passed and not r.details.get("expected_positive", True))
        false_negatives = sum(1 for r in validation_results if not r.passed and r.details.get("expected_positive", False))
        
        if true_positives + false_positives > 0:
            precision = true_positives / (true_positives + false_positives)
            metrics["precision"] = MetricResult(
                metric_id="precision",
                value=precision,
                normalized_value=precision,
                sample_size=len(validation_results)
            )
        
        if true_positives + false_negatives > 0:
            recall = true_positives / (true_positives + false_negatives)
            metrics["recall"] = MetricResult(
                metric_id="recall",
                value=recall,
                normalized_value=recall,
                sample_size=len(validation_results)
            )
        
        # F1 score
        if "precision" in metrics and "recall" in metrics:
            precision_val = metrics["precision"].value
            recall_val = metrics["recall"].value
            if precision_val + recall_val > 0:
                f1 = 2 * (precision_val * recall_val) / (precision_val + recall_val)
                metrics["f1_score"] = MetricResult(
                    metric_id="f1_score",
                    value=f1,
                    normalized_value=f1,
                    sample_size=len(validation_results)
                )
        
        return metrics
    
    def _calculate_performance_metrics(
        self,
        validation_results: List[ValidationResult],
        performance_data: Dict[str, Any]
    ) -> Dict[str, MetricResult]:
        """Calculate performance-related metrics."""
        metrics = {}
        
        # Response time
        if "response_times" in performance_data:
            response_times = performance_data["response_times"]
            if response_times:
                avg_response_time = mean(response_times)
                metric_def = self._metric_definitions["response_time"]
                metrics["response_time"] = MetricResult(
                    metric_id="response_time",
                    value=avg_response_time,
                    normalized_value=metric_def.normalize_value(avg_response_time),
                    sample_size=len(response_times),
                    metadata={"std_dev": stdev(response_times) if len(response_times) > 1 else 0}
                )
        
        # Throughput
        if "throughput_values" in performance_data:
            throughput_values = performance_data["throughput_values"]
            if throughput_values:
                avg_throughput = mean(throughput_values)
                metric_def = self._metric_definitions["throughput"]
                metrics["throughput"] = MetricResult(
                    metric_id="throughput",
                    value=avg_throughput,
                    normalized_value=metric_def.normalize_value(avg_throughput),
                    sample_size=len(throughput_values)
                )
        
        # Resource efficiency
        if "resource_usage" in performance_data:
            resource_data = performance_data["resource_usage"]
            if "cpu_usage" in resource_data and "memory_usage" in resource_data:
                # Simple efficiency calculation: inverse of resource usage
                cpu_efficiency = 1 - (resource_data["cpu_usage"] / 100)
                memory_efficiency = 1 - (resource_data["memory_usage"] / 100)
                resource_efficiency = (cpu_efficiency + memory_efficiency) / 2
                
                metrics["resource_efficiency"] = MetricResult(
                    metric_id="resource_efficiency",
                    value=resource_efficiency,
                    normalized_value=resource_efficiency,
                    metadata={
                        "cpu_usage": resource_data["cpu_usage"],
                        "memory_usage": resource_data["memory_usage"]
                    }
                )
        
        return metrics
    
    def _calculate_reliability_metrics(
        self,
        validation_results: List[ValidationResult]
    ) -> Dict[str, MetricResult]:
        """Calculate reliability-related metrics."""
        metrics = {}
        
        if not validation_results:
            return metrics
        
        # Success rate
        successful = sum(1 for r in validation_results if r.passed)
        success_rate = (successful / len(validation_results)) * 100
        
        metrics["success_rate"] = MetricResult(
            metric_id="success_rate",
            value=success_rate,
            normalized_value=success_rate / 100,
            sample_size=len(validation_results)
        )
        
        # Error rate
        errors = sum(1 for r in validation_results if r.severity in [ValidationSeverity.HIGH, ValidationSeverity.CRITICAL])
        error_rate = (errors / len(validation_results)) * 100
        
        metric_def = self._metric_definitions["error_rate"]
        metrics["error_rate"] = MetricResult(
            metric_id="error_rate",
            value=error_rate,
            normalized_value=metric_def.normalize_value(error_rate),
            sample_size=len(validation_results)
        )
        
        return metrics
    
    def _calculate_consistency_metrics(
        self,
        validation_results: List[ValidationResult],
        consistency_data: Dict[str, Any]
    ) -> Dict[str, MetricResult]:
        """Calculate consistency-related metrics."""
        metrics = {}
        
        # Consistency score from validation results
        consistency_results = [r for r in validation_results if r.check_name == "consistency_validation"]
        if consistency_results:
            consistency_scores = [r.score for r in consistency_results]
            avg_consistency = mean(consistency_scores)
            
            metrics["consistency_score"] = MetricResult(
                metric_id="consistency_score",
                value=avg_consistency,
                normalized_value=avg_consistency,
                sample_size=len(consistency_scores),
                metadata={"std_dev": stdev(consistency_scores) if len(consistency_scores) > 1 else 0}
            )
        
        # Determinism score
        if "determinism_tests" in consistency_data:
            deterministic_runs = consistency_data["determinism_tests"]
            if deterministic_runs:
                determinism_score = sum(1 for r in deterministic_runs if r) / len(deterministic_runs)
                metrics["determinism_score"] = MetricResult(
                    metric_id="determinism_score",
                    value=determinism_score,
                    normalized_value=determinism_score,
                    sample_size=len(deterministic_runs)
                )
        
        return metrics
    
    def _calculate_completeness_metrics(
        self,
        validation_results: List[ValidationResult]
    ) -> Dict[str, MetricResult]:
        """Calculate completeness-related metrics."""
        metrics = {}
        
        if not validation_results:
            return metrics
        
        # Completeness score based on missing data/fields
        completeness_checks = [r for r in validation_results if "completeness" in r.check_name.lower() or "missing" in r.message.lower()]
        if completeness_checks:
            completeness_score = mean([r.score for r in completeness_checks])
        else:
            # If no specific completeness checks, use format validation as proxy
            format_checks = [r for r in validation_results if "format" in r.check_name.lower()]
            completeness_score = mean([r.score for r in format_checks]) if format_checks else 1.0
        
        metrics["completeness_score"] = MetricResult(
            metric_id="completeness_score",
            value=completeness_score,
            normalized_value=completeness_score,
            sample_size=len(validation_results)
        )
        
        return metrics
    
    def _calculate_safety_metrics(
        self,
        validation_results: List[ValidationResult]
    ) -> Dict[str, MetricResult]:
        """Calculate safety-related metrics."""
        metrics = {}
        
        if not validation_results:
            return metrics
        
        # Safety score based on critical issues
        critical_issues = sum(1 for r in validation_results if r.severity == ValidationSeverity.CRITICAL)
        high_issues = sum(1 for r in validation_results if r.severity == ValidationSeverity.HIGH)
        
        # Safety score decreases with critical/high severity issues
        safety_penalty = (critical_issues * 0.2 + high_issues * 0.1) / len(validation_results)
        safety_score = max(0, 1 - safety_penalty)
        
        metrics["safety_score"] = MetricResult(
            metric_id="safety_score",
            value=safety_score,
            normalized_value=safety_score,
            sample_size=len(validation_results),
            metadata={
                "critical_issues": critical_issues,
                "high_issues": high_issues
            }
        )
        
        # Hallucination rate (if available)
        hallucination_checks = [r for r in validation_results if "hallucination" in r.check_name.lower()]
        if hallucination_checks:
            hallucinations = sum(1 for r in hallucination_checks if not r.passed)
            hallucination_rate = (hallucinations / len(hallucination_checks)) * 100
            
            metric_def = self._metric_definitions["hallucination_rate"]
            metrics["hallucination_rate"] = MetricResult(
                metric_id="hallucination_rate",
                value=hallucination_rate,
                normalized_value=metric_def.normalize_value(hallucination_rate),
                sample_size=len(hallucination_checks)
            )
        
        return metrics
    
    def aggregate_metrics(
        self,
        metric_results_list: List[Dict[str, MetricResult]]
    ) -> Dict[str, MetricResult]:
        """
        Aggregate metrics from multiple validation runs.
        
        Args:
            metric_results_list: List of metric results from different runs
            
        Returns:
            Aggregated metrics
        """
        if not metric_results_list:
            return {}
        
        aggregated = {}
        
        # Group results by metric ID
        metric_groups = {}
        for results in metric_results_list:
            for metric_id, result in results.items():
                if metric_id not in metric_groups:
                    metric_groups[metric_id] = []
                metric_groups[metric_id].append(result)
        
        # Aggregate each metric
        for metric_id, results in metric_groups.items():
            values = [r.value for r in results]
            normalized_values = [r.normalized_value for r in results]
            
            metric_def = self._metric_definitions.get(metric_id)
            if metric_def:
                # Use specified aggregation method
                if metric_def.aggregation_method == "mean":
                    agg_value = mean(values)
                    agg_normalized = mean(normalized_values)
                elif metric_def.aggregation_method == "median":
                    agg_value = median(values)
                    agg_normalized = median(normalized_values)
                elif metric_def.aggregation_method == "min":
                    agg_value = min(values)
                    agg_normalized = min(normalized_values)
                elif metric_def.aggregation_method == "max":
                    agg_value = max(values)
                    agg_normalized = max(normalized_values)
                elif metric_def.aggregation_method == "sum":
                    agg_value = sum(values)
                    agg_normalized = min(1.0, sum(normalized_values))
                else:
                    agg_value = mean(values)
                    agg_normalized = mean(normalized_values)
            else:
                agg_value = mean(values)
                agg_normalized = mean(normalized_values)
            
            total_samples = sum(r.sample_size or 1 for r in results)
            
            aggregated[metric_id] = MetricResult(
                metric_id=metric_id,
                value=agg_value,
                normalized_value=agg_normalized,
                confidence=mean([r.confidence for r in results]),
                sample_size=total_samples,
                metadata={
                    "num_runs": len(results),
                    "std_dev": stdev(values) if len(values) > 1 else 0,
                    "min_value": min(values),
                    "max_value": max(values)
                }
            )
        
        return aggregated
    
    def get_metric_definition(self, metric_id: str) -> Optional[MetricDefinition]:
        """Get metric definition by ID."""
        return self._metric_definitions.get(metric_id)
    
    def list_metrics(self, metric_type: Optional[MetricType] = None) -> List[MetricDefinition]:
        """
        List available metrics.
        
        Args:
            metric_type: Optional filter by metric type
            
        Returns:
            List of metric definitions
        """
        metrics = list(self._metric_definitions.values())
        if metric_type:
            metrics = [m for m in metrics if m.type == metric_type]
        return metrics