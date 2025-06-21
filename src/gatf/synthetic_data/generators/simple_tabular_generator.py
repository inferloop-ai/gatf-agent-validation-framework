"""
Simple Tabular Data Generator

This module provides basic tabular/CSV synthetic data generation capabilities
for testing and development purposes. It can generate various column types
with realistic distributions.
"""

from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import string
from faker import Faker

from ...core.exceptions import DataGenerationError
from ...utils.logging import get_logger, log_performance

logger = get_logger(__name__)
fake = Faker()


class SimpleTabularGenerator:
    """
    Simple tabular data generator for creating synthetic datasets.
    
    This generator can create DataFrames with various column types including:
    - Numeric (integers, floats)
    - Categorical
    - Text
    - Dates/timestamps
    - Boolean
    - IDs/codes
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the tabular generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            Faker.seed(seed)
        
        self.fake = Faker()
        
    @log_performance
    def generate(
        self,
        schema: Dict[str, Dict[str, Any]],
        num_rows: int,
        **kwargs
    ) -> pd.DataFrame:
        """
        Generate tabular data based on schema.
        
        Args:
            schema: Column definitions
            num_rows: Number of rows to generate
            **kwargs: Additional generation parameters
            
        Returns:
            Generated DataFrame
            
        Example schema:
            {
                "user_id": {"type": "id", "prefix": "USR"},
                "age": {"type": "integer", "min": 18, "max": 80},
                "salary": {"type": "float", "min": 30000, "max": 200000},
                "department": {"type": "categorical", "values": ["Sales", "IT", "HR"]},
                "hire_date": {"type": "date", "start": "2020-01-01", "end": "2023-12-31"},
                "is_active": {"type": "boolean", "probability": 0.9}
            }
        """
        if num_rows <= 0:
            raise DataGenerationError("Number of rows must be positive")
        
        if not schema:
            raise DataGenerationError("Schema cannot be empty")
        
        data = {}
        
        for column_name, column_spec in schema.items():
            try:
                column_type = column_spec.get("type", "string")
                
                if column_type == "id":
                    data[column_name] = self._generate_ids(
                        num_rows,
                        column_spec.get("prefix", "ID"),
                        column_spec.get("length", 8)
                    )
                
                elif column_type == "integer":
                    data[column_name] = self._generate_integers(
                        num_rows,
                        column_spec.get("min", 0),
                        column_spec.get("max", 100),
                        column_spec.get("distribution", "uniform")
                    )
                
                elif column_type == "float":
                    data[column_name] = self._generate_floats(
                        num_rows,
                        column_spec.get("min", 0.0),
                        column_spec.get("max", 1.0),
                        column_spec.get("distribution", "uniform"),
                        column_spec.get("decimals", 2)
                    )
                
                elif column_type == "categorical":
                    data[column_name] = self._generate_categorical(
                        num_rows,
                        column_spec.get("values", ["A", "B", "C"]),
                        column_spec.get("probabilities")
                    )
                
                elif column_type == "text":
                    data[column_name] = self._generate_text(
                        num_rows,
                        column_spec.get("min_length", 10),
                        column_spec.get("max_length", 100),
                        column_spec.get("text_type", "sentence")
                    )
                
                elif column_type == "date":
                    data[column_name] = self._generate_dates(
                        num_rows,
                        column_spec.get("start", "2020-01-01"),
                        column_spec.get("end", "2023-12-31"),
                        column_spec.get("format", "%Y-%m-%d")
                    )
                
                elif column_type == "datetime":
                    data[column_name] = self._generate_datetimes(
                        num_rows,
                        column_spec.get("start", "2020-01-01 00:00:00"),
                        column_spec.get("end", "2023-12-31 23:59:59")
                    )
                
                elif column_type == "boolean":
                    data[column_name] = self._generate_booleans(
                        num_rows,
                        column_spec.get("probability", 0.5)
                    )
                
                elif column_type == "email":
                    data[column_name] = self._generate_emails(num_rows)
                
                elif column_type == "phone":
                    data[column_name] = self._generate_phones(num_rows)
                
                elif column_type == "address":
                    data[column_name] = self._generate_addresses(num_rows)
                
                elif column_type == "name":
                    data[column_name] = self._generate_names(
                        num_rows,
                        column_spec.get("name_type", "full")
                    )
                
                else:
                    # Default to string
                    data[column_name] = self._generate_strings(
                        num_rows,
                        column_spec.get("length", 10)
                    )
                
            except Exception as e:
                logger.error(f"Failed to generate column '{column_name}': {str(e)}")
                raise DataGenerationError(
                    f"Error generating column '{column_name}': {str(e)}"
                )
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Apply any constraints
        if "constraints" in kwargs:
            df = self._apply_constraints(df, kwargs["constraints"])
        
        # Add missing values if specified
        if "missing_rate" in kwargs:
            df = self._add_missing_values(df, kwargs["missing_rate"])
        
        return df
    
    def _generate_ids(self, n: int, prefix: str, length: int) -> List[str]:
        """Generate unique IDs."""
        ids = []
        used_ids = set()
        
        while len(ids) < n:
            # Generate random alphanumeric suffix
            suffix = ''.join(random.choices(
                string.ascii_uppercase + string.digits,
                k=length
            ))
            id_val = f"{prefix}{suffix}"
            
            if id_val not in used_ids:
                ids.append(id_val)
                used_ids.add(id_val)
        
        return ids
    
    def _generate_integers(
        self,
        n: int,
        min_val: int,
        max_val: int,
        distribution: str
    ) -> np.ndarray:
        """Generate integer values."""
        if distribution == "uniform":
            return np.random.randint(min_val, max_val + 1, size=n)
        elif distribution == "normal":
            mean = (min_val + max_val) / 2
            std = (max_val - min_val) / 6  # 99.7% within range
            values = np.random.normal(mean, std, size=n)
            return np.clip(values, min_val, max_val).astype(int)
        elif distribution == "exponential":
            values = np.random.exponential(scale=(max_val - min_val) / 3, size=n)
            return (min_val + np.clip(values, 0, max_val - min_val)).astype(int)
        else:
            return np.random.randint(min_val, max_val + 1, size=n)
    
    def _generate_floats(
        self,
        n: int,
        min_val: float,
        max_val: float,
        distribution: str,
        decimals: int
    ) -> np.ndarray:
        """Generate float values."""
        if distribution == "uniform":
            values = np.random.uniform(min_val, max_val, size=n)
        elif distribution == "normal":
            mean = (min_val + max_val) / 2
            std = (max_val - min_val) / 6
            values = np.random.normal(mean, std, size=n)
            values = np.clip(values, min_val, max_val)
        elif distribution == "exponential":
            values = np.random.exponential(scale=(max_val - min_val) / 3, size=n)
            values = min_val + np.clip(values, 0, max_val - min_val)
        else:
            values = np.random.uniform(min_val, max_val, size=n)
        
        return np.round(values, decimals)
    
    def _generate_categorical(
        self,
        n: int,
        values: List[Any],
        probabilities: Optional[List[float]] = None
    ) -> List[Any]:
        """Generate categorical values."""
        if probabilities:
            # Normalize probabilities
            total = sum(probabilities)
            probs = [p / total for p in probabilities]
            return np.random.choice(values, size=n, p=probs).tolist()
        else:
            return np.random.choice(values, size=n).tolist()
    
    def _generate_text(
        self,
        n: int,
        min_length: int,
        max_length: int,
        text_type: str
    ) -> List[str]:
        """Generate text values."""
        texts = []
        
        for _ in range(n):
            if text_type == "sentence":
                text = self.fake.sentence()
            elif text_type == "paragraph":
                text = self.fake.paragraph()
            elif text_type == "word":
                text = self.fake.word()
            elif text_type == "company":
                text = self.fake.company()
            elif text_type == "job":
                text = self.fake.job()
            else:
                text = self.fake.text(max_nb_chars=max_length)
            
            # Adjust length if needed
            if len(text) > max_length:
                text = text[:max_length]
            elif len(text) < min_length:
                text = text + " " * (min_length - len(text))
            
            texts.append(text)
        
        return texts
    
    def _generate_dates(
        self,
        n: int,
        start: str,
        end: str,
        format: str
    ) -> List[str]:
        """Generate date values."""
        start_date = pd.to_datetime(start)
        end_date = pd.to_datetime(end)
        
        # Generate random timestamps
        timestamps = pd.to_datetime(
            np.random.uniform(
                start_date.timestamp(),
                end_date.timestamp(),
                size=n
            ),
            unit='s'
        )
        
        return [ts.strftime(format) for ts in timestamps]
    
    def _generate_datetimes(
        self,
        n: int,
        start: str,
        end: str
    ) -> List[datetime]:
        """Generate datetime values."""
        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        
        timestamps = pd.to_datetime(
            np.random.uniform(
                start_dt.timestamp(),
                end_dt.timestamp(),
                size=n
            ),
            unit='s'
        )
        
        return timestamps.tolist()
    
    def _generate_booleans(self, n: int, probability: float) -> List[bool]:
        """Generate boolean values."""
        return np.random.random(n) < probability
    
    def _generate_emails(self, n: int) -> List[str]:
        """Generate email addresses."""
        return [self.fake.email() for _ in range(n)]
    
    def _generate_phones(self, n: int) -> List[str]:
        """Generate phone numbers."""
        return [self.fake.phone_number() for _ in range(n)]
    
    def _generate_addresses(self, n: int) -> List[str]:
        """Generate addresses."""
        return [self.fake.address().replace('\n', ', ') for _ in range(n)]
    
    def _generate_names(self, n: int, name_type: str) -> List[str]:
        """Generate names."""
        names = []
        for _ in range(n):
            if name_type == "first":
                names.append(self.fake.first_name())
            elif name_type == "last":
                names.append(self.fake.last_name())
            elif name_type == "full":
                names.append(self.fake.name())
            else:
                names.append(self.fake.name())
        return names
    
    def _generate_strings(self, n: int, length: int) -> List[str]:
        """Generate random strings."""
        return [''.join(random.choices(
            string.ascii_letters + string.digits,
            k=length
        )) for _ in range(n)]
    
    def _apply_constraints(
        self,
        df: pd.DataFrame,
        constraints: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply constraints to the generated data."""
        # Example: Ensure column A > column B
        if "greater_than" in constraints:
            for constraint in constraints["greater_than"]:
                col1, col2 = constraint["column1"], constraint["column2"]
                if col1 in df.columns and col2 in df.columns:
                    mask = df[col1] <= df[col2]
                    df.loc[mask, col1] = df.loc[mask, col2] + 1
        
        # Example: Ensure unique combinations
        if "unique_together" in constraints:
            for columns in constraints["unique_together"]:
                if all(col in df.columns for col in columns):
                    df = df.drop_duplicates(subset=columns, keep='first')
        
        return df
    
    def _add_missing_values(
        self,
        df: pd.DataFrame,
        missing_rate: Union[float, Dict[str, float]]
    ) -> pd.DataFrame:
        """Add missing values to the data."""
        if isinstance(missing_rate, float):
            # Apply same rate to all columns
            for col in df.columns:
                mask = np.random.random(len(df)) < missing_rate
                df.loc[mask, col] = np.nan
        else:
            # Apply specific rates to columns
            for col, rate in missing_rate.items():
                if col in df.columns:
                    mask = np.random.random(len(df)) < rate
                    df.loc[mask, col] = np.nan
        
        return df
    
    def generate_correlated(
        self,
        n: int,
        columns: List[str],
        correlation_matrix: np.ndarray,
        means: Optional[List[float]] = None,
        stds: Optional[List[float]] = None
    ) -> pd.DataFrame:
        """
        Generate correlated numeric data.
        
        Args:
            n: Number of rows
            columns: Column names
            correlation_matrix: Correlation matrix
            means: Mean values for each column
            stds: Standard deviations for each column
            
        Returns:
            DataFrame with correlated data
        """
        num_vars = len(columns)
        
        if means is None:
            means = [0] * num_vars
        if stds is None:
            stds = [1] * num_vars
        
        # Generate uncorrelated data
        uncorrelated = np.random.randn(n, num_vars)
        
        # Apply correlation
        L = np.linalg.cholesky(correlation_matrix)
        correlated = uncorrelated @ L.T
        
        # Apply means and standard deviations
        for i in range(num_vars):
            correlated[:, i] = correlated[:, i] * stds[i] + means[i]
        
        return pd.DataFrame(correlated, columns=columns)