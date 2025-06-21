"""
GATF Domain Router

This module handles intelligent routing of validation requests to appropriate
domain-specific validators based on agent configuration and data characteristics.
"""

import re
from typing import Dict, List, Optional, Any, Tuple, Type, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
import importlib
import inspect

from ..utils.logging import get_logger
from ..utils.caching import cached, get_cache_manager


logger = get_logger(__name__)


class Domain(Enum):
    """Supported validation domains"""
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    LEGAL = "legal"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    CYBERSECURITY = "cybersecurity"
    HR = "hr"
    RESEARCH = "research"
    DEVOPS = "devops"
    CUSTOM = "custom"


@dataclass
class DomainSignature:
    """Characteristics that identify a domain"""
    keywords: Set[str] = field(default_factory=set)
    data_patterns: List[str] = field(default_factory=list)  # Regex patterns
    required_fields: Set[str] = field(default_factory=set)
    model_types: Set[str] = field(default_factory=set)
    confidence_threshold: float = 0.7


@dataclass
class DomainMatch:
    """Result of domain matching"""
    domain: Domain
    confidence: float
    matched_features: Dict[str, List[str]]
    
    @property
    def is_confident(self) -> bool:
        """Check if match meets confidence threshold"""
        return self.confidence >= 0.7


class DomainRouter:
    """Routes requests to appropriate domain validators"""
    
    def __init__(self):
        """Initialize domain router with signatures"""
        self._signatures = self._initialize_signatures()
        self._validators: Dict[Domain, Any] = {}
        self._custom_domains: Dict[str, Any] = {}
        self._load_validators()
    
    def _initialize_signatures(self) -> Dict[Domain, DomainSignature]:
        """Initialize domain signatures for detection"""
        return {
            Domain.FINANCE: DomainSignature(
                keywords={
                    "trading", "portfolio", "risk", "fraud", "transaction",
                    "investment", "banking", "credit", "loan", "payment",
                    "stock", "bond", "derivative", "compliance", "aml",
                    "kyc", "financial", "accounting", "audit", "tax"
                },
                data_patterns=[
                    r"\b\d{3,4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3,4}\b",  # Credit card
                    r"\b[A-Z]{3}\s?\d+\.\d{2}\b",  # Currency amounts
                    r"\bIBAN\s?[A-Z]{2}\d{2}[A-Z0-9]+\b",  # IBAN
                    r"\bSWIFT\s?[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?\b"  # SWIFT
                ],
                required_fields={
                    "amount", "currency", "transaction_id", "account"
                },
                model_types={
                    "fraud_detection", "risk_assessment", "trading_strategy",
                    "credit_scoring", "portfolio_optimization"
                }
            ),
            
            Domain.HEALTHCARE: DomainSignature(
                keywords={
                    "patient", "diagnosis", "treatment", "medical", "clinical",
                    "prescription", "symptom", "disease", "healthcare", "hospital",
                    "doctor", "nurse", "medication", "therapy", "surgery",
                    "radiology", "pathology", "genomics", "ehr", "hipaa"
                },
                data_patterns=[
                    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN (for HIPAA)
                    r"\bICD[-\s]?10[-\s]?[A-Z]\d{2}(\.\d{1,2})?\b",  # ICD-10 codes
                    r"\bCPT[-\s]?\d{5}\b",  # CPT codes
                    r"\bNPI[-\s]?\d{10}\b"  # NPI numbers
                ],
                required_fields={
                    "patient_id", "diagnosis", "treatment", "provider"
                },
                model_types={
                    "diagnosis_assistant", "treatment_recommendation",
                    "risk_prediction", "clinical_decision_support"
                }
            ),
            
            Domain.LEGAL: DomainSignature(
                keywords={
                    "contract", "law", "legal", "court", "litigation",
                    "compliance", "regulation", "statute", "clause", "agreement",
                    "intellectual property", "patent", "trademark", "copyright",
                    "attorney", "counsel", "jurisdiction", "precedent"
                },
                data_patterns=[
                    r"\b\d{4}\s[A-Z]{2}\s\d+\b",  # Case citations
                    r"\bSection\s\d+(\.\d+)*\b",  # Legal sections
                    r"\b[A-Z][a-z]+\sv\.\s[A-Z][a-z]+\b",  # Case names
                    r"\bU\.S\.C\.\s§\s\d+\b"  # US Code citations
                ],
                required_fields={
                    "document_type", "parties", "jurisdiction", "date"
                },
                model_types={
                    "contract_analysis", "legal_research", "compliance_check",
                    "case_prediction", "document_review"
                }
            ),
            
            Domain.MANUFACTURING: DomainSignature(
                keywords={
                    "production", "manufacturing", "quality", "assembly",
                    "inventory", "supply chain", "maintenance", "equipment",
                    "defect", "inspection", "process", "automation", "robot",
                    "sensor", "iot", "scada", "plc", "mes", "erp"
                },
                data_patterns=[
                    r"\bSN[-\s]?[A-Z0-9]{8,}\b",  # Serial numbers
                    r"\bLOT[-\s]?[A-Z0-9]+\b",  # Lot numbers
                    r"\bISO[-\s]?\d{4,5}\b",  # ISO standards
                    r"\b\d+[-\s]?PPM\b"  # Parts per million
                ],
                required_fields={
                    "product_id", "batch_id", "timestamp", "metrics"
                },
                model_types={
                    "quality_prediction", "predictive_maintenance",
                    "process_optimization", "defect_detection"
                }
            ),
            
            Domain.RETAIL: DomainSignature(
                keywords={
                    "customer", "product", "sales", "inventory", "pricing",
                    "recommendation", "cart", "checkout", "order", "shipping",
                    "retail", "ecommerce", "marketing", "promotion", "loyalty",
                    "sku", "barcode", "pos", "crm", "personalization"
                },
                data_patterns=[
                    r"\bSKU[-\s]?[A-Z0-9]+\b",  # SKU codes
                    r"\bUPC[-\s]?\d{12}\b",  # UPC codes
                    r"\bEAN[-\s]?\d{13}\b",  # EAN codes
                    r"\$\d+\.\d{2}\b"  # Price patterns
                ],
                required_fields={
                    "product_id", "customer_id", "price", "quantity"
                },
                model_types={
                    "recommendation_engine", "demand_forecasting",
                    "price_optimization", "customer_segmentation"
                }
            ),
            
            Domain.CYBERSECURITY: DomainSignature(
                keywords={
                    "threat", "vulnerability", "exploit", "malware", "attack",
                    "security", "firewall", "intrusion", "detection", "response",
                    "encryption", "authentication", "authorization", "audit",
                    "siem", "soc", "incident", "forensics", "penetration"
                },
                data_patterns=[
                    r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",  # IP addresses
                    r"\b[A-Fa-f0-9]{32,64}\b",  # Hash values
                    r"\bCVE[-\s]?\d{4}[-\s]?\d{4,}\b",  # CVE IDs
                    r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b"  # MAC addresses
                ],
                required_fields={
                    "event_type", "source", "target", "timestamp"
                },
                model_types={
                    "threat_detection", "anomaly_detection", "incident_response",
                    "vulnerability_assessment", "behavior_analysis"
                }
            ),
            
            Domain.HR: DomainSignature(
                keywords={
                    "employee", "recruitment", "hiring", "performance", "review",
                    "compensation", "benefits", "training", "development", "hr",
                    "human resources", "talent", "workforce", "attendance",
                    "payroll", "onboarding", "retention", "engagement"
                },
                data_patterns=[
                    r"\bEMP[-\s]?\d{4,}\b",  # Employee IDs
                    r"\b\d{2}/\d{2}/\d{4}\b",  # Date patterns
                    r"\b[A-Z]{2,3}[-\s]?\d{2,4}\b",  # Department codes
                ],
                required_fields={
                    "employee_id", "department", "role", "date"
                },
                model_types={
                    "recruitment_screening", "performance_prediction",
                    "retention_analysis", "skill_matching"
                }
            ),
            
            Domain.RESEARCH: DomainSignature(
                keywords={
                    "research", "study", "experiment", "hypothesis", "analysis",
                    "data", "methodology", "results", "conclusion", "paper",
                    "journal", "citation", "peer review", "academic", "scientific",
                    "statistics", "correlation", "significance", "publication"
                },
                data_patterns=[
                    r"\bDOI[-\s]?10\.\d{4,}/[-._;()/:\w]+\b",  # DOI
                    r"\bPMID[-\s]?\d{7,}\b",  # PubMed IDs
                    r"\barXiv[-\s]?\d{4}\.\d{4,}\b",  # arXiv IDs
                    r"\bp\s?[<>]\s?0\.\d{2,3}\b"  # p-values
                ],
                required_fields={
                    "title", "authors", "abstract", "methodology"
                },
                model_types={
                    "literature_review", "data_analysis", "hypothesis_testing",
                    "citation_analysis", "research_synthesis"
                }
            ),
            
            Domain.DEVOPS: DomainSignature(
                keywords={
                    "deployment", "pipeline", "container", "kubernetes", "docker",
                    "monitoring", "logging", "metrics", "alert", "incident",
                    "infrastructure", "automation", "cicd", "devops", "sre",
                    "microservice", "api", "performance", "scalability"
                },
                data_patterns=[
                    r"\b[a-f0-9]{12}\b",  # Container IDs
                    r"\bv?\d+\.\d+\.\d+\b",  # Version numbers
                    r"\b[A-Z][A-Z0-9_]+=[^\s]+\b",  # Environment variables
                    r"\b\d+\.\d+\.\d+\.\d+:\d+\b"  # IP:Port
                ],
                required_fields={
                    "service", "environment", "timestamp", "status"
                },
                model_types={
                    "anomaly_detection", "root_cause_analysis",
                    "performance_optimization", "incident_prediction"
                }
            )
        }
    
    def _load_validators(self):
        """Dynamically load domain validators"""
        domains_path = Path(__file__).parent.parent / "domains"
        
        for domain in Domain:
            if domain == Domain.CUSTOM:
                continue
                
            domain_path = domains_path / domain.value
            if domain_path.exists():
                try:
                    # Import the domain module
                    module_path = f"gatf.domains.{domain.value}"
                    module = importlib.import_module(module_path)
                    
                    # Look for validator class
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            name.endswith("Validator") and
                            obj.__module__ == module_path):
                            self._validators[domain] = obj
                            logger.info(f"Loaded validator for {domain.value}: {name}")
                            break
                            
                except Exception as e:
                    logger.warning(f"Failed to load validator for {domain.value}: {e}")
    
    def detect_domain(
        self,
        agent_config: Dict[str, Any],
        sample_data: Optional[Any] = None
    ) -> List[DomainMatch]:
        """
        Detect the most likely domain(s) for an agent
        
        Args:
            agent_config: Agent configuration
            sample_data: Optional sample data for analysis
        
        Returns:
            List of domain matches sorted by confidence
        """
        matches = []
        
        for domain, signature in self._signatures.items():
            confidence = 0.0
            matched_features = {
                "keywords": [],
                "patterns": [],
                "fields": [],
                "model_types": []
            }
            
            # Check keywords in agent config
            config_text = str(agent_config).lower()
            matched_keywords = [kw for kw in signature.keywords if kw in config_text]
            if matched_keywords:
                confidence += len(matched_keywords) / len(signature.keywords) * 0.4
                matched_features["keywords"] = matched_keywords
            
            # Check model type
            model_type = agent_config.get("model_type", "").lower()
            if model_type in signature.model_types:
                confidence += 0.3
                matched_features["model_types"] = [model_type]
            
            # Check data patterns if sample data provided
            if sample_data:
                sample_text = str(sample_data)
                for pattern in signature.data_patterns:
                    if re.search(pattern, sample_text, re.IGNORECASE):
                        matched_features["patterns"].append(pattern)
                
                if matched_features["patterns"]:
                    confidence += len(matched_features["patterns"]) / len(signature.data_patterns) * 0.2
            
            # Check required fields
            if isinstance(sample_data, dict):
                matched_fields = signature.required_fields.intersection(sample_data.keys())
                if matched_fields:
                    confidence += len(matched_fields) / len(signature.required_fields) * 0.1
                    matched_features["fields"] = list(matched_fields)
            
            if confidence > 0:
                matches.append(DomainMatch(
                    domain=domain,
                    confidence=confidence,
                    matched_features=matched_features
                ))
        
        # Sort by confidence
        matches.sort(key=lambda x: x.confidence, reverse=True)
        
        return matches
    
    @cached(ttl=3600)
    def get_validator(self, domain: Union[Domain, str]) -> Optional[Any]:
        """
        Get validator instance for a domain
        
        Args:
            domain: Domain enum or string
        
        Returns:
            Validator instance or None
        """
        if isinstance(domain, str):
            if domain in self._custom_domains:
                return self._custom_domains[domain]
            
            try:
                domain = Domain(domain)
            except ValueError:
                logger.warning(f"Unknown domain: {domain}")
                return None
        
        return self._validators.get(domain)
    
    def route_request(
        self,
        agent_config: Dict[str, Any],
        validation_request: Dict[str, Any]
    ) -> Tuple[Optional[Any], Domain]:
        """
        Route validation request to appropriate validator
        
        Args:
            agent_config: Agent configuration
            validation_request: Validation request details
        
        Returns:
            Tuple of (validator_instance, detected_domain)
        """
        # Check if domain is explicitly specified
        specified_domain = agent_config.get("domain") or validation_request.get("domain")
        
        if specified_domain:
            validator = self.get_validator(specified_domain)
            if validator:
                return validator, Domain(specified_domain)
        
        # Auto-detect domain
        sample_data = validation_request.get("sample_data")
        matches = self.detect_domain(agent_config, sample_data)
        
        if matches and matches[0].is_confident:
            domain = matches[0].domain
            validator = self.get_validator(domain)
            
            if validator:
                logger.info(
                    f"Routed to {domain.value} validator "
                    f"(confidence: {matches[0].confidence:.2f})"
                )
                return validator, domain
        
        # Default to generic validation if no specific domain detected
        logger.warning("No specific domain detected, using generic validation")
        return None, Domain.CUSTOM
    
    def register_custom_domain(
        self,
        name: str,
        validator_class: Type,
        signature: Optional[DomainSignature] = None
    ):
        """
        Register a custom domain validator
        
        Args:
            name: Domain name
            validator_class: Validator class
            signature: Optional domain signature for auto-detection
        """
        self._custom_domains[name] = validator_class
        
        if signature:
            # Create a custom domain enum value dynamically
            custom_domain = Domain.CUSTOM
            self._signatures[name] = signature
            
        logger.info(f"Registered custom domain: {name}")
    
    def get_supported_domains(self) -> List[str]:
        """Get list of supported domains"""
        domains = [d.value for d in Domain if d != Domain.CUSTOM]
        domains.extend(self._custom_domains.keys())
        return domains
    
    def get_domain_info(self, domain: Union[Domain, str]) -> Dict[str, Any]:
        """
        Get information about a domain
        
        Args:
            domain: Domain to get info for
        
        Returns:
            Domain information dictionary
        """
        if isinstance(domain, str):
            if domain not in self._custom_domains:
                try:
                    domain = Domain(domain)
                except ValueError:
                    return {"error": f"Unknown domain: {domain}"}
        
        signature = self._signatures.get(domain, DomainSignature())
        validator = self.get_validator(domain)
        
        return {
            "name": domain.value if isinstance(domain, Domain) else domain,
            "validator_available": validator is not None,
            "signature": {
                "keywords": list(signature.keywords),
                "required_fields": list(signature.required_fields),
                "model_types": list(signature.model_types),
                "pattern_count": len(signature.data_patterns)
            }
        }


# Global domain router instance
_domain_router: Optional[DomainRouter] = None


def get_domain_router() -> DomainRouter:
    """Get or create global domain router"""
    global _domain_router
    if _domain_router is None:
        _domain_router = DomainRouter()
    return _domain_router