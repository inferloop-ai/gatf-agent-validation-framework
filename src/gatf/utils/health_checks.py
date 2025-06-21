"""
GATF Health Check Utilities

This module provides health check functionality for monitoring the health
and status of various components in the GATF framework.
"""

import time
import asyncio
import psutil
import socket
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import httpx
import redis
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging


class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Types of components to health check"""
    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    EXTERNAL_API = "external_api"
    STORAGE = "storage"
    COMPUTE = "compute"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    component_name: str
    component_type: ComponentType
    status: HealthStatus
    response_time_ms: Optional[float] = None
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_healthy(self) -> bool:
        """Check if component is healthy"""
        return self.status == HealthStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "component_name": self.component_name,
            "component_type": self.component_type.value,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at.isoformat()
        }


@dataclass
class SystemHealthMetrics:
    """System-level health metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    open_connections: int
    process_count: int
    load_average: Tuple[float, float, float]
    uptime_seconds: float
    
    @classmethod
    def collect(cls) -> 'SystemHealthMetrics':
        """Collect current system metrics"""
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # Get network connections
        try:
            connections = len(psutil.net_connections())
        except:
            connections = 0
        
        # Get process count
        process_count = len(psutil.pids())
        
        # Get load average
        load_average = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0.0, 0.0, 0.0)
        
        # Get uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        return cls(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
            open_connections=connections,
            process_count=process_count,
            load_average=load_average,
            uptime_seconds=uptime_seconds
        )
    
    def get_health_status(self) -> HealthStatus:
        """Determine health status based on metrics"""
        # Define thresholds
        if (self.cpu_percent > 90 or 
            self.memory_percent > 90 or 
            self.disk_percent > 95):
            return HealthStatus.UNHEALTHY
        elif (self.cpu_percent > 80 or 
              self.memory_percent > 80 or 
              self.disk_percent > 90):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY


class HealthChecker:
    """Main health checker class"""
    
    def __init__(self, timeout: float = 5.0):
        """
        Initialize health checker
        
        Args:
            timeout: Default timeout for health checks
        """
        self.timeout = timeout
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        
    def register_check(
        self,
        name: str,
        check_func: Callable[[], Union[bool, HealthCheckResult]],
        component_type: ComponentType = ComponentType.SERVICE
    ):
        """
        Register a health check
        
        Args:
            name: Name of the component
            check_func: Function that performs the health check
            component_type: Type of component
        """
        self._checks[name] = (check_func, component_type)
    
    def check_http_endpoint(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        timeout: Optional[float] = None
    ) -> HealthCheckResult:
        """
        Check HTTP endpoint health
        
        Args:
            name: Name of the endpoint
            url: URL to check
            expected_status: Expected HTTP status code
            timeout: Request timeout
        
        Returns:
            Health check result
        """
        timeout = timeout or self.timeout
        start_time = time.time()
        
        try:
            response = httpx.get(url, timeout=timeout)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == expected_status:
                return HealthCheckResult(
                    component_name=name,
                    component_type=ComponentType.EXTERNAL_API,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    message=f"HTTP {response.status_code}",
                    details={"status_code": response.status_code}
                )
            else:
                return HealthCheckResult(
                    component_name=name,
                    component_type=ComponentType.EXTERNAL_API,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    message=f"Unexpected status: HTTP {response.status_code}",
                    details={"status_code": response.status_code}
                )
        except Exception as e:
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.EXTERNAL_API,
                status=HealthStatus.UNHEALTHY,
                message=f"HTTP check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def check_database(
        self,
        name: str,
        connection_func: Callable[[], Any],
        query: str = "SELECT 1"
    ) -> HealthCheckResult:
        """
        Check database health
        
        Args:
            name: Name of the database
            connection_func: Function that returns a database connection
            query: Query to execute
        
        Returns:
            Health check result
        """
        start_time = time.time()
        
        try:
            conn = connection_func()
            cursor = conn.cursor()
            cursor.execute(query)
            cursor.close()
            conn.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="Database connection successful"
            )
        except Exception as e:
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def check_redis(
        self,
        name: str,
        redis_client: redis.Redis
    ) -> HealthCheckResult:
        """
        Check Redis health
        
        Args:
            name: Name of the Redis instance
            redis_client: Redis client
        
        Returns:
            Health check result
        """
        start_time = time.time()
        
        try:
            # Ping Redis
            redis_client.ping()
            
            # Get some basic info
            info = redis_client.info()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.CACHE,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="Redis connection successful",
                details={
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "uptime_in_seconds": info.get("uptime_in_seconds", 0)
                }
            )
        except Exception as e:
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.CACHE,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def check_port(
        self,
        name: str,
        host: str,
        port: int,
        timeout: Optional[float] = None
    ) -> HealthCheckResult:
        """
        Check if a port is open
        
        Args:
            name: Name of the service
            host: Host to check
            port: Port to check
            timeout: Connection timeout
        
        Returns:
            Health check result
        """
        timeout = timeout or self.timeout
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            response_time = (time.time() - start_time) * 1000
            
            if result == 0:
                return HealthCheckResult(
                    component_name=name,
                    component_type=ComponentType.SERVICE,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    message=f"Port {port} is open",
                    details={"host": host, "port": port}
                )
            else:
                return HealthCheckResult(
                    component_name=name,
                    component_type=ComponentType.SERVICE,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Port {port} is closed",
                    details={"host": host, "port": port}
                )
        except Exception as e:
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.SERVICE,
                status=HealthStatus.UNHEALTHY,
                message=f"Port check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def check_disk_space(
        self,
        name: str = "disk",
        path: str = "/",
        min_free_percent: float = 10.0
    ) -> HealthCheckResult:
        """
        Check disk space availability
        
        Args:
            name: Name for this check
            path: Path to check
            min_free_percent: Minimum free space percentage
        
        Returns:
            Health check result
        """
        try:
            usage = psutil.disk_usage(path)
            free_percent = 100 - usage.percent
            
            if free_percent < min_free_percent:
                status = HealthStatus.UNHEALTHY
                message = f"Low disk space: {free_percent:.1f}% free"
            elif free_percent < min_free_percent * 2:
                status = HealthStatus.DEGRADED
                message = f"Disk space warning: {free_percent:.1f}% free"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {free_percent:.1f}% free"
            
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.STORAGE,
                status=status,
                message=message,
                details={
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "free_gb": usage.free / (1024**3),
                    "percent_used": usage.percent
                }
            )
        except Exception as e:
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.STORAGE,
                status=HealthStatus.UNHEALTHY,
                message=f"Disk check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def run_check(self, name: str) -> HealthCheckResult:
        """
        Run a single health check
        
        Args:
            name: Name of the check to run
        
        Returns:
            Health check result
        """
        if name not in self._checks:
            return HealthCheckResult(
                component_name=name,
                component_type=ComponentType.SERVICE,
                status=HealthStatus.UNKNOWN,
                message="Check not registered"
            )
        
        check_func, component_type = self._checks[name]
        
        try:
            result = check_func()
            
            # Convert boolean result to HealthCheckResult
            if isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                result = HealthCheckResult(
                    component_name=name,
                    component_type=component_type,
                    status=status
                )
            
            self._last_results[name] = result
            return result
            
        except Exception as e:
            result = HealthCheckResult(
                component_name=name,
                component_type=component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                details={"error": str(e)}
            )
            self._last_results[name] = result
            return result
    
    def run_all_checks(self, parallel: bool = True) -> Dict[str, HealthCheckResult]:
        """
        Run all registered health checks
        
        Args:
            parallel: Whether to run checks in parallel
        
        Returns:
            Dictionary of check results
        """
        results = {}
        
        if parallel and len(self._checks) > 1:
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_name = {
                    executor.submit(self.run_check, name): name
                    for name in self._checks
                }
                
                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        result = future.result()
                        results[name] = result
                    except Exception as e:
                        results[name] = HealthCheckResult(
                            component_name=name,
                            component_type=ComponentType.SERVICE,
                            status=HealthStatus.UNHEALTHY,
                            message=f"Check execution failed: {str(e)}"
                        )
        else:
            for name in self._checks:
                results[name] = self.run_check(name)
        
        return results
    
    def get_system_health(self) -> Tuple[SystemHealthMetrics, HealthStatus]:
        """
        Get system-level health metrics
        
        Returns:
            Tuple of (metrics, health_status)
        """
        metrics = SystemHealthMetrics.collect()
        status = metrics.get_health_status()
        return metrics, status
    
    def get_overall_health(self) -> Dict[str, Any]:
        """
        Get overall system health status
        
        Returns:
            Overall health report
        """
        # Run all checks
        check_results = self.run_all_checks()
        
        # Get system metrics
        system_metrics, system_status = self.get_system_health()
        
        # Determine overall status
        unhealthy_count = sum(1 for r in check_results.values() if r.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for r in check_results.values() if r.status == HealthStatus.DEGRADED)
        
        if unhealthy_count > 0 or system_status == HealthStatus.UNHEALTHY:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0 or system_status == HealthStatus.DEGRADED:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {name: result.to_dict() for name, result in check_results.items()},
            "system": {
                "status": system_status.value,
                "metrics": {
                    "cpu_percent": system_metrics.cpu_percent,
                    "memory_percent": system_metrics.memory_percent,
                    "disk_percent": system_metrics.disk_percent,
                    "open_connections": system_metrics.open_connections,
                    "process_count": system_metrics.process_count,
                    "load_average": system_metrics.load_average,
                    "uptime_hours": system_metrics.uptime_seconds / 3600
                }
            },
            "summary": {
                "total_checks": len(check_results),
                "healthy": sum(1 for r in check_results.values() if r.status == HealthStatus.HEALTHY),
                "degraded": degraded_count,
                "unhealthy": unhealthy_count
            }
        }


async def run_health_checks(
    checker: HealthChecker,
    interval: int = 60,
    callback: Optional[Callable[[Dict[str, Any]], None]] = None
):
    """
    Run health checks periodically
    
    Args:
        checker: Health checker instance
        interval: Check interval in seconds
        callback: Optional callback for results
    """
    while True:
        try:
            health_report = checker.get_overall_health()
            
            if callback:
                callback(health_report)
            
            # Log if unhealthy
            if health_report["status"] != "healthy":
                logging.warning(f"System health check: {health_report['status']}")
            
        except Exception as e:
            logging.error(f"Health check error: {str(e)}")
        
        await asyncio.sleep(interval)


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get or create global health checker"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker