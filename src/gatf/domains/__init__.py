"""
GATF Domains Module

This module provides domain registration and discovery functionality.
It manages all available domain implementations and provides a unified
interface for domain access.
"""

from typing import Dict, Type, Optional, List, Any
import importlib
import inspect
from pathlib import Path

from .base_domain import BaseDomain, DomainType
from ..core.exceptions import (
    DomainNotFoundError,
    DomainRegistrationError,
    InvalidDomainError
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DomainRegistry:
    """
    Registry for managing domain implementations.
    
    This class provides functionality to:
    - Register new domains
    - Discover domains from the package
    - Instantiate domain objects
    - Query available domains
    """
    
    def __init__(self):
        """Initialize the domain registry."""
        self._domains: Dict[str, Type[BaseDomain]] = {}
        self._domain_instances: Dict[str, BaseDomain] = {}
        self._auto_discover = True
        
    def register(
        self,
        domain_class: Type[BaseDomain],
        override: bool = False
    ) -> None:
        """
        Register a domain implementation.
        
        Args:
            domain_class: The domain class to register
            override: Whether to override existing registration
            
        Raises:
            DomainRegistrationError: If registration fails
            InvalidDomainError: If domain class is invalid
        """
        # Validate domain class
        if not inspect.isclass(domain_class):
            raise InvalidDomainError(f"{domain_class} is not a class")
            
        if not issubclass(domain_class, BaseDomain):
            raise InvalidDomainError(
                f"{domain_class.__name__} must inherit from BaseDomain"
            )
        
        # Check if abstract methods are implemented
        abstract_methods = [
            method for method in dir(BaseDomain)
            if method.startswith('_') is False
            and callable(getattr(BaseDomain, method))
            and getattr(getattr(BaseDomain, method), '__isabstractmethod__', False)
        ]
        
        for method in abstract_methods:
            if getattr(getattr(domain_class, method), '__isabstractmethod__', False):
                raise InvalidDomainError(
                    f"{domain_class.__name__} must implement abstract method '{method}'"
                )
        
        # Get domain type
        try:
            instance = domain_class()
            domain_type = instance.domain_type.value
        except Exception as e:
            raise DomainRegistrationError(
                f"Failed to instantiate {domain_class.__name__}: {str(e)}"
            )
        
        # Check for existing registration
        if domain_type in self._domains and not override:
            raise DomainRegistrationError(
                f"Domain '{domain_type}' is already registered. "
                "Set override=True to replace it."
            )
        
        # Register the domain
        self._domains[domain_type] = domain_class
        logger.info(f"Registered domain: {domain_type} ({domain_class.__name__})")
        
    def unregister(self, domain_type: str) -> None:
        """
        Unregister a domain.
        
        Args:
            domain_type: The domain type to unregister
        """
        if domain_type in self._domains:
            del self._domains[domain_type]
            if domain_type in self._domain_instances:
                del self._domain_instances[domain_type]
            logger.info(f"Unregistered domain: {domain_type}")
        
    def get(
        self,
        domain_type: str,
        config: Optional[Dict[str, Any]] = None,
        force_new: bool = False
    ) -> BaseDomain:
        """
        Get a domain instance.
        
        Args:
            domain_type: The domain type to retrieve
            config: Optional configuration for the domain
            force_new: Force creation of a new instance
            
        Returns:
            Domain instance
            
        Raises:
            DomainNotFoundError: If domain type is not found
        """
        # Auto-discover domains if enabled
        if self._auto_discover and not self._domains:
            self.discover_domains()
        
        # Check if domain is registered
        if domain_type not in self._domains:
            available = list(self._domains.keys())
            raise DomainNotFoundError(domain_type, available)
        
        # Return cached instance if available and not forcing new
        if not force_new and domain_type in self._domain_instances:
            instance = self._domain_instances[domain_type]
            # Update config if provided
            if config:
                instance.config.update(config)
            return instance
        
        # Create new instance
        domain_class = self._domains[domain_type]
        try:
            instance = domain_class(config)
            instance.ensure_initialized()
            
            # Cache the instance
            if not force_new:
                self._domain_instances[domain_type] = instance
                
            logger.debug(f"Created domain instance: {domain_type}")
            return instance
            
        except Exception as e:
            raise DomainRegistrationError(
                f"Failed to create domain instance for '{domain_type}': {str(e)}"
            )
    
    def list_domains(self) -> List[str]:
        """
        List all registered domain types.
        
        Returns:
            List of domain type strings
        """
        if self._auto_discover and not self._domains:
            self.discover_domains()
        return list(self._domains.keys())
    
    def get_domain_info(self, domain_type: str) -> Dict[str, Any]:
        """
        Get information about a domain.
        
        Args:
            domain_type: The domain type
            
        Returns:
            Dictionary with domain information
        """
        instance = self.get(domain_type)
        return instance.to_dict()
    
    def discover_domains(self) -> None:
        """
        Auto-discover domain implementations from the package.
        
        This method scans the domains package for subdirectories
        containing domain implementations and automatically registers them.
        """
        logger.info("Starting domain auto-discovery...")
        
        # Get the domains package directory
        domains_dir = Path(__file__).parent
        
        # List of known domain subdirectories
        domain_subdirs = [
            "finance",
            "healthcare",
            "legal",
            "manufacturing",
            "retail",
            "cybersecurity",
            "hr",
            "research",
            "devops"
        ]
        
        discovered_count = 0
        
        for subdir in domain_subdirs:
            domain_path = domains_dir / subdir
            if not domain_path.exists() or not domain_path.is_dir():
                continue
                
            # Look for __init__.py in the subdirectory
            init_file = domain_path / "__init__.py"
            if not init_file.exists():
                continue
            
            try:
                # Import the module
                module_name = f"gatf.domains.{subdir}"
                module = importlib.import_module(module_name)
                
                # Look for classes that inherit from BaseDomain
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (obj != BaseDomain and
                        issubclass(obj, BaseDomain) and
                        not inspect.isabstract(obj)):
                        
                        try:
                            self.register(obj, override=False)
                            discovered_count += 1
                        except DomainRegistrationError:
                            # Domain might already be registered
                            pass
                        except Exception as e:
                            logger.warning(
                                f"Failed to register domain {name}: {str(e)}"
                            )
                            
            except ImportError as e:
                logger.debug(f"Could not import domain module {subdir}: {str(e)}")
            except Exception as e:
                logger.warning(f"Error discovering domains in {subdir}: {str(e)}")
        
        logger.info(f"Domain discovery complete. Found {discovered_count} domains.")
    
    def validate_all_domains(self) -> Dict[str, List[str]]:
        """
        Validate configuration for all registered domains.
        
        Returns:
            Dictionary mapping domain types to validation errors
        """
        results = {}
        
        for domain_type in self.list_domains():
            try:
                instance = self.get(domain_type)
                errors = instance.validate_config()
                if errors:
                    results[domain_type] = errors
            except Exception as e:
                results[domain_type] = [f"Validation failed: {str(e)}"]
        
        return results
    
    def clear_cache(self) -> None:
        """Clear the domain instance cache."""
        self._domain_instances.clear()
        logger.debug("Cleared domain instance cache")


# Global domain registry instance
_registry = DomainRegistry()


# Public API functions
def register_domain(
    domain_class: Type[BaseDomain],
    override: bool = False
) -> None:
    """
    Register a domain implementation.
    
    Args:
        domain_class: The domain class to register
        override: Whether to override existing registration
    """
    _registry.register(domain_class, override)


def get_domain(
    domain_type: str,
    config: Optional[Dict[str, Any]] = None,
    force_new: bool = False
) -> BaseDomain:
    """
    Get a domain instance.
    
    Args:
        domain_type: The domain type to retrieve
        config: Optional configuration for the domain
        force_new: Force creation of a new instance
        
    Returns:
        Domain instance
    """
    return _registry.get(domain_type, config, force_new)


def list_domains() -> List[str]:
    """
    List all registered domain types.
    
    Returns:
        List of domain type strings
    """
    return _registry.list_domains()


def discover_domains() -> None:
    """Auto-discover domain implementations."""
    _registry.discover_domains()


def get_domain_info(domain_type: str) -> Dict[str, Any]:
    """
    Get information about a domain.
    
    Args:
        domain_type: The domain type
        
    Returns:
        Dictionary with domain information
    """
    return _registry.get_domain_info(domain_type)


def validate_all_domains() -> Dict[str, List[str]]:
    """
    Validate configuration for all registered domains.
    
    Returns:
        Dictionary mapping domain types to validation errors
    """
    return _registry.validate_all_domains()


def clear_domain_cache() -> None:
    """Clear the domain instance cache."""
    _registry.clear_cache()


# Export public API
__all__ = [
    "BaseDomain",
    "DomainType",
    "register_domain",
    "get_domain",
    "list_domains",
    "discover_domains",
    "get_domain_info",
    "validate_all_domains",
    "clear_domain_cache"
]