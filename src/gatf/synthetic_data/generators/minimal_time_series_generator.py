"""
Minimal Time Series Generator

This module provides basic time series data generation capabilities for
testing temporal data processing in AI agents.
"""

from typing import Dict, Any, List, Optional, Union, Tuple, Callable
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from enum import Enum

from ...core.exceptions import DataGenerationError
from ...utils.logging import get_logger, log_performance

logger = get_logger(__name__)


class TimeSeriesPattern(Enum):
    """Common time series patterns."""
    CONSTANT = "constant"
    TREND = "trend"
    SEASONAL = "seasonal"
    RANDOM_WALK = "random_walk"
    CYCLICAL = "cyclical"
    IRREGULAR = "irregular"
    MIXED = "mixed"


class MinimalTimeSeriesGenerator:
    """
    Minimal time series generator for creating synthetic temporal data.
    
    This generator can create time series with various patterns including:
    - Trends (linear, exponential)
    - Seasonality (daily, weekly, monthly, yearly)
    - Random walks
    - Cyclical patterns
    - Irregular/noisy data
    - Mixed patterns
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the time series generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
    
    @log_performance
    def generate(
        self,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        frequency: str = "D",
        columns: Optional[Dict[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Generate time series data.
        
        Args:
            start_date: Start date for the time series
            end_date: End date for the time series
            frequency: Frequency of data points (D, H, T, S, etc.)
            columns: Column specifications
            **kwargs: Additional generation parameters
            
        Returns:
            DataFrame with time series data
            
        Example columns:
            {
                "temperature": {
                    "pattern": "seasonal",
                    "base_value": 20,
                    "amplitude": 10,
                    "period": 365,
                    "noise_level": 0.1
                },
                "sales": {
                    "pattern": "trend",
                    "start_value": 1000,
                    "trend_rate": 0.02,
                    "noise_level": 0.2
                }
            }
        """
        # Parse dates
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        
        # Generate date index
        date_index = pd.date_range(
            start=start_date,
            end=end_date,
            freq=frequency
        )
        
        if len(date_index) == 0:
            raise DataGenerationError("Invalid date range or frequency")
        
        # Initialize DataFrame
        df = pd.DataFrame(index=date_index)
        
        # Generate columns
        if columns is None:
            # Default: single value column with random walk
            columns = {
                "value": {
                    "pattern": TimeSeriesPattern.RANDOM_WALK.value,
                    "start_value": 100,
                    "volatility": 0.02
                }
            }
        
        for column_name, column_spec in columns.items():
            try:
                pattern = column_spec.get("pattern", TimeSeriesPattern.RANDOM_WALK.value)
                
                if isinstance(pattern, str):
                    pattern = TimeSeriesPattern(pattern)
                
                # Generate based on pattern
                if pattern == TimeSeriesPattern.CONSTANT:
                    series = self._generate_constant(len(date_index), column_spec)
                elif pattern == TimeSeriesPattern.TREND:
                    series = self._generate_trend(len(date_index), column_spec)
                elif pattern == TimeSeriesPattern.SEASONAL:
                    series = self._generate_seasonal(date_index, column_spec)
                elif pattern == TimeSeriesPattern.RANDOM_WALK:
                    series = self._generate_random_walk(len(date_index), column_spec)
                elif pattern == TimeSeriesPattern.CYCLICAL:
                    series = self._generate_cyclical(len(date_index), column_spec)
                elif pattern == TimeSeriesPattern.IRREGULAR:
                    series = self._generate_irregular(len(date_index), column_spec)
                elif pattern == TimeSeriesPattern.MIXED:
                    series = self._generate_mixed(date_index, column_spec)
                else:
                    raise DataGenerationError(f"Unknown pattern: {pattern}")
                
                df[column_name] = series
                
            except Exception as e:
                logger.error(f"Failed to generate column '{column_name}': {str(e)}")
                raise DataGenerationError(
                    f"Error generating column '{column_name}': {str(e)}"
                )
        
        # Add anomalies if specified
        if kwargs.get("add_anomalies", False):
            df = self._add_anomalies(
                df,
                kwargs.get("anomaly_rate", 0.01),
                kwargs.get("anomaly_magnitude", 3.0)
            )
        
        # Add missing values if specified
        if kwargs.get("missing_rate", 0) > 0:
            df = self._add_missing_values(df, kwargs["missing_rate"])
        
        return df
    
    def _generate_constant(
        self,
        n: int,
        spec: Dict[str, Any]
    ) -> np.ndarray:
        """Generate constant series with optional noise."""
        value = spec.get("value", 0)
        noise_level = spec.get("noise_level", 0)
        
        series = np.full(n, value)
        
        if noise_level > 0:
            noise = np.random.normal(0, noise_level * abs(value), n)
            series += noise
        
        return series
    
    def _generate_trend(
        self,
        n: int,
        spec: Dict[str, Any]
    ) -> np.ndarray:
        """Generate series with trend."""
        start_value = spec.get("start_value", 0)
        trend_type = spec.get("trend_type", "linear")
        trend_rate = spec.get("trend_rate", 0.01)
        noise_level = spec.get("noise_level", 0)
        
        t = np.arange(n)
        
        if trend_type == "linear":
            series = start_value + trend_rate * t
        elif trend_type == "exponential":
            series = start_value * np.exp(trend_rate * t)
        elif trend_type == "logarithmic":
            series = start_value * np.log1p(trend_rate * t)
        elif trend_type == "polynomial":
            degree = spec.get("polynomial_degree", 2)
            coeffs = spec.get("coefficients", [start_value] + [trend_rate] * degree)
            series = np.polyval(coeffs[::-1], t)
        else:
            series = start_value + trend_rate * t
        
        if noise_level > 0:
            noise = np.random.normal(0, noise_level * np.std(series), n)
            series += noise
        
        return series
    
    def _generate_seasonal(
        self,
        date_index: pd.DatetimeIndex,
        spec: Dict[str, Any]
    ) -> np.ndarray:
        """Generate seasonal series."""
        base_value = spec.get("base_value", 0)
        amplitude = spec.get("amplitude", 1)
        period = spec.get("period", 365)  # days
        phase = spec.get("phase", 0)
        noise_level = spec.get("noise_level", 0)
        
        # Calculate time in days from start
        t = (date_index - date_index[0]).days.values
        
        # Generate seasonal component
        seasonal = amplitude * np.sin(2 * np.pi * (t - phase) / period)
        series = base_value + seasonal
        
        # Add multiple seasonal components if specified
        if "additional_periods" in spec:
            for add_period, add_amplitude in spec["additional_periods"]:
                seasonal_add = add_amplitude * np.sin(2 * np.pi * t / add_period)
                series += seasonal_add
        
        if noise_level > 0:
            noise = np.random.normal(0, noise_level * amplitude, len(series))
            series += noise
        
        return series
    
    def _generate_random_walk(
        self,
        n: int,
        spec: Dict[str, Any]
    ) -> np.ndarray:
        """Generate random walk series."""
        start_value = spec.get("start_value", 0)
        volatility = spec.get("volatility", 0.01)
        drift = spec.get("drift", 0)
        
        # Generate returns
        returns = np.random.normal(drift, volatility, n)
        
        # Cumulative sum to create random walk
        series = start_value * np.exp(np.cumsum(returns))
        
        return series
    
    def _generate_cyclical(
        self,
        n: int,
        spec: Dict[str, Any]
    ) -> np.ndarray:
        """Generate cyclical series."""
        base_value = spec.get("base_value", 0)
        cycles = spec.get("cycles", [])
        noise_level = spec.get("noise_level", 0)
        
        t = np.arange(n)
        series = np.full(n, base_value, dtype=float)
        
        # Add each cycle
        for cycle in cycles:
            period = cycle.get("period", 100)
            amplitude = cycle.get("amplitude", 1)
            phase = cycle.get("phase", 0)
            
            cycle_component = amplitude * np.sin(2 * np.pi * (t - phase) / period)
            series += cycle_component
        
        if noise_level > 0:
            noise = np.random.normal(0, noise_level * np.std(series), n)
            series += noise
        
        return series
    
    def _generate_irregular(
        self,
        n: int,
        spec: Dict[str, Any]
    ) -> np.ndarray:
        """Generate irregular/noisy series."""
        mean = spec.get("mean", 0)
        std = spec.get("std", 1)
        distribution = spec.get("distribution", "normal")
        
        if distribution == "normal":
            series = np.random.normal(mean, std, n)
        elif distribution == "uniform":
            low = mean - std * np.sqrt(3)
            high = mean + std * np.sqrt(3)
            series = np.random.uniform(low, high, n)
        elif distribution == "exponential":
            series = np.random.exponential(mean, n)
        elif distribution == "poisson":
            series = np.random.poisson(max(1, int(mean)), n).astype(float)
        else:
            series = np.random.normal(mean, std, n)
        
        return series
    
    def _generate_mixed(
        self,
        date_index: pd.DatetimeIndex,
        spec: Dict[str, Any]
    ) -> np.ndarray:
        """Generate mixed pattern series."""
        # Start with base value
        base_value = spec.get("base_value", 0)
        series = np.full(len(date_index), base_value, dtype=float)
        
        # Add trend component
        if spec.get("add_trend", True):
            trend_spec = spec.get("trend_spec", {
                "trend_rate": 0.001,
                "trend_type": "linear"
            })
            trend_spec["start_value"] = 0  # Additive
            trend = self._generate_trend(len(date_index), trend_spec)
            series += trend
        
        # Add seasonal component
        if spec.get("add_seasonal", True):
            seasonal_spec = spec.get("seasonal_spec", {
                "amplitude": 10,
                "period": 365,
                "base_value": 0  # Additive
            })
            seasonal = self._generate_seasonal(date_index, seasonal_spec)
            series += seasonal
        
        # Add cyclical component
        if spec.get("add_cyclical", False):
            cyclical_spec = spec.get("cyclical_spec", {
                "cycles": [
                    {"period": 30, "amplitude": 5},
                    {"period": 90, "amplitude": 3}
                ],
                "base_value": 0  # Additive
            })
            cyclical = self._generate_cyclical(len(date_index), cyclical_spec)
            series += cyclical
        
        # Add noise
        noise_level = spec.get("noise_level", 0.05)
        if noise_level > 0:
            noise = np.random.normal(0, noise_level * np.std(series), len(series))
            series += noise
        
        return series
    
    def _add_anomalies(
        self,
        df: pd.DataFrame,
        anomaly_rate: float,
        anomaly_magnitude: float
    ) -> pd.DataFrame:
        """Add anomalies to the time series."""
        df = df.copy()
        
        for column in df.select_dtypes(include=[np.number]).columns:
            # Determine anomaly positions
            n_anomalies = int(len(df) * anomaly_rate)
            anomaly_positions = np.random.choice(
                len(df),
                size=n_anomalies,
                replace=False
            )
            
            # Add anomalies
            col_std = df[column].std()
            for pos in anomaly_positions:
                # Random anomaly type
                anomaly_type = random.choice(["spike", "dip", "shift"])
                
                if anomaly_type == "spike":
                    df.iloc[pos, df.columns.get_loc(column)] += anomaly_magnitude * col_std
                elif anomaly_type == "dip":
                    df.iloc[pos, df.columns.get_loc(column)] -= anomaly_magnitude * col_std
                else:  # shift
                    shift_value = random.uniform(-anomaly_magnitude, anomaly_magnitude) * col_std
                    df.iloc[pos:, df.columns.get_loc(column)] += shift_value
        
        return df
    
    def _add_missing_values(
        self,
        df: pd.DataFrame,
        missing_rate: float
    ) -> pd.DataFrame:
        """Add missing values to the time series."""
        df = df.copy()
        
        for column in df.columns:
            mask = np.random.random(len(df)) < missing_rate
            df.loc[mask, column] = np.nan
        
        return df
    
    def generate_multivariate(
        self,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        frequency: str = "D",
        n_series: int = 3,
        correlation_matrix: Optional[np.ndarray] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Generate multivariate time series with correlations.
        
        Args:
            start_date: Start date
            end_date: End date
            frequency: Data frequency
            n_series: Number of series
            correlation_matrix: Correlation matrix between series
            **kwargs: Additional parameters
            
        Returns:
            DataFrame with correlated time series
        """
        # Generate independent series first
        date_index = pd.date_range(start=start_date, end=end_date, freq=frequency)
        n = len(date_index)
        
        # Generate base series
        independent_series = np.random.randn(n, n_series)
        
        # Apply correlation if specified
        if correlation_matrix is not None:
            if correlation_matrix.shape != (n_series, n_series):
                raise DataGenerationError(
                    f"Correlation matrix shape {correlation_matrix.shape} doesn't match "
                    f"n_series {n_series}"
                )
            
            # Cholesky decomposition for correlation
            L = np.linalg.cholesky(correlation_matrix)
            correlated_series = independent_series @ L.T
        else:
            correlated_series = independent_series
        
        # Create DataFrame
        df = pd.DataFrame(
            correlated_series,
            index=date_index,
            columns=[f"series_{i+1}" for i in range(n_series)]
        )
        
        # Apply patterns to each series
        patterns = kwargs.get("patterns", ["random_walk"] * n_series)
        for i, (col, pattern) in enumerate(zip(df.columns, patterns)):
            if pattern != "random":
                spec = kwargs.get(f"series_{i+1}_spec", {
                    "pattern": pattern,
                    "start_value": 100,
                    "volatility": 0.02
                })
                
                # Preserve correlation structure while applying pattern
                base_values = df[col].values
                pattern_series = self.generate(
                    start_date,
                    end_date,
                    frequency,
                    {col: spec}
                )[col].values
                
                # Blend original correlation with pattern
                blend_factor = kwargs.get("correlation_preservation", 0.5)
                df[col] = blend_factor * base_values + (1 - blend_factor) * pattern_series
        
        return df
    
    def detect_pattern(
        self,
        series: Union[pd.Series, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Simple pattern detection for a time series.
        
        Args:
            series: Time series data
            
        Returns:
            Dictionary with detected patterns
        """
        if isinstance(series, pd.Series):
            values = series.values
        else:
            values = series
        
        n = len(values)
        if n < 10:
            return {"pattern": "insufficient_data"}
        
        # Calculate basic statistics
        mean = np.mean(values)
        std = np.std(values)
        cv = std / mean if mean != 0 else 0
        
        # Check for trend
        x = np.arange(n)
        slope, intercept = np.polyfit(x, values, 1)
        trend_strength = abs(slope) / std if std > 0 else 0
        
        # Check for seasonality (simple autocorrelation)
        max_lag = min(n // 2, 365)
        autocorr = []
        for lag in range(1, max_lag):
            if n > lag:
                corr = np.corrcoef(values[:-lag], values[lag:])[0, 1]
                autocorr.append((lag, corr))
        
        # Find peak autocorrelation
        if autocorr:
            peak_lag, peak_corr = max(autocorr, key=lambda x: abs(x[1]))
        else:
            peak_lag, peak_corr = 0, 0
        
        # Detect pattern
        detected_pattern = {
            "mean": mean,
            "std": std,
            "cv": cv,
            "trend_slope": slope,
            "trend_strength": trend_strength,
            "peak_autocorr_lag": peak_lag,
            "peak_autocorr_value": peak_corr
        }
        
        # Classify pattern
        if cv < 0.1 and trend_strength < 0.1:
            detected_pattern["pattern"] = "constant"
        elif trend_strength > 0.5:
            detected_pattern["pattern"] = "trend"
        elif abs(peak_corr) > 0.5:
            detected_pattern["pattern"] = "seasonal"
        elif cv > 0.5:
            detected_pattern["pattern"] = "irregular"
        else:
            detected_pattern["pattern"] = "mixed"
        
        return detected_pattern