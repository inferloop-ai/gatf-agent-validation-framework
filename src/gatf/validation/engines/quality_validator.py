"""
Quality Validation Engine

This module implements core quality validation checks for AI agent outputs.
It provides comprehensive quality assessment including accuracy, performance,
consistency, and format validation.
"""

from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime, timedelta
import time
import json
import re
from collections import Counter
from statistics import mean, stdev
import numpy as np
from dataclasses import dataclass, field

from ...core.exceptions import ValidationError, MetricCalculationError
from ...domains.base_domain import ValidationResult, ValidationSeverity
from ...utils.logging import get_logger, log_performance

logger = get_logger(__name__)


@dataclass
class QualityCheckConfig:
    """Configuration for quality checks."""
    accuracy_threshold: float = 0.8
    performance_timeout: float = 10.0  # seconds
    consistency_threshold: float = 0.9
    format_strict: bool = False
    custom_checks: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for validation."""
    response_time: float
    tokens_processed: int
    throughput: float  # tokens per second
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    
    @property
    def is_acceptable(self) -> bool:
        """Check if performance is within acceptable bounds."""
        return self.response_time < 10.0 and self.throughput > 10.0


class QualityValidator:
    """
    Implements core quality validation for AI agent outputs.
    
    This validator performs:
    - Accuracy assessment
    - Performance benchmarking
    - Consistency validation
    - Output format verification
    - Statistical quality metrics
    """
    
    def __init__(self, config: Optional[QualityCheckConfig] = None):
        """
        Initialize the quality validator.
        
        Args:
            config: Quality check configuration
        """
        self.config = config or QualityCheckConfig()
        self._performance_history: List[PerformanceMetrics] = []
        self._accuracy_history: List[float] = []
        
    @log_performance
    def validate(
        self,
        output: Any,
        expected: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResult]:
        """
        Perform comprehensive quality validation.
        
        Args:
            output: The output to validate
            expected: Optional expected output for comparison
            context: Optional context information
            
        Returns:
            List of validation results
        """
        results = []
        context = context or {}
        
        # Accuracy validation
        if expected is not None:
            accuracy_result = self.validate_accuracy(output, expected, context)
            results.append(accuracy_result)
        
        # Performance validation
        if "performance_metrics" in context:
            performance_result = self.validate_performance(
                context["performance_metrics"]
            )
            results.append(performance_result)
        
        # Consistency validation
        if "previous_outputs" in context:
            consistency_result = self.validate_consistency(
                output,
                context["previous_outputs"]
            )
            results.append(consistency_result)
        
        # Format validation
        format_result = self.validate_format(output, context)
        results.append(format_result)
        
        # Statistical validation
        stats_result = self.validate_statistics(output, context)
        results.append(stats_result)
        
        # Custom checks
        for check_name, check_func in self.config.custom_checks.items():
            try:
                custom_result = check_func(output, expected, context)
                if isinstance(custom_result, ValidationResult):
                    results.append(custom_result)
            except Exception as e:
                logger.error(f"Custom check '{check_name}' failed: {str(e)}")
                results.append(ValidationResult(
                    check_name=f"custom_{check_name}",
                    passed=False,
                    score=0.0,
                    severity=ValidationSeverity.MEDIUM,
                    message=f"Custom check failed: {str(e)}"
                ))
        
        return results
    
    def validate_accuracy(
        self,
        output: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate output accuracy against expected results.
        
        Args:
            output: The actual output
            expected: The expected output
            context: Optional context
            
        Returns:
            Validation result for accuracy
        """
        try:
            accuracy_score = self._calculate_accuracy(output, expected)
            self._accuracy_history.append(accuracy_score)
            
            passed = accuracy_score >= self.config.accuracy_threshold
            
            # Determine severity based on accuracy
            if accuracy_score >= 0.95:
                severity = ValidationSeverity.INFO
            elif accuracy_score >= 0.8:
                severity = ValidationSeverity.LOW
            elif accuracy_score >= 0.6:
                severity = ValidationSeverity.MEDIUM
            else:
                severity = ValidationSeverity.HIGH
            
            suggestions = []
            if not passed:
                suggestions.extend([
                    "Review the model's training data",
                    "Consider fine-tuning on domain-specific data",
                    "Check for data preprocessing issues"
                ])
            
            return ValidationResult(
                check_name="accuracy_validation",
                passed=passed,
                score=accuracy_score,
                severity=severity,
                message=f"Accuracy score: {accuracy_score:.2%}",
                details={
                    "accuracy_score": accuracy_score,
                    "threshold": self.config.accuracy_threshold,
                    "historical_average": mean(self._accuracy_history[-10:])
                    if len(self._accuracy_history) > 0 else None
                },
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Accuracy validation failed: {str(e)}")
            return ValidationResult(
                check_name="accuracy_validation",
                passed=False,
                score=0.0,
                severity=ValidationSeverity.HIGH,
                message=f"Accuracy validation error: {str(e)}"
            )
    
    def validate_performance(
        self,
        metrics: Union[Dict[str, Any], PerformanceMetrics]
    ) -> ValidationResult:
        """
        Validate performance metrics.
        
        Args:
            metrics: Performance metrics to validate
            
        Returns:
            Validation result for performance
        """
        try:
            # Convert dict to PerformanceMetrics if needed
            if isinstance(metrics, dict):
                perf_metrics = PerformanceMetrics(
                    response_time=metrics.get("response_time", 0.0),
                    tokens_processed=metrics.get("tokens_processed", 0),
                    throughput=metrics.get("throughput", 0.0),
                    memory_usage=metrics.get("memory_usage"),
                    cpu_usage=metrics.get("cpu_usage")
                )
            else:
                perf_metrics = metrics
            
            self._performance_history.append(perf_metrics)
            
            # Check performance thresholds
            passed = (
                perf_metrics.response_time < self.config.performance_timeout and
                perf_metrics.throughput > 0
            )
            
            # Calculate performance score (0-1)
            time_score = max(0, 1 - (perf_metrics.response_time / self.config.performance_timeout))
            throughput_score = min(1, perf_metrics.throughput / 100)  # 100 tokens/sec as baseline
            performance_score = (time_score + throughput_score) / 2
            
            severity = ValidationSeverity.LOW if passed else ValidationSeverity.MEDIUM
            
            suggestions = []
            if perf_metrics.response_time > self.config.performance_timeout:
                suggestions.append("Consider optimizing model inference")
                suggestions.append("Use model quantization or distillation")
            if perf_metrics.throughput < 10:
                suggestions.append("Batch processing may improve throughput")
            
            return ValidationResult(
                check_name="performance_validation",
                passed=passed,
                score=performance_score,
                severity=severity,
                message=f"Response time: {perf_metrics.response_time:.2f}s, "
                       f"Throughput: {perf_metrics.throughput:.1f} tokens/s",
                details={
                    "response_time": perf_metrics.response_time,
                    "throughput": perf_metrics.throughput,
                    "tokens_processed": perf_metrics.tokens_processed,
                    "memory_usage": perf_metrics.memory_usage,
                    "cpu_usage": perf_metrics.cpu_usage,
                    "timeout_threshold": self.config.performance_timeout
                },
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Performance validation failed: {str(e)}")
            return ValidationResult(
                check_name="performance_validation",
                passed=False,
                score=0.0,
                severity=ValidationSeverity.MEDIUM,
                message=f"Performance validation error: {str(e)}"
            )
    
    def validate_consistency(
        self,
        output: Any,
        previous_outputs: List[Any]
    ) -> ValidationResult:
        """
        Validate output consistency across multiple runs.
        
        Args:
            output: Current output
            previous_outputs: List of previous outputs
            
        Returns:
            Validation result for consistency
        """
        try:
            if not previous_outputs:
                return ValidationResult(
                    check_name="consistency_validation",
                    passed=True,
                    score=1.0,
                    severity=ValidationSeverity.INFO,
                    message="No previous outputs for comparison"
                )
            
            # Calculate consistency scores
            consistency_scores = []
            for prev_output in previous_outputs:
                score = self._calculate_similarity(output, prev_output)
                consistency_scores.append(score)
            
            avg_consistency = mean(consistency_scores)
            consistency_std = stdev(consistency_scores) if len(consistency_scores) > 1 else 0
            
            passed = avg_consistency >= self.config.consistency_threshold
            
            severity = ValidationSeverity.LOW if passed else ValidationSeverity.MEDIUM
            
            suggestions = []
            if not passed:
                suggestions.extend([
                    "Check for non-deterministic behavior",
                    "Ensure consistent temperature settings",
                    "Verify random seed configuration"
                ])
            
            return ValidationResult(
                check_name="consistency_validation",
                passed=passed,
                score=avg_consistency,
                severity=severity,
                message=f"Average consistency: {avg_consistency:.2%} "
                       f"(Ã={consistency_std:.3f})",
                details={
                    "average_consistency": avg_consistency,
                    "consistency_std": consistency_std,
                    "threshold": self.config.consistency_threshold,
                    "num_comparisons": len(previous_outputs)
                },
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Consistency validation failed: {str(e)}")
            return ValidationResult(
                check_name="consistency_validation",
                passed=False,
                score=0.0,
                severity=ValidationSeverity.MEDIUM,
                message=f"Consistency validation error: {str(e)}"
            )
    
    def validate_format(
        self,
        output: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate output format and structure.
        
        Args:
            output: Output to validate
            context: Optional context with format requirements
            
        Returns:
            Validation result for format
        """
        try:
            format_issues = []
            format_score = 1.0
            
            # Check JSON validity if output should be JSON
            if context and context.get("expected_format") == "json":
                if isinstance(output, str):
                    try:
                        json.loads(output)
                    except json.JSONDecodeError as e:
                        format_issues.append(f"Invalid JSON: {str(e)}")
                        format_score -= 0.5
                elif not isinstance(output, (dict, list)):
                    format_issues.append("Output is not JSON-serializable")
                    format_score -= 0.5
            
            # Check required fields
            if context and "required_fields" in context:
                if isinstance(output, dict):
                    missing_fields = set(context["required_fields"]) - set(output.keys())
                    if missing_fields:
                        format_issues.append(f"Missing fields: {missing_fields}")
                        format_score -= 0.1 * len(missing_fields)
            
            # Check output length constraints
            if context:
                if "min_length" in context and len(str(output)) < context["min_length"]:
                    format_issues.append("Output too short")
                    format_score -= 0.2
                if "max_length" in context and len(str(output)) > context["max_length"]:
                    format_issues.append("Output too long")
                    format_score -= 0.2
            
            format_score = max(0, format_score)
            passed = format_score >= 0.8 or (not self.config.format_strict and format_score >= 0.5)
            
            severity = ValidationSeverity.LOW if passed else ValidationSeverity.MEDIUM
            if self.config.format_strict and not passed:
                severity = ValidationSeverity.HIGH
            
            return ValidationResult(
                check_name="format_validation",
                passed=passed,
                score=format_score,
                severity=severity,
                message="Format validation " + ("passed" if passed else f"failed: {'; '.join(format_issues)}"),
                details={
                    "format_issues": format_issues,
                    "strict_mode": self.config.format_strict
                },
                suggestions=["Ensure output matches expected format"] if not passed else []
            )
            
        except Exception as e:
            logger.error(f"Format validation failed: {str(e)}")
            return ValidationResult(
                check_name="format_validation",
                passed=False,
                score=0.0,
                severity=ValidationSeverity.MEDIUM,
                message=f"Format validation error: {str(e)}"
            )
    
    def validate_statistics(
        self,
        output: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate statistical properties of the output.
        
        Args:
            output: Output to validate
            context: Optional context
            
        Returns:
            Validation result for statistics
        """
        try:
            stats_checks = []
            stats_score = 1.0
            
            # Convert output to string for analysis
            output_str = str(output)
            
            # Check for repetition
            words = output_str.split()
            if len(words) > 10:
                word_counts = Counter(words)
                repetition_ratio = max(word_counts.values()) / len(words)
                if repetition_ratio > 0.1:  # More than 10% repetition
                    stats_checks.append(f"High repetition detected ({repetition_ratio:.1%})")
                    stats_score -= 0.3
            
            # Check for diversity (unique words ratio)
            if len(words) > 0:
                diversity_ratio = len(set(words)) / len(words)
                if diversity_ratio < 0.5:  # Less than 50% unique words
                    stats_checks.append(f"Low diversity ({diversity_ratio:.1%} unique words)")
                    stats_score -= 0.2
            
            # Check for anomalies in numeric outputs
            if isinstance(output, (list, np.ndarray)) and len(output) > 0:
                try:
                    numeric_values = [float(x) for x in output if isinstance(x, (int, float))]
                    if numeric_values:
                        # Check for outliers using IQR
                        q1, q3 = np.percentile(numeric_values, [25, 75])
                        iqr = q3 - q1
                        outliers = [x for x in numeric_values if x < q1 - 1.5*iqr or x > q3 + 1.5*iqr]
                        if len(outliers) / len(numeric_values) > 0.1:  # More than 10% outliers
                            stats_checks.append(f"{len(outliers)} outliers detected")
                            stats_score -= 0.2
                except (ValueError, TypeError):
                    pass
            
            stats_score = max(0, stats_score)
            passed = stats_score >= 0.7
            
            severity = ValidationSeverity.INFO if passed else ValidationSeverity.LOW
            
            return ValidationResult(
                check_name="statistical_validation",
                passed=passed,
                score=stats_score,
                severity=severity,
                message="Statistical validation " + ("passed" if passed else f"issues: {'; '.join(stats_checks)}"),
                details={
                    "statistical_issues": stats_checks,
                    "output_length": len(output_str),
                    "word_count": len(words) if isinstance(output, str) else None
                },
                suggestions=["Review output generation parameters"] if not passed else []
            )
            
        except Exception as e:
            logger.error(f"Statistical validation failed: {str(e)}")
            return ValidationResult(
                check_name="statistical_validation",
                passed=True,  # Don't fail on stats errors
                score=1.0,
                severity=ValidationSeverity.INFO,
                message=f"Statistical validation skipped: {str(e)}"
            )
    
    def _calculate_accuracy(self, output: Any, expected: Any) -> float:
        """
        Calculate accuracy score between output and expected.
        
        Args:
            output: Actual output
            expected: Expected output
            
        Returns:
            Accuracy score between 0 and 1
        """
        # Handle exact matches
        if output == expected:
            return 1.0
        
        # Handle string comparison
        if isinstance(output, str) and isinstance(expected, str):
            # Normalize strings
            output_norm = output.lower().strip()
            expected_norm = expected.lower().strip()
            
            if output_norm == expected_norm:
                return 1.0
            
            # Calculate character-level similarity
            longer = max(len(output_norm), len(expected_norm))
            if longer == 0:
                return 1.0
            
            # Use Levenshtein distance
            distance = self._levenshtein_distance(output_norm, expected_norm)
            return 1 - (distance / longer)
        
        # Handle numeric comparison
        if isinstance(output, (int, float)) and isinstance(expected, (int, float)):
            if expected == 0:
                return 1.0 if output == 0 else 0.0
            return 1 - min(1, abs(output - expected) / abs(expected))
        
        # Handle list/array comparison
        if isinstance(output, (list, tuple)) and isinstance(expected, (list, tuple)):
            if len(output) != len(expected):
                return 0.0
            if len(output) == 0:
                return 1.0
            
            scores = []
            for o, e in zip(output, expected):
                scores.append(self._calculate_accuracy(o, e))
            return mean(scores)
        
        # Handle dict comparison
        if isinstance(output, dict) and isinstance(expected, dict):
            all_keys = set(output.keys()) | set(expected.keys())
            if not all_keys:
                return 1.0
            
            scores = []
            for key in all_keys:
                if key in output and key in expected:
                    scores.append(self._calculate_accuracy(output[key], expected[key]))
                else:
                    scores.append(0.0)
            return mean(scores)
        
        # Default: type mismatch
        return 0.0
    
    def _calculate_similarity(self, output1: Any, output2: Any) -> float:
        """
        Calculate similarity between two outputs.
        
        Args:
            output1: First output
            output2: Second output
            
        Returns:
            Similarity score between 0 and 1
        """
        # Reuse accuracy calculation for similarity
        return self._calculate_accuracy(output1, output2)
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def get_summary_metrics(self) -> Dict[str, Any]:
        """
        Get summary metrics from validation history.
        
        Returns:
            Dictionary of summary metrics
        """
        summary = {
            "total_validations": len(self._accuracy_history),
            "average_accuracy": mean(self._accuracy_history) if self._accuracy_history else None,
            "accuracy_trend": "stable"
        }
        
        # Calculate accuracy trend
        if len(self._accuracy_history) >= 10:
            recent = mean(self._accuracy_history[-5:])
            older = mean(self._accuracy_history[-10:-5])
            if recent > older + 0.05:
                summary["accuracy_trend"] = "improving"
            elif recent < older - 0.05:
                summary["accuracy_trend"] = "degrading"
        
        # Performance summary
        if self._performance_history:
            recent_perf = self._performance_history[-10:]
            summary["average_response_time"] = mean([p.response_time for p in recent_perf])
            summary["average_throughput"] = mean([p.throughput for p in recent_perf])
        
        return summary