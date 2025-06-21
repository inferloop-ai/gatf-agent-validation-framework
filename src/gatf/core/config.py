"""
GATF Configuration Management Module

This module handles all configuration aspects of the Global AI Trust Framework,
including environment-specific settings, platform integrations, and domain configurations.
"""

import os
import yaml
import json
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging
from copy import deepcopy


class Environment(Enum):
    """Supported environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class ConfigurationError(Exception):
    """Raised when there's an error in configuration"""
    pass


@dataclass
class PlatformConfig:
    """Configuration for external platform integrations"""
    enabled: bool = False
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 1
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    def validate(self):
        """Validate platform configuration"""
        if self.enabled and not self.api_key:
            raise ConfigurationError("API key required when platform is enabled")
        if self.enabled and not self.base_url:
            raise ConfigurationError("Base URL required when platform is enabled")


@dataclass
class SyntheticDataConfig:
    """Configuration for synthetic data generation"""
    default_platform: str = "inferloop"
    platform_preferences: Dict[str, List[str]] = field(default_factory=dict)
    quality_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "statistical_similarity": 0.85,
        "privacy_preservation": 0.95,
        "data_utility": 0.90
    })
    generation_timeout: int = 300
    max_retries: int = 3
    cache_enabled: bool = True
    cache_ttl: int = 3600


@dataclass
class ValidationConfig:
    """Configuration for validation engines"""
    parallel_execution: bool = True
    max_workers: int = 4
    timeout_per_test: int = 60
    enable_human_in_loop: bool = True
    hitl_threshold: float = 0.7
    batch_size: int = 100
    validation_cache_ttl: int = 1800
    
    # Validation thresholds
    quality_threshold: float = 0.8
    bias_threshold: float = 0.15
    security_threshold: float = 0.9
    compliance_threshold: float = 0.95
    fairness_threshold: float = 0.85


@dataclass
class TrustScoringConfig:
    """Configuration for trust scoring and badges"""
    scoring_algorithm: str = "weighted_average"
    confidence_level: float = 0.95
    
    # Weight configuration for different validation types
    weights: Dict[str, float] = field(default_factory=lambda: {
        "quality": 0.25,
        "bias": 0.20,
        "security": 0.20,
        "compliance": 0.20,
        "fairness": 0.15
    })
    
    # Badge thresholds
    badge_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "basic": 0.60,
        "validated": 0.75,
        "certified": 0.85,
        "premium": 0.95
    })
    
    # Score validity period (in days)
    score_validity_days: int = 30
    continuous_monitoring: bool = True
    drift_detection_threshold: float = 0.1


@dataclass
class APIConfig:
    """Configuration for API services"""
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api"
    version: str = "v1"
    cors_enabled: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60
    api_key_header: str = "X-API-Key"
    request_timeout: int = 30
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    enable_graphql: bool = True
    enable_webhooks: bool = True


@dataclass
class DatabaseConfig:
    """Configuration for database connections"""
    driver: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    username: str = "gatf_user"
    password: Optional[str] = None
    database: str = "gatf"
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    echo: bool = False
    
    @property
    def connection_string(self) -> str:
        """Generate database connection string"""
        password = self.password or os.getenv("GATF_DB_PASSWORD", "")
        return f"{self.driver}://{self.username}:{password}@{self.host}:{self.port}/{self.database}"


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and observability"""
    enabled: bool = True
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    logging_level: str = "INFO"
    
    # Prometheus configuration
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    
    # Grafana configuration
    grafana_enabled: bool = True
    grafana_url: str = "http://localhost:3000"
    
    # Alert configuration
    alerting_enabled: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["email", "slack"])
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "error_rate": 0.05,
        "response_time": 1000,  # ms
        "cpu_usage": 0.8,
        "memory_usage": 0.8
    })


@dataclass
class SecurityConfig:
    """Configuration for security settings"""
    encryption_enabled: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    jwt_enabled: bool = True
    jwt_algorithm: str = "RS256"
    jwt_expiry_hours: int = 24
    api_key_rotation_days: int = 90
    
    # TLS configuration
    tls_enabled: bool = True
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    tls_verify_client: bool = False
    
    # Security headers
    security_headers: Dict[str, str] = field(default_factory=lambda: {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
    })


class GATFConfig:
    """Main configuration class for GATF"""
    
    def __init__(self, environment: Optional[Environment] = None):
        self.environment = environment or Environment(
            os.getenv("GATF_ENV", "development").lower()
        )
        self.config_dir = Path(__file__).parent.parent.parent.parent / "configs"
        
        # Initialize configurations
        self.api = APIConfig()
        self.database = DatabaseConfig()
        self.monitoring = MonitoringConfig()
        self.security = SecurityConfig()
        self.validation = ValidationConfig()
        self.trust_scoring = TrustScoringConfig()
        self.synthetic_data = SyntheticDataConfig()
        
        # Platform configurations
        self.platforms = {
            "inferloop": PlatformConfig(enabled=True),
            "gretel": PlatformConfig(),
            "mostly_ai": PlatformConfig(),
            "sdv": PlatformConfig(),
            "hazy": PlatformConfig()
        }
        
        # Domain configurations
        self.domains: Dict[str, Dict[str, Any]] = {}
        
        # Load configurations
        self._load_config()
        
        # Validate configurations
        self._validate_config()
    
    def _load_config(self):
        """Load configuration from files and environment variables"""
        # Load base configuration
        base_config_path = self.config_dir / "base.yaml"
        if base_config_path.exists():
            self._load_yaml_config(base_config_path)
        
        # Load environment-specific configuration
        env_config_path = self.config_dir / "environments" / f"{self.environment.value}.yaml"
        if env_config_path.exists():
            self._load_yaml_config(env_config_path)
        
        # Load domain configurations
        domain_config_dir = self.config_dir / "domains"
        if domain_config_dir.exists():
            for domain_file in domain_config_dir.glob("*.yaml"):
                domain_name = domain_file.stem.replace("_config", "")
                self.domains[domain_name] = self._load_yaml_file(domain_file)
        
        # Override with environment variables
        self._load_env_vars()
    
    def _load_yaml_config(self, path: Path):
        """Load configuration from YAML file"""
        config_data = self._load_yaml_file(path)
        
        # Update configurations
        if "api" in config_data:
            self._update_dataclass(self.api, config_data["api"])
        if "database" in config_data:
            self._update_dataclass(self.database, config_data["database"])
        if "monitoring" in config_data:
            self._update_dataclass(self.monitoring, config_data["monitoring"])
        if "security" in config_data:
            self._update_dataclass(self.security, config_data["security"])
        if "validation" in config_data:
            self._update_dataclass(self.validation, config_data["validation"])
        if "trust_scoring" in config_data:
            self._update_dataclass(self.trust_scoring, config_data["trust_scoring"])
        if "synthetic_data" in config_data:
            self._update_dataclass(self.synthetic_data, config_data["synthetic_data"])
        
        # Update platform configurations
        if "platforms" in config_data:
            for platform, platform_config in config_data["platforms"].items():
                if platform in self.platforms:
                    self._update_dataclass(self.platforms[platform], platform_config)
    
    def _load_yaml_file(self, path: Path) -> Dict[str, Any]:
        """Load YAML file and return dictionary"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.warning(f"Failed to load config file {path}: {e}")
            return {}
    
    def _update_dataclass(self, obj: Any, data: Dict[str, Any]):
        """Update dataclass fields from dictionary"""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
    
    def _load_env_vars(self):
        """Load configuration from environment variables"""
        # API configuration
        if os.getenv("GATF_API_HOST"):
            self.api.host = os.getenv("GATF_API_HOST")
        if os.getenv("GATF_API_PORT"):
            self.api.port = int(os.getenv("GATF_API_PORT"))
        
        # Database configuration
        if os.getenv("GATF_DB_HOST"):
            self.database.host = os.getenv("GATF_DB_HOST")
        if os.getenv("GATF_DB_PORT"):
            self.database.port = int(os.getenv("GATF_DB_PORT"))
        if os.getenv("GATF_DB_USERNAME"):
            self.database.username = os.getenv("GATF_DB_USERNAME")
        if os.getenv("GATF_DB_PASSWORD"):
            self.database.password = os.getenv("GATF_DB_PASSWORD")
        
        # Platform API keys
        for platform in self.platforms:
            env_key = f"GATF_{platform.upper()}_API_KEY"
            if os.getenv(env_key):
                self.platforms[platform].api_key = os.getenv(env_key)
                self.platforms[platform].enabled = True
        
        # Security settings
        if os.getenv("GATF_JWT_SECRET"):
            self.security.jwt_secret = os.getenv("GATF_JWT_SECRET")
        if os.getenv("GATF_ENCRYPTION_KEY"):
            self.security.encryption_key = os.getenv("GATF_ENCRYPTION_KEY")
    
    def _validate_config(self):
        """Validate all configurations"""
        # Validate platform configurations
        for platform_name, platform_config in self.platforms.items():
            try:
                platform_config.validate()
            except ConfigurationError as e:
                raise ConfigurationError(f"Invalid {platform_name} configuration: {e}")
        
        # Validate trust scoring weights
        total_weight = sum(self.trust_scoring.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            raise ConfigurationError(f"Trust scoring weights must sum to 1.0, got {total_weight}")
        
        # Validate thresholds
        for threshold_name, threshold_value in self.trust_scoring.badge_thresholds.items():
            if not 0 <= threshold_value <= 1:
                raise ConfigurationError(f"Badge threshold {threshold_name} must be between 0 and 1")
    
    def get_domain_config(self, domain: str) -> Dict[str, Any]:
        """Get configuration for a specific domain"""
        if domain not in self.domains:
            logging.warning(f"No specific configuration for domain '{domain}', using defaults")
            return {}
        return deepcopy(self.domains[domain])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "environment": self.environment.value,
            "api": self.api.__dict__,
            "database": {k: v for k, v in self.database.__dict__.items() if k != "password"},
            "monitoring": self.monitoring.__dict__,
            "security": {k: v for k, v in self.security.__dict__.items() if k not in ["jwt_secret", "encryption_key"]},
            "validation": self.validation.__dict__,
            "trust_scoring": self.trust_scoring.__dict__,
            "synthetic_data": self.synthetic_data.__dict__,
            "platforms": {name: config.__dict__ for name, config in self.platforms.items()},
            "domains": list(self.domains.keys())
        }
    
    def save_to_file(self, path: Union[str, Path]):
        """Save current configuration to file"""
        path = Path(path)
        config_dict = self.to_dict()
        
        if path.suffix == ".json":
            with open(path, 'w') as f:
                json.dump(config_dict, f, indent=2)
        elif path.suffix in [".yaml", ".yml"]:
            with open(path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False)
        else:
            raise ValueError("Unsupported file format. Use .json or .yaml")


# Global configuration instance
_config: Optional[GATFConfig] = None


def get_config() -> GATFConfig:
    """Get or create global configuration instance"""
    global _config
    if _config is None:
        _config = GATFConfig()
    return _config


def reset_config(environment: Optional[Environment] = None):
    """Reset global configuration instance"""
    global _config
    _config = GATFConfig(environment)
    return _config