"""
Data Quality Validator

This module validates the quality of synthetic data to ensure it meets
requirements for testing AI agents effectively.
"""

from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from dataclasses import dataclass, field
import json

from ...core.exceptions import DataQualityError
from ...utils.logging import get_logger, log_performance

logger = get_logger(__name__)


@dataclass
class QualityMetrics:
    """Quality metrics for synthetic data."""
    completeness: float = 0.0  # Percentage of non-null values
    validity: float = 0.0      # Percentage of valid values
    accuracy: float = 0.0      # Statistical similarity to real data
    consistency: float = 0.0   # Internal consistency
    uniqueness: float = 0.0    # Percentage of unique values
    timeliness: float = 0.0    # Data freshness (for time series)
    
    @property
    def overall_quality(self) -> float:
        """Calculate overall quality score."""
        metrics = [
            self.completeness,
            self.validity,
            self.accuracy,
            self.consistency,
            self.uniqueness
        ]
        # Exclude timeliness if not applicable (0.0)
        if self.timeliness > 0:
            metrics.append(self.timeliness)
        
        return sum(metrics) / len(metrics)
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "completeness": self.completeness,
            "validity": self.validity,
            "accuracy": self.accuracy,
            "consistency": self.consistency,
            "uniqueness": self.uniqueness,
            "timeliness": self.timeliness,
            "overall_quality": self.overall_quality
        }


@dataclass
class ValidationRule:
    """Validation rule for data quality."""
    name: str
    check_function: Any
    severity: str = "warning"  # warning, error, critical
    threshold: Optional[float] = None
    description: str = ""
    
    def apply(self, data: Any) -> Tuple[bool, str]:
        """Apply the validation rule."""
        try:
            result = self.check_function(data)
            if self.threshold is not None:
                passed = result >= self.threshold
                message = f"{self.name}: {result:.2f} (threshold: {self.threshold})"
            else:
                passed = bool(result)
                message = f"{self.name}: {'passed' if passed else 'failed'}"
            return passed, message
        except Exception as e:
            return False, f"{self.name}: Error - {str(e)}"


class DataQualityValidator:
    """
    Validates synthetic data quality across multiple dimensions.
    
    This validator checks:
    - Data completeness
    - Value validity
    - Statistical accuracy
    - Internal consistency
    - Uniqueness constraints
    - Privacy preservation
    """
    
    def __init__(self):
        """Initialize the data quality validator."""
        self.custom_rules: Dict[str, ValidationRule] = {}
        self._initialize_default_rules()
    
    def _initialize_default_rules(self):
        """Initialize default validation rules."""
        # Add default rules that can be applied to any data type
        self.add_rule(ValidationRule(
            name="non_empty",
            check_function=lambda data: len(data) > 0 if hasattr(data, '__len__') else True,
            severity="critical",
            description="Data must not be empty"
        ))
    
    @log_performance
    def validate(
        self,
        synthetic_data: Any,
        reference_data: Optional[Any] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate synthetic data quality.
        
        Args:
            synthetic_data: The synthetic data to validate
            reference_data: Optional reference/real data for comparison
            schema: Optional schema definition
            **kwargs: Additional validation parameters
            
        Returns:
            Validation results including metrics and issues
        """
        results = {
            "valid": True,
            "metrics": None,
            "issues": [],
            "warnings": [],
            "statistics": {}
        }
        
        # Determine data type and validate accordingly
        if isinstance(synthetic_data, pd.DataFrame):
            results = self._validate_dataframe(
                synthetic_data,
                reference_data,
                schema,
                **kwargs
            )
        elif isinstance(synthetic_data, (list, tuple)):
            results = self._validate_list(
                synthetic_data,
                reference_data,
                schema,
                **kwargs
            )
        elif isinstance(synthetic_data, dict):
            results = self._validate_dict(
                synthetic_data,
                reference_data,
                schema,
                **kwargs
            )
        elif isinstance(synthetic_data, str):
            results = self._validate_text(
                synthetic_data,
                reference_data,
                schema,
                **kwargs
            )
        else:
            # Generic validation
            results = self._validate_generic(
                synthetic_data,
                reference_data,
                schema,
                **kwargs
            )
        
        # Apply custom rules
        for rule_name, rule in self.custom_rules.items():
            passed, message = rule.apply(synthetic_data)
            if not passed:
                if rule.severity == "critical":
                    results["valid"] = False
                    results["issues"].append(message)
                elif rule.severity == "error":
                    results["issues"].append(message)
                else:
                    results["warnings"].append(message)
        
        return results
    
    def _validate_dataframe(
        self,
        df: pd.DataFrame,
        reference_df: Optional[pd.DataFrame] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Validate pandas DataFrame."""
        metrics = QualityMetrics()
        issues = []
        warnings = []
        statistics = {}
        
        # Completeness check
        total_cells = df.size
        non_null_cells = df.count().sum()
        metrics.completeness = non_null_cells / total_cells if total_cells > 0 else 0
        
        if metrics.completeness < kwargs.get("min_completeness", 0.95):
            warnings.append(f"Low completeness: {metrics.completeness:.2%}")
        
        # Column-level validation
        for column in df.columns:
            col_stats = self._validate_column(df[column], column, schema)
            statistics[column] = col_stats
            
            # Check validity
            if "invalid_count" in col_stats:
                valid_ratio = 1 - (col_stats["invalid_count"] / len(df))
                if valid_ratio < kwargs.get("min_validity", 0.99):
                    issues.append(f"Column '{column}' has low validity: {valid_ratio:.2%}")
        
        # Uniqueness check
        for column in df.columns:
            if schema and column in schema:
                if schema[column].get("unique", False):
                    unique_ratio = df[column].nunique() / len(df)
                    if unique_ratio < kwargs.get("min_uniqueness", 0.99):
                        issues.append(f"Column '{column}' has duplicate values")
        
        # Statistical similarity (if reference provided)
        if reference_df is not None:
            accuracy_scores = []
            for column in df.columns:
                if column in reference_df.columns:
                    score = self._compare_distributions(
                        df[column],
                        reference_df[column]
                    )
                    accuracy_scores.append(score)
                    statistics[column]["distribution_similarity"] = score
            
            if accuracy_scores:
                metrics.accuracy = np.mean(accuracy_scores)
                if metrics.accuracy < kwargs.get("min_accuracy", 0.8):
                    warnings.append(f"Low statistical similarity: {metrics.accuracy:.2%}")
        
        # Consistency checks
        consistency_scores = []
        
        # Check data type consistency
        for column in df.columns:
            try:
                # Check if column has mixed types
                types = df[column].dropna().apply(type).unique()
                if len(types) > 1:
                    warnings.append(f"Column '{column}' has mixed data types")
                    consistency_scores.append(0.5)
                else:
                    consistency_scores.append(1.0)
            except:
                consistency_scores.append(1.0)
        
        if consistency_scores:
            metrics.consistency = np.mean(consistency_scores)
        
        # Overall uniqueness
        total_unique = sum(df[col].nunique() for col in df.columns)
        total_values = sum(len(df[col]) for col in df.columns)
        metrics.uniqueness = total_unique / total_values if total_values > 0 else 0
        
        # Time series specific checks
        if df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
            # Check for gaps in time series
            if hasattr(df.index, 'freq') and df.index.freq:
                expected_periods = pd.date_range(
                    start=df.index.min(),
                    end=df.index.max(),
                    freq=df.index.freq
                )
                missing_periods = len(expected_periods) - len(df)
                if missing_periods > 0:
                    warnings.append(f"Time series has {missing_periods} missing periods")
            
            metrics.timeliness = 1.0  # Assume fresh for synthetic data
        
        # Calculate overall validity
        metrics.validity = 1.0 - (len(issues) / (len(df.columns) * len(df))) if len(df) > 0 else 1.0
        
        return {
            "valid": len(issues) == 0,
            "metrics": metrics.to_dict(),
            "issues": issues,
            "warnings": warnings,
            "statistics": statistics
        }
    
    def _validate_column(
        self,
        series: pd.Series,
        column_name: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate a single column."""
        stats = {
            "count": len(series),
            "non_null_count": series.count(),
            "unique_count": series.nunique(),
            "dtype": str(series.dtype)
        }
        
        # Numeric columns
        if pd.api.types.is_numeric_dtype(series):
            stats.update({
                "mean": series.mean(),
                "std": series.std(),
                "min": series.min(),
                "max": series.max(),
                "q25": series.quantile(0.25),
                "q50": series.quantile(0.50),
                "q75": series.quantile(0.75)
            })
            
            # Check for outliers (using IQR method)
            q1, q3 = stats["q25"], stats["q75"]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outliers = series[(series < lower_bound) | (series > upper_bound)]
            stats["outlier_count"] = len(outliers)
            stats["outlier_percentage"] = len(outliers) / len(series) * 100
            
            # Check range if schema provided
            if schema and column_name in schema:
                col_schema = schema[column_name]
                invalid_count = 0
                
                if "min" in col_schema:
                    invalid_count += (series < col_schema["min"]).sum()
                if "max" in col_schema:
                    invalid_count += (series > col_schema["max"]).sum()
                
                stats["invalid_count"] = invalid_count
        
        # Categorical columns
        elif pd.api.types.is_categorical_dtype(series) or series.dtype == 'object':
            value_counts = series.value_counts()
            stats.update({
                "unique_values": value_counts.to_dict(),
                "mode": value_counts.index[0] if len(value_counts) > 0 else None,
                "mode_frequency": value_counts.iloc[0] if len(value_counts) > 0 else 0
            })
            
            # Check allowed values if schema provided
            if schema and column_name in schema:
                col_schema = schema[column_name]
                if "values" in col_schema:
                    allowed_values = set(col_schema["values"])
                    actual_values = set(series.dropna().unique())
                    invalid_values = actual_values - allowed_values
                    
                    if invalid_values:
                        stats["invalid_values"] = list(invalid_values)
                        stats["invalid_count"] = series.isin(invalid_values).sum()
        
        # DateTime columns
        elif pd.api.types.is_datetime64_any_dtype(series):
            stats.update({
                "min_date": series.min(),
                "max_date": series.max(),
                "date_range_days": (series.max() - series.min()).days
            })
        
        return stats
    
    def _validate_list(
        self,
        data: List[Any],
        reference: Optional[List[Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Validate list data."""
        metrics = QualityMetrics()
        issues = []
        warnings = []
        
        # Basic checks
        if len(data) == 0:
            issues.append("Empty list")
            metrics.completeness = 0.0
        else:
            metrics.completeness = 1.0
        
        # Type consistency
        types = set(type(item) for item in data)
        if len(types) > 1:
            warnings.append(f"Mixed types in list: {types}")
            metrics.consistency = 0.5
        else:
            metrics.consistency = 1.0
        
        # Uniqueness
        unique_count = len(set(str(item) for item in data))
        metrics.uniqueness = unique_count / len(data) if len(data) > 0 else 0
        
        # Validity (basic)
        metrics.validity = 1.0
        
        # Statistical comparison if reference provided
        if reference:
            # Simple length comparison
            length_diff = abs(len(data) - len(reference)) / max(len(data), len(reference))
            metrics.accuracy = 1.0 - length_diff
        
        return {
            "valid": len(issues) == 0,
            "metrics": metrics.to_dict(),
            "issues": issues,
            "warnings": warnings,
            "statistics": {
                "length": len(data),
                "types": [str(t) for t in types],
                "unique_count": unique_count
            }
        }
    
    def _validate_dict(
        self,
        data: Dict[str, Any],
        reference: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Validate dictionary data."""
        metrics = QualityMetrics()
        issues = []
        warnings = []
        
        # Schema validation
        if schema:
            required_keys = schema.get("required", [])
            for key in required_keys:
                if key not in data:
                    issues.append(f"Missing required key: {key}")
            
            # Check types
            properties = schema.get("properties", {})
            for key, value in data.items():
                if key in properties:
                    expected_type = properties[key].get("type")
                    if expected_type:
                        actual_type = type(value).__name__
                        if not self._check_type(value, expected_type):
                            issues.append(
                                f"Key '{key}' has wrong type: expected {expected_type}, "
                                f"got {actual_type}"
                            )
        
        # Completeness
        if schema:
            total_fields = len(schema.get("properties", {}))
            present_fields = sum(1 for k in schema.get("properties", {}) if k in data)
            metrics.completeness = present_fields / total_fields if total_fields > 0 else 1.0
        else:
            metrics.completeness = 1.0 if data else 0.0
        
        # Validity
        metrics.validity = 1.0 - (len(issues) / max(len(data), 1))
        
        # Consistency
        metrics.consistency = 1.0
        
        # Uniqueness (for dict values)
        if data:
            values = [str(v) for v in data.values()]
            unique_values = len(set(values))
            metrics.uniqueness = unique_values / len(values)
        
        return {
            "valid": len(issues) == 0,
            "metrics": metrics.to_dict(),
            "issues": issues,
            "warnings": warnings,
            "statistics": {
                "key_count": len(data),
                "keys": list(data.keys())
            }
        }
    
    def _validate_text(
        self,
        text: str,
        reference: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Validate text data."""
        metrics = QualityMetrics()
        issues = []
        warnings = []
        statistics = {}
        
        # Basic statistics
        statistics["length"] = len(text)
        statistics["word_count"] = len(text.split())
        statistics["line_count"] = len(text.splitlines())
        
        # Completeness (non-empty)
        metrics.completeness = 1.0 if text.strip() else 0.0
        
        # Schema validation
        if schema:
            min_length = schema.get("min_length", 0)
            max_length = schema.get("max_length", float('inf'))
            
            if statistics["length"] < min_length:
                issues.append(f"Text too short: {statistics['length']} < {min_length}")
            if statistics["length"] > max_length:
                issues.append(f"Text too long: {statistics['length']} > {max_length}")
            
            # Pattern validation
            if "pattern" in schema:
                import re
                if not re.match(schema["pattern"], text):
                    issues.append(f"Text doesn't match required pattern")
        
        # Validity
        metrics.validity = 1.0 if not issues else 0.5
        
        # Consistency (check for encoding issues)
        try:
            text.encode('utf-8').decode('utf-8')
            metrics.consistency = 1.0
        except:
            metrics.consistency = 0.0
            issues.append("Text has encoding issues")
        
        # Uniqueness (character diversity)
        unique_chars = len(set(text))
        metrics.uniqueness = unique_chars / len(text) if text else 0
        
        return {
            "valid": len(issues) == 0,
            "metrics": metrics.to_dict(),
            "issues": issues,
            "warnings": warnings,
            "statistics": statistics
        }
    
    def _validate_generic(
        self,
        data: Any,
        reference: Optional[Any] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generic validation for other data types."""
        metrics = QualityMetrics()
        
        # Basic validation
        metrics.completeness = 1.0 if data is not None else 0.0
        metrics.validity = 1.0
        metrics.consistency = 1.0
        metrics.uniqueness = 1.0
        
        return {
            "valid": True,
            "metrics": metrics.to_dict(),
            "issues": [],
            "warnings": [],
            "statistics": {
                "type": type(data).__name__,
                "str_representation": str(data)[:100]
            }
        }
    
    def _compare_distributions(
        self,
        synthetic: pd.Series,
        reference: pd.Series
    ) -> float:
        """Compare statistical distributions of two series."""
        # Remove null values
        synthetic_clean = synthetic.dropna()
        reference_clean = reference.dropna()
        
        if len(synthetic_clean) == 0 or len(reference_clean) == 0:
            return 0.0
        
        try:
            if pd.api.types.is_numeric_dtype(synthetic):
                # Kolmogorov-Smirnov test for numeric data
                ks_statistic, p_value = stats.ks_2samp(
                    synthetic_clean,
                    reference_clean
                )
                # Convert to similarity score (higher p-value = more similar)
                return p_value
            else:
                # Chi-square test for categorical data
                # Get value counts
                synthetic_counts = synthetic_clean.value_counts()
                reference_counts = reference_clean.value_counts()
                
                # Align categories
                all_categories = set(synthetic_counts.index) | set(reference_counts.index)
                
                synthetic_freq = []
                reference_freq = []
                
                for cat in all_categories:
                    synthetic_freq.append(synthetic_counts.get(cat, 0))
                    reference_freq.append(reference_counts.get(cat, 0))
                
                # Normalize to probabilities
                synthetic_freq = np.array(synthetic_freq) / sum(synthetic_freq)
                reference_freq = np.array(reference_freq) / sum(reference_freq)
                
                # Calculate chi-square statistic
                chi2 = np.sum((synthetic_freq - reference_freq) ** 2 / reference_freq)
                
                # Convert to similarity score
                return np.exp(-chi2)
                
        except Exception as e:
            logger.warning(f"Failed to compare distributions: {str(e)}")
            return 0.5
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": (list, tuple),
            "object": dict
        }
        
        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])
        
        return True
    
    def add_rule(self, rule: ValidationRule) -> None:
        """Add a custom validation rule."""
        self.custom_rules[rule.name] = rule
    
    def remove_rule(self, rule_name: str) -> None:
        """Remove a custom validation rule."""
        if rule_name in self.custom_rules:
            del self.custom_rules[rule_name]
    
    def validate_privacy(
        self,
        synthetic_data: pd.DataFrame,
        reference_data: pd.DataFrame,
        quasi_identifiers: List[str],
        sensitive_attributes: List[str],
        k_anonymity_threshold: int = 5
    ) -> Dict[str, Any]:
        """
        Validate privacy preservation in synthetic data.
        
        Args:
            synthetic_data: Synthetic dataset
            reference_data: Original dataset
            quasi_identifiers: Columns that could identify individuals
            sensitive_attributes: Sensitive columns to protect
            k_anonymity_threshold: Minimum group size for anonymity
            
        Returns:
            Privacy validation results
        """
        results = {
            "k_anonymity": 0,
            "l_diversity": {},
            "attribute_disclosure_risk": {},
            "privacy_score": 0.0,
            "issues": []
        }
        
        # K-anonymity check
        if quasi_identifiers:
            group_sizes = synthetic_data.groupby(quasi_identifiers).size()
            min_group_size = group_sizes.min()
            results["k_anonymity"] = min_group_size
            
            if min_group_size < k_anonymity_threshold:
                results["issues"].append(
                    f"K-anonymity violation: minimum group size is {min_group_size}"
                )
        
        # L-diversity check for sensitive attributes
        for sensitive_attr in sensitive_attributes:
            if sensitive_attr in synthetic_data.columns and quasi_identifiers:
                diversity_scores = []
                for _, group in synthetic_data.groupby(quasi_identifiers):
                    unique_values = group[sensitive_attr].nunique()
                    group_size = len(group)
                    diversity = unique_values / group_size if group_size > 0 else 0
                    diversity_scores.append(diversity)
                
                avg_diversity = np.mean(diversity_scores) if diversity_scores else 0
                results["l_diversity"][sensitive_attr] = avg_diversity
                
                if avg_diversity < 0.5:
                    results["issues"].append(
                        f"Low l-diversity for {sensitive_attr}: {avg_diversity:.2f}"
                    )
        
        # Attribute disclosure risk
        for attr in sensitive_attributes:
            if attr in synthetic_data.columns and attr in reference_data.columns:
                # Check if any exact matches exist
                synthetic_values = set(synthetic_data[attr].unique())
                reference_values = set(reference_data[attr].unique())
                overlap = synthetic_values & reference_values
                
                disclosure_risk = len(overlap) / len(reference_values) if reference_values else 0
                results["attribute_disclosure_risk"][attr] = disclosure_risk
                
                if disclosure_risk > 0.8:
                    results["issues"].append(
                        f"High attribute disclosure risk for {attr}: {disclosure_risk:.2f}"
                    )
        
        # Calculate overall privacy score
        scores = []
        
        # K-anonymity score
        k_score = min(1.0, results["k_anonymity"] / k_anonymity_threshold)
        scores.append(k_score)
        
        # L-diversity scores
        if results["l_diversity"]:
            l_scores = list(results["l_diversity"].values())
            scores.extend(l_scores)
        
        # Disclosure risk scores (inverted)
        if results["attribute_disclosure_risk"]:
            disclosure_scores = [1 - risk for risk in results["attribute_disclosure_risk"].values()]
            scores.extend(disclosure_scores)
        
        results["privacy_score"] = np.mean(scores) if scores else 0.0
        
        return results