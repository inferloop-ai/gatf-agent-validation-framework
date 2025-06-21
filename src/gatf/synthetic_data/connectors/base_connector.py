"""
Base Connector for Synthetic Data Platforms

This module defines the abstract base class for all synthetic data platform
connectors. It provides a consistent interface for integrating with various
synthetic data generation services.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

from ...core.exceptions import (
    ConnectorError,
    PlatformAuthenticationError,
    PlatformAPIError,
    DataGenerationError
)
from ...utils.logging import get_logger, log_performance

logger = get_logger(__name__)


class PlatformType(Enum):
    """Supported synthetic data platforms."""
    INFERLOOP = "inferloop"
    GRETEL = "gretel"
    MOSTLY_AI = "mostly_ai"
    SDV = "synthetic_data_vault"
    HAZY = "hazy"
    CUSTOM = "custom"


class GenerationStatus(Enum):
    """Status of data generation jobs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataFormat(Enum):
    """Supported data formats."""
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    ARROW = "arrow"
    PICKLE = "pickle"
    CUSTOM = "custom"


@dataclass
class PlatformConfig:
    """Configuration for synthetic data platform."""
    platform_type: PlatformType
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    endpoint_url: Optional[str] = None
    timeout: float = 300.0
    max_retries: int = 3
    retry_delay: float = 1.0
    verify_ssl: bool = True
    additional_config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration."""
        if self.platform_type != PlatformType.CUSTOM and not self.api_key:
            logger.warning(f"No API key provided for {self.platform_type.value}")


@dataclass
class GenerationRequest:
    """Request for synthetic data generation."""
    request_id: str
    data_type: str  # tabular, text, time_series, etc.
    schema: Optional[Dict[str, Any]] = None
    sample_data: Optional[Any] = None
    num_records: int = 100
    parameters: Dict[str, Any] = field(default_factory=dict)
    output_format: DataFormat = DataFormat.JSON
    privacy_settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "data_type": self.data_type,
            "schema": self.schema,
            "num_records": self.num_records,
            "parameters": self.parameters,
            "output_format": self.output_format.value,
            "privacy_settings": self.privacy_settings,
            "metadata": self.metadata
        }


@dataclass
class GenerationResponse:
    """Response from synthetic data generation."""
    request_id: str
    job_id: Optional[str] = None
    status: GenerationStatus = GenerationStatus.PENDING
    data: Optional[Any] = None
    data_location: Optional[str] = None
    generation_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "job_id": self.job_id,
            "status": self.status.value,
            "data_location": self.data_location,
            "generation_time": self.generation_time,
            "metadata": self.metadata,
            "error": self.error
        }


@dataclass
class DataQualityReport:
    """Quality report for generated synthetic data."""
    statistical_similarity: float  # 0-1 score
    privacy_score: float  # 0-1 score
    utility_score: float  # 0-1 score
    completeness: float  # 0-1 score
    validity: float  # 0-1 score
    uniqueness: float  # 0-1 score
    consistency: float  # 0-1 score
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def overall_score(self) -> float:
        """Calculate overall quality score."""
        scores = [
            self.statistical_similarity,
            self.privacy_score,
            self.utility_score,
            self.completeness,
            self.validity,
            self.uniqueness,
            self.consistency
        ]
        return sum(scores) / len(scores)


class BaseSyntheticDataConnector(ABC):
    """
    Abstract base class for synthetic data platform connectors.
    
    This class defines the interface that all platform connectors must implement
    to ensure consistent integration across different synthetic data services.
    """
    
    def __init__(self, config: PlatformConfig):
        """
        Initialize the connector.
        
        Args:
            config: Platform configuration
        """
        self.config = config
        self._authenticated = False
        self._session = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        
    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        """Return the platform type."""
        pass
    
    @property
    @abstractmethod
    def supported_data_types(self) -> List[str]:
        """Return list of supported data types."""
        pass
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the platform.
        
        Returns:
            True if authentication successful
            
        Raises:
            PlatformAuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    async def generate_data(
        self,
        request: GenerationRequest
    ) -> GenerationResponse:
        """
        Generate synthetic data.
        
        Args:
            request: Generation request
            
        Returns:
            Generation response
            
        Raises:
            DataGenerationError: If generation fails
        """
        pass
    
    @abstractmethod
    async def get_job_status(
        self,
        job_id: str
    ) -> GenerationStatus:
        """
        Get status of a generation job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Current job status
        """
        pass
    
    @abstractmethod
    async def get_generated_data(
        self,
        job_id: str,
        format: Optional[DataFormat] = None
    ) -> Any:
        """
        Retrieve generated data.
        
        Args:
            job_id: Job identifier
            format: Desired output format
            
        Returns:
            Generated data
        """
        pass
    
    @abstractmethod
    async def cancel_job(
        self,
        job_id: str
    ) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cancellation successful
        """
        pass
    
    @abstractmethod
    async def get_data_quality_report(
        self,
        job_id: str
    ) -> DataQualityReport:
        """
        Get quality report for generated data.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Data quality report
        """
        pass
    
    def ensure_authenticated(self) -> None:
        """Ensure connector is authenticated."""
        if not self._authenticated:
            raise PlatformAuthenticationError(
                f"Not authenticated with {self.platform_type.value}"
            )
    
    @log_performance
    async def generate_and_wait(
        self,
        request: GenerationRequest,
        poll_interval: float = 5.0,
        max_wait_time: Optional[float] = None
    ) -> GenerationResponse:
        """
        Generate data and wait for completion.
        
        Args:
            request: Generation request
            poll_interval: Polling interval in seconds
            max_wait_time: Maximum wait time in seconds
            
        Returns:
            Completed generation response
        """
        # Start generation
        response = await self.generate_data(request)
        
        if response.status == GenerationStatus.COMPLETED:
            return response
        
        # Wait for completion
        start_time = time.time()
        max_wait = max_wait_time or self.config.timeout
        
        while response.status in [GenerationStatus.PENDING, GenerationStatus.RUNNING]:
            # Check timeout
            if time.time() - start_time > max_wait:
                # Try to cancel the job
                if response.job_id:
                    await self.cancel_job(response.job_id)
                raise DataGenerationError(
                    f"Generation timeout after {max_wait} seconds"
                )
            
            # Wait before polling
            await asyncio.sleep(poll_interval)
            
            # Check status
            if response.job_id:
                response.status = await self.get_job_status(response.job_id)
                
                if response.status == GenerationStatus.COMPLETED:
                    # Retrieve data
                    response.data = await self.get_generated_data(
                        response.job_id,
                        request.output_format
                    )
                    response.generation_time = time.time() - start_time
        
        if response.status == GenerationStatus.FAILED:
            raise DataGenerationError(
                f"Generation failed: {response.error or 'Unknown error'}"
            )
        
        return response
    
    async def batch_generate(
        self,
        requests: List[GenerationRequest],
        max_concurrent: int = 3
    ) -> List[GenerationResponse]:
        """
        Generate multiple datasets concurrently.
        
        Args:
            requests: List of generation requests
            max_concurrent: Maximum concurrent generations
            
        Returns:
            List of generation responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: GenerationRequest):
            async with semaphore:
                try:
                    return await self.generate_and_wait(request)
                except Exception as e:
                    logger.error(f"Batch generation failed for {request.request_id}: {str(e)}")
                    return GenerationResponse(
                        request_id=request.request_id,
                        status=GenerationStatus.FAILED,
                        error=str(e)
                    )
        
        tasks = [generate_with_semaphore(req) for req in requests]
        return await asyncio.gather(*tasks)
    
    async def stream_generate(
        self,
        request: GenerationRequest,
        chunk_size: int = 1000
    ) -> AsyncGenerator[Any, None]:
        """
        Stream generated data in chunks.
        
        Args:
            request: Generation request
            chunk_size: Size of each chunk
            
        Yields:
            Data chunks
        """
        # Generate data
        response = await self.generate_and_wait(request)
        
        if not response.data:
            return
        
        # Stream data in chunks
        if isinstance(response.data, (list, tuple)):
            for i in range(0, len(response.data), chunk_size):
                yield response.data[i:i + chunk_size]
        else:
            # For non-list data, yield as single chunk
            yield response.data
    
    def validate_request(self, request: GenerationRequest) -> List[str]:
        """
        Validate generation request.
        
        Args:
            request: Generation request
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check data type support
        if request.data_type not in self.supported_data_types:
            errors.append(
                f"Data type '{request.data_type}' not supported. "
                f"Supported types: {', '.join(self.supported_data_types)}"
            )
        
        # Check num_records
        if request.num_records <= 0:
            errors.append("Number of records must be positive")
        
        # Platform-specific validation
        platform_errors = self._validate_platform_request(request)
        errors.extend(platform_errors)
        
        return errors
    
    def _validate_platform_request(self, request: GenerationRequest) -> List[str]:
        """
        Platform-specific request validation.
        
        Override in subclasses for custom validation.
        
        Args:
            request: Generation request
            
        Returns:
            List of validation errors
        """
        return []
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check platform health and connectivity.
        
        Returns:
            Health status information
        """
        health_info = {
            "platform": self.platform_type.value,
            "authenticated": self._authenticated,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Try to authenticate if not already
            if not self._authenticated:
                auth_success = await self.authenticate()
                health_info["authentication"] = "success" if auth_success else "failed"
            else:
                health_info["authentication"] = "active"
            
            # Platform-specific health checks
            platform_health = await self._platform_health_check()
            health_info.update(platform_health)
            
            health_info["status"] = "healthy"
            
        except Exception as e:
            health_info["status"] = "unhealthy"
            health_info["error"] = str(e)
        
        return health_info
    
    async def _platform_health_check(self) -> Dict[str, Any]:
        """
        Platform-specific health check.
        
        Override in subclasses for custom health checks.
        
        Returns:
            Platform-specific health information
        """
        return {}
    
    async def close(self) -> None:
        """Clean up resources."""
        if self._session:
            await self._session.close()
        self._executor.shutdown(wait=True)
        logger.info(f"Closed {self.platform_type.value} connector")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"{self.__class__.__name__}("
            f"platform={self.platform_type.value}, "
            f"authenticated={self._authenticated})"
        )