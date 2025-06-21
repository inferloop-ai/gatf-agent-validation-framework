#!/bin/bash

# GATF to VOS Migration Script
# Migrates existing GATF repository structure to VOS-enhanced structure
# Version: 1.0.0
# Author: GATF-VOS Migration Team

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(pwd)"
BACKUP_DIR="${REPO_ROOT}/gatf_backup_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${REPO_ROOT}/vos_migration.log"
DRY_RUN=false
FORCE_MIGRATION=false
ROLLBACK_DIR=""

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

print_section() {
    echo -e "${BLUE}[SECTION]${NC} $1" | tee -a "$LOG_FILE"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

print_migration() {
    echo -e "${PURPLE}[MIGRATE]${NC} $1" | tee -a "$LOG_FILE"
}

print_create() {
    echo -e "${CYAN}[CREATE]${NC} $1" | tee -a "$LOG_FILE"
}

# Help function
show_help() {
    cat << EOF
GATF to VOS Migration Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -d, --dry-run          Show what would be done without making changes
    -f, --force            Force migration even if VOS structure already exists
    -r, --rollback DIR     Rollback to previous backup directory
    -v, --verbose          Enable verbose output
    --backup-dir DIR       Specify custom backup directory

EXAMPLES:
    $0                     # Standard migration
    $0 --dry-run          # Preview changes
    $0 --force            # Force migration
    $0 --rollback /path/to/backup  # Rollback migration

DESCRIPTION:
    This script migrates an existing GATF repository structure to the new
    VOS-enhanced structure. It safely backs up existing files, creates new
    VOS directories, moves existing components to appropriate locations,
    and creates placeholder files for new VOS components.

MIGRATION PROCESS:
    1. Validate current repository structure
    2. Create backup of existing structure
    3. Create new VOS directory structure
    4. Migrate existing files to new locations
    5. Create placeholder files for new components
    6. Update configuration files
    7. Generate migration report

SAFETY FEATURES:
    - Full backup before migration
    - Dry-run mode for preview
    - Rollback capability
    - Comprehensive logging
    - Validation checks

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--dry-run)
                DRY_RUN=true
                print_warning "DRY RUN MODE: No changes will be made"
                shift
                ;;
            -f|--force)
                FORCE_MIGRATION=true
                print_warning "FORCE MODE: Will overwrite existing VOS structure"
                shift
                ;;
            -r|--rollback)
                ROLLBACK_DIR="$2"
                shift 2
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            --backup-dir)
                BACKUP_DIR="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Validation functions
validate_environment() {
    print_section "Validating Environment"
    
    # Check if we're in a Git repository
    if [[ ! -d ".git" ]]; then
        print_error "Not in a Git repository. Please run from repository root."
        exit 1
    fi
    
    # Check if this looks like a GATF repository
    if [[ ! -f "setup.py" ]] && [[ ! -f "pyproject.toml" ]]; then
        print_error "No setup.py or pyproject.toml found. Is this a GATF repository?"
        exit 1
    fi
    
    # Check for existing VOS structure
    if [[ -d "src/gatf_vos" ]] && [[ "$FORCE_MIGRATION" == false ]]; then
        print_error "VOS structure already exists. Use --force to overwrite."
        exit 1
    fi
    
    # Check Git working directory status
    if [[ -n "$(git status --porcelain)" ]]; then
        print_warning "Working directory has uncommitted changes."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Migration cancelled by user"
            exit 1
        fi
    fi
    
    print_success "Environment validation passed"
}

# Backup functions
create_backup() {
    if [[ "$DRY_RUN" == true ]]; then
        print_migration "Would create backup at: $BACKUP_DIR"
        return
    fi
    
    print_section "Creating Backup"
    print_status "Backup location: $BACKUP_DIR"
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Copy current structure to backup
    rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
          --exclude='.pytest_cache' --exclude='node_modules' \
          "$REPO_ROOT/" "$BACKUP_DIR/" > /dev/null
    
    # Save Git state
    git rev-parse HEAD > "$BACKUP_DIR/git_commit.txt"
    git status --porcelain > "$BACKUP_DIR/git_status.txt"
    
    print_success "Backup created successfully"
}

# Rollback function
rollback_migration() {
    if [[ ! -d "$ROLLBACK_DIR" ]]; then
        print_error "Rollback directory does not exist: $ROLLBACK_DIR"
        exit 1
    fi
    
    print_section "Rolling Back Migration"
    print_warning "This will restore the repository to the backed-up state"
    
    read -p "Are you sure you want to rollback? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Rollback cancelled by user"
        exit 1
    fi
    
    # Remove current files (except .git)
    find . -maxdepth 1 -not -name '.git' -not -name '.' -exec rm -rf {} \; 2>/dev/null || true
    
    # Restore from backup
    rsync -av --exclude='.git' "$ROLLBACK_DIR/" "$REPO_ROOT/"
    
    print_success "Rollback completed successfully"
    exit 0
}

# Directory creation functions
create_vos_directory_structure() {
    print_section "Creating VOS Directory Structure"
    
    # Define all new VOS directories
    local vos_dirs=(
        "src/gatf_vos"
        "src/gatf_vos/core"
        "src/gatf_vos/runtime"
        "src/gatf_vos/runtime/detection"
        "src/gatf_vos/runtime/correction"
        "src/gatf_vos/runtime/uncertainty"
        "src/gatf_vos/runtime/coordination"
        "src/gatf_vos/validation/handoff"
        "src/gatf_vos/validation/workflow"
        "src/gatf_vos/validation/memory"
        "src/gatf_vos/trust"
        "src/gatf_vos/hitl"
        "src/gatf_vos/learning"
        "src/gatf_vos/benchmarking"
        "src/gatf_vos/synthetic_data/platform_adapters"
        "src/gatf_vos/synthetic_data/generators"
        "src/gatf_vos/synthetic_data/scenarios"
        "src/gatf_vos/synthetic_data/validation"
        "src/gatf_vos/vaas"
        "src/gatf_vos/compliance"
        "src/gatf_vos/infrastructure/security"
        "src/gatf_vos/infrastructure/monitoring"
        "src/gatf_vos/infrastructure/data"
        "src/gatf_vos/infrastructure/deployment"
        "src/gatf_vos/cli/commands"
        "src/gatf_vos/cli/sdk"
        "src/gatf_vos/cli/integrations"
        "tests/multi_agent"
        "tests/performance"
        "tests/e2e"
        "tests/benchmarks"
        "configs/vos"
        "configs/synthetic_data"
        "configs/infrastructure"
        "docs/vos"
        "docs/tutorials"
        "docs/benchmarks"
        "examples/vos_examples"
        "examples/domain_examples"
        "examples/integration_examples"
        "scripts/deployment"
        "scripts/migration"
        "scripts/maintenance"
        "deployments/docker"
        "deployments/kubernetes"
        "deployments/cloud/aws"
        "deployments/cloud/azure"
        "deployments/cloud/gcp"
        "deployments/cloud/multi-cloud"
        "deployments/on-premise/bare-metal"
        "deployments/on-premise/vmware"
        "deployments/on-premise/openstack"
        "requirements"
        "tools"
    )
    
    # Create directories
    for dir in "${vos_dirs[@]}"; do
        if [[ "$DRY_RUN" == true ]]; then
            print_create "Would create directory: $dir"
        else
            mkdir -p "$dir"
            print_create "Created directory: $dir"
        fi
    done
}

# File migration functions
migrate_existing_files() {
    print_section "Migrating Existing Files"
    
    # Define migration mappings (old_path -> new_path)
    declare -A migration_map=(
        # Core framework files
        ["src/gatf/core/trust_framework.py"]="src/gatf_vos/core/trust_framework.py"
        ["src/gatf/core/validation_pipeline.py"]="src/gatf_vos/core/validation_pipeline.py"
        ["src/gatf/core/meta_orchestrator.py"]="src/gatf_vos/core/meta_orchestrator.py"
        ["src/gatf/core/domain_router.py"]="src/gatf_vos/core/domain_router.py"
        ["src/gatf/core/config.py"]="src/gatf_vos/core/config.py"
        ["src/gatf/core/exceptions.py"]="src/gatf_vos/core/exceptions.py"
        ["src/gatf/core/logging.py"]="src/gatf_vos/core/logging.py"
        
        # Validation engines
        ["src/gatf/validation/engines/quality_validator.py"]="src/gatf_vos/validation/engines/quality_validator.py"
        ["src/gatf/validation/engines/bias_validator.py"]="src/gatf_vos/validation/engines/bias_validator.py"
        ["src/gatf/validation/engines/security_validator.py"]="src/gatf_vos/validation/engines/security_validator.py"
        ["src/gatf/validation/engines/compliance_validator.py"]="src/gatf_vos/validation/engines/compliance_validator.py"
        ["src/gatf/validation/engines/fairness_validator.py"]="src/gatf_vos/validation/engines/fairness_validator.py"
        ["src/gatf/validation/engines/hallucination_validator.py"]="src/gatf_vos/validation/engines/hallucination_validator.py"
        
        # Trust scoring
        ["src/gatf/trust/calculator.py"]="src/gatf_vos/trust/trust_calculator.py"
        ["src/gatf/trust/scorecard_generator.py"]="src/gatf_vos/trust/scorecard_generator.py"
        ["src/gatf/trust/badge_assigner.py"]="src/gatf_vos/trust/badge_assigner.py"
        
        # VaaS components
        ["src/gatf/vaas/api_service.py"]="src/gatf_vos/vaas/vos_api_service.py"
        ["src/gatf/vaas/real_time_validator.py"]="src/gatf_vos/vaas/real_time_validator.py"
        ["src/gatf/vaas/monitoring_service.py"]="src/gatf_vos/vaas/monitoring_service.py"
        
        # Compliance
        ["src/gatf/compliance/gdpr_validator.py"]="src/gatf_vos/compliance/gdpr_validator.py"
        ["src/gatf/compliance/hipaa_validator.py"]="src/gatf_vos/compliance/hipaa_validator.py"
        ["src/gatf/compliance/privacy_auditor.py"]="src/gatf_vos/compliance/privacy_auditor.py"
        
        # Domain modules
        ["src/gatf/domains/finance/"]="src/gatf_vos/domains/finance/"
        ["src/gatf/domains/healthcare/"]="src/gatf_vos/domains/healthcare/"
        ["src/gatf/domains/automotive/"]="src/gatf_vos/domains/automotive/"
        ["src/gatf/domains/legal/"]="src/gatf_vos/domains/legal/"
        ["src/gatf/domains/retail/"]="src/gatf_vos/domains/retail/"
        ["src/gatf/domains/manufacturing/"]="src/gatf_vos/domains/manufacturing/"
        ["src/gatf/domains/energy/"]="src/gatf_vos/domains/energy/"
        
        # Configuration files
        ["configs/validation_policies/"]="configs/validation_policies/"
        ["configs/trust_scoring/"]="configs/trust_scoring/"
        ["configs/compliance_rules/"]="configs/compliance_rules/"
        
        # Documentation
        ["docs/api/"]="docs/api/"
        ["docs/integration/"]="docs/integration/"
        ["docs/compliance/"]="docs/compliance/"
        
        # Tests
        ["tests/unit/"]="tests/unit/"
        ["tests/integration/"]="tests/integration/"
        ["tests/security/"]="tests/security/"
    )
    
    # Perform migrations
    for old_path in "${!migration_map[@]}"; do
        new_path="${migration_map[$old_path]}"
        
        if [[ -e "$old_path" ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                print_migration "Would migrate: $old_path -> $new_path"
            else
                # Create target directory if it doesn't exist
                mkdir -p "$(dirname "$new_path")"
                
                # Move file or directory
                if [[ -d "$old_path" ]]; then
                    rsync -av "$old_path" "$(dirname "$new_path")/" > /dev/null
                    rm -rf "$old_path"
                else
                    mv "$old_path" "$new_path"
                fi
                
                print_migration "Migrated: $old_path -> $new_path"
            fi
        else
            print_warning "Source not found: $old_path"
        fi
    done
}

# Create new VOS placeholder files
create_vos_placeholder_files() {
    print_section "Creating VOS Placeholder Files"
    
    # Define new VOS files to create
    local vos_files=(
        "src/gatf_vos/__init__.py"
        "src/gatf_vos/vos_primitives.py"
        "src/gatf_vos/core/vos_orchestrator.py"
        "src/gatf_vos/core/event_coordinator.py"
        "src/gatf_vos/core/memory_orchestrator.py"
        "src/gatf_vos/core/agent_lifecycle_manager.py"
        "src/gatf_vos/runtime/runtime_monitor.py"
        "src/gatf_vos/runtime/detection/hallucination_detector.py"
        "src/gatf_vos/runtime/detection/intent_drift_detector.py"
        "src/gatf_vos/runtime/detection/memory_drift_detector.py"
        "src/gatf_vos/runtime/correction/correction_engine.py"
        "src/gatf_vos/runtime/correction/rag_corrector.py"
        "src/gatf_vos/runtime/uncertainty/uncertainty_quantifier.py"
        "src/gatf_vos/runtime/coordination/ovon_protocol.py"
        "src/gatf_vos/validation/handoff/handoff_validator.py"
        "src/gatf_vos/validation/workflow/workflow_coherence_validator.py"
        "src/gatf_vos/validation/memory/memory_validator.py"
        "src/gatf_vos/hitl/hitl_gateway.py"
        "src/gatf_vos/learning/real_time_learner.py"
        "src/gatf_vos/benchmarking/vos_benchmarks.py"
        "src/gatf_vos/cli/vos_cli.py"
        "vos-config.yaml"
        "VOS-ARCHITECTURE.md"
        "MULTI-AGENT-GUIDE.md"
    )
    
    # Create placeholder files with basic content
    for file in "${vos_files[@]}"; do
        if [[ "$DRY_RUN" == true ]]; then
            print_create "Would create file: $file"
        else
            # Create directory if it doesn't exist
            mkdir -p "$(dirname "$file")"
            
            # Create file with basic content
            case "$file" in
                *.py)
                    cat > "$file" << EOF
"""
VOS Component: $(basename "$file" .py)
Generated by GATF to VOS migration script

TODO: Implement VOS functionality
"""

# VOS imports
from typing import Any, Dict, List, Optional

# TODO: Add VOS implementation

class $(basename "$file" .py | sed 's/_/ /g' | sed 's/\b\w/\U&/g' | sed 's/ //g'):
    """VOS component implementation placeholder"""
    
    def __init__(self):
        # TODO: Initialize VOS component
        pass
    
    def process(self, *args, **kwargs) -> Any:
        """Main processing method"""
        # TODO: Implement VOS logic
        raise NotImplementedError("VOS implementation pending")
EOF
                    ;;
                *.yaml|*.yml)
                    cat > "$file" << EOF
# VOS Configuration File
# Generated by GATF to VOS migration script

version: "1.0.0"
vos:
  enabled: true
  # TODO: Add VOS configuration
EOF
                    ;;
                *.md)
                    cat > "$file" << EOF
# VOS Documentation

Generated by GATF to VOS migration script

## Overview

TODO: Add VOS documentation

## Features

TODO: List VOS features

## Usage

TODO: Add usage examples
EOF
                    ;;
            esac
            
            print_create "Created file: $file"
        fi
    done
}

# Update configuration files
update_configuration_files() {
    print_section "Updating Configuration Files"
    
    # Update setup.py or pyproject.toml
    if [[ -f "setup.py" ]] && [[ "$DRY_RUN" == false ]]; then
        # Backup original
        cp setup.py setup.py.bak
        
        # Update package name and structure
        sed -i 's/gatf/gatf_vos/g' setup.py
        sed -i 's/name="gatf"/name="gatf_vos"/g' setup.py
        
        print_status "Updated setup.py"
    fi
    
    if [[ -f "pyproject.toml" ]] && [[ "$DRY_RUN" == false ]]; then
        # Backup original
        cp pyproject.toml pyproject.toml.bak
        
        # Update package configuration
        sed -i 's/name = "gatf"/name = "gatf_vos"/g' pyproject.toml
        
        print_status "Updated pyproject.toml"
    fi
    
    # Update requirements files
    if [[ -f "requirements.txt" ]] && [[ "$DRY_RUN" == false ]]; then
        # Add VOS-specific requirements
        cat >> requirements.txt << EOF

# VOS-specific requirements
kafka-python>=2.0.0
nats-py>=2.0.0
redis>=4.0.0
prometheus-client>=0.15.0
grafana-api>=1.0.0
kubernetes>=24.0.0
pytest-xdist>=3.0.0
pytest-benchmark>=4.0.0
memory-profiler>=0.60.0
EOF
        
        print_status "Updated requirements.txt with VOS dependencies"
    fi
    
    # Update README.md
    if [[ -f "README.md" ]] && [[ "$DRY_RUN" == false ]]; then
        # Backup original
        cp README.md README.md.bak
        
        # Add VOS information
        cat > README_vos_update.md << EOF
# GATF-VOS: Enhanced Validation Operating System

**Migrated from GATF to VOS on $(date)**

## Overview

This repository has been migrated from the original GATF (General Agent Testing Framework) to the enhanced VOS (Validation Operating System) architecture.

## VOS Enhancements

- 🚀 Multi-agent coordination and validation
- 🧠 Memory drift detection and management
- ⚡ Real-time monitoring and correction
- 🤝 Human-in-the-loop integration
- 📊 Continuous learning and adaptation
- 🛡️ Zero-trust security architecture
- 🌐 Enterprise deployment support

## Migration Information

- **Migration Date**: $(date)
- **Backup Location**: $BACKUP_DIR
- **Migration Log**: $LOG_FILE

## Quick Start

\`\`\`bash
# Install VOS dependencies
pip install -r requirements.txt

# Initialize VOS
python -m gatf_vos.cli.vos_cli init

# Run VOS validation
python -m gatf_vos.cli.vos_cli validate --agent-id example
\`\`\`

---

$(cat README.md)
EOF
        
        mv README_vos_update.md README.md
        print_status "Updated README.md with VOS information"
    fi
}

# Generate migration report
generate_migration_report() {
    print_section "Generating Migration Report"
    
    local report_file="VOS_MIGRATION_REPORT.md"
    
    if [[ "$DRY_RUN" == true ]]; then
        print_status "Would generate migration report: $report_file"
        return
    fi
    
    cat > "$report_file" << EOF
# GATF to VOS Migration Report

**Migration Completed**: $(date)
**Migration Script Version**: 1.0.0

## Migration Summary

### Repository Information
- **Repository**: $(git config --get remote.origin.url 2>/dev/null || echo "Local repository")
- **Branch**: $(git branch --show-current 2>/dev/null || echo "Unknown")
- **Commit**: $(git rev-parse HEAD 2>/dev/null || echo "Unknown")

### Backup Information
- **Backup Location**: $BACKUP_DIR
- **Backup Size**: $(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "Unknown")

### Migration Statistics
- **Original Structure**: GATF Framework
- **New Structure**: VOS (Validation Operating System)
- **New Directories Created**: $(find src/gatf_vos -type d | wc -l)
- **New Files Created**: $(find src/gatf_vos -type f | wc -l)
- **Files Migrated**: $(grep "Migrated:" "$LOG_FILE" | wc -l)

### Key Enhancements
1. ✅ Multi-agent coordination system
2. ✅ Runtime monitoring and detection
3. ✅ Real-time correction pipeline
4. ✅ Memory orchestration system
5. ✅ Human-in-the-loop gateway
6. ✅ Continuous learning system
7. ✅ VOS benchmarking framework
8. ✅ Enhanced infrastructure layer

### Next Steps
1. Review migrated files and update imports
2. Implement VOS placeholder components
3. Update configuration files for your environment
4. Run VOS validation tests
5. Deploy using new VOS infrastructure

### Rollback Instructions
If you need to rollback this migration:
\`\`\`bash
./$(basename "$0") --rollback "$BACKUP_DIR"
\`\`\`

### Support
- **Migration Log**: $LOG_FILE
- **Documentation**: docs/vos/
- **Examples**: examples/vos_examples/

## Files Modified

### Configuration Files
- setup.py (backed up to setup.py.bak)
- pyproject.toml (backed up to pyproject.toml.bak)
- README.md (backed up to README.md.bak)
- requirements.txt (enhanced with VOS dependencies)

### New VOS Components
$(find src/gatf_vos -name "*.py" | sort)

### Migrated Files
$(grep "Migrated:" "$LOG_FILE" | sed 's/.*Migrated: /- /')

---
**Migration completed successfully!**
EOF
    
    print_success "Migration report generated: $report_file"
}

# Cleanup function
cleanup_old_structure() {
    print_section "Cleaning Up Old Structure"
    
    # Define old directories to remove (if empty)
    local old_dirs=(
        "src/gatf/core"
        "src/gatf/validation/engines"
        "src/gatf/validation/metrics"
        "src/gatf/validation/orchestrators"
        "src/gatf/trust"
        "src/gatf/vaas"
        "src/gatf/compliance"
        "src/gatf/domains"
        "src/gatf"
    )
    
    for dir in "${old_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                print_status "Would check for cleanup: $dir"
            else
                # Remove directory if empty
                if [[ -z "$(ls -A "$dir" 2>/dev/null)" ]]; then
                    rmdir "$dir" 2>/dev/null || true
                    print_status "Removed empty directory: $dir"
                else
                    print_warning "Directory not empty, keeping: $dir"
                fi
            fi
        fi
    done
}

# Post-migration validation
validate_migration() {
    print_section "Validating Migration"
    
    # Check that VOS structure exists
    if [[ ! -d "src/gatf_vos" ]] && [[ "$DRY_RUN" == false ]]; then
        print_error "VOS structure not created properly"
        return 1
    fi
    
    # Check for key VOS files
    local key_files=(
        "src/gatf_vos/__init__.py"
        "src/gatf_vos/vos_primitives.py"
        "src/gatf_vos/core/vos_orchestrator.py"
        "vos-config.yaml"
        "VOS-ARCHITECTURE.md"
    )
    
    for file in "${key_files[@]}"; do
        if [[ ! -f "$file" ]] && [[ "$DRY_RUN" == false ]]; then
            print_error "Key VOS file missing: $file"
            return 1
        elif [[ "$DRY_RUN" == true ]]; then
            print_status "Would validate: $file"
        else
            print_status "Validated: $file"
        fi
    done
    
    print_success "Migration validation passed"
}

# Main migration function
run_migration() {
    print_section "Starting GATF to VOS Migration"
    print_status "Repository: $REPO_ROOT"
    print_status "Backup: $BACKUP_DIR"
    print_status "Log: $LOG_FILE"
    
    # Validation
    validate_environment
    
    # Create backup
    create_backup
    
    # Create VOS structure
    create_vos_directory_structure
    
    # Migrate existing files
    migrate_existing_files
    
    # Create new VOS files
    create_vos_placeholder_files
    
    # Update configuration
    update_configuration_files
    
    # Cleanup old structure
    cleanup_old_structure
    
    # Validate migration
    validate_migration
    
    # Generate report
    generate_migration_report
    
    print_success "Migration completed successfully!"
    
    if [[ "$DRY_RUN" == false ]]; then
        print_status "Next steps:"
        print_status "1. Review the migration report: VOS_MIGRATION_REPORT.md"
        print_status "2. Update imports in migrated files"
        print_status "3. Implement VOS placeholder components"
        print_status "4. Test the new VOS structure"
        print_status "5. Commit changes to Git"
    fi
}

# Main execution
main() {
    # Initialize log file
    echo "GATF to VOS Migration Log - $(date)" > "$LOG_FILE"
    
    # Parse arguments
    parse_args "$@"
    
    # Handle rollback
    if [[ -n "$ROLLBACK_DIR" ]]; then
        rollback_migration
        return
    fi
    
    # Run migration
    run_migration
}

# Trap for cleanup on exit
trap 'print_status "Migration script finished"' EXIT

# Execute main function
main "$@"