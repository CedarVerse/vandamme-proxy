# ============================================================================
# Claude Code Proxy - Makefile
# ============================================================================
# Modern, elegant build system for Python FastAPI proxy server
# ============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

.PHONY: help install install-dev clean test test-unit test-integration \
        format lint type-check check build run dev docker-build docker-up \
        docker-down docker-logs health ci coverage pre-commit all watch \
        deps-check security-check validate quick-check

# ============================================================================
# Configuration
# ============================================================================

PYTHON := python3
UV := uv
PYTEST := pytest
BLACK := black
ISORT := isort
MYPY := mypy

SRC_DIR := src
TEST_DIR := tests
PYTHON_FILES := $(SRC_DIR) $(TEST_DIR) start_proxy.py test_cancellation.py

HOST ?= 0.0.0.0
PORT ?= 8082
LOG_LEVEL ?= INFO

# Auto-detect available tools
HAS_UV := $(shell command -v uv 2> /dev/null)
HAS_DOCKER := $(shell command -v docker 2> /dev/null)
HAS_GUM := $(shell command -v gum 2> /dev/null)

# Colors for output
BOLD := \033[1m
RESET := \033[0m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
CYAN := \033[36m
RED := \033[31m

# ============================================================================
# Help
# ============================================================================

help: ## Show this help message
	@echo "$(BOLD)$(CYAN)Claude Code Proxy - Makefile Commands$(RESET)"
	@echo ""
	@echo "$(BOLD)Quick Start:$(RESET)"
	@echo "  $(GREEN)make install-dev$(RESET)    - Install all dependencies"
	@echo "  $(GREEN)make dev$(RESET)            - Start development server"
	@echo "  $(GREEN)make validate$(RESET)       - Quick check + tests (fast)"
	@echo ""
	@echo "$(BOLD)Setup & Installation:$(RESET)"
	@grep -E '^(install|deps-check).*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Development:$(RESET)"
	@grep -E '^(run|dev|health|clean|watch):.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Code Quality:$(RESET)"
	@grep -E '^(format|lint|type-check|check|quick-check|security-check|validate|pre-commit):.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Testing:$(RESET)"
	@grep -E '^test.*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@grep -E '^coverage.*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Docker:$(RESET)"
	@grep -E '^docker-.*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)CI/CD:$(RESET)"
	@grep -E '^(ci|build|all):.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Utilities:$(RESET)"
	@grep -E '^(version|info|env-template):.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Setup & Installation
# ============================================================================

install: ## Install production dependencies (UV)
	@echo "$(BOLD)$(GREEN)Installing production dependencies...$(RESET)"
ifndef HAS_UV
	$(error UV is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh)
endif
	$(UV) sync --no-dev

install-dev: ## Install all dependencies including dev tools (UV)
	@echo "$(BOLD)$(GREEN)Installing all dependencies (including dev)...$(RESET)"
ifndef HAS_UV
	$(error UV is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh)
endif
	$(UV) sync

install-pip: ## Install dependencies using pip (fallback)
	@echo "$(BOLD)$(GREEN)Installing dependencies with pip...$(RESET)"
	$(PYTHON) -m pip install -r requirements.txt

deps-check: ## Check for outdated dependencies
	@echo "$(BOLD)$(YELLOW)Checking dependencies...$(RESET)"
ifdef HAS_UV
	@$(UV) pip list --outdated || echo "$(GREEN)✓ All dependencies up to date$(RESET)"
else
	@$(PYTHON) -m pip list --outdated || echo "$(GREEN)✓ All dependencies up to date$(RESET)"
endif

# ============================================================================
# Development
# ============================================================================

run: ## Run the proxy server
	@echo "$(BOLD)$(BLUE)Starting Claude Code Proxy...$(RESET)"
	$(PYTHON) start_proxy.py

dev: install-dev ## Setup dev environment and run server with hot reload
	@echo "$(BOLD)$(BLUE)Starting development server with auto-reload...$(RESET)"
	$(UV) run uvicorn src.main:app --host $(HOST) --port $(PORT) --reload --log-level $(LOG_LEVEL)

health: ## Check proxy server health
	@echo "$(BOLD)$(CYAN)Checking server health...$(RESET)"
	@curl -s http://localhost:$(PORT)/health | $(PYTHON) -m json.tool || echo "$(YELLOW)Server not running on port $(PORT)$(RESET)"

clean: ## Clean temporary files and caches
	@echo "$(BOLD)$(YELLOW)Cleaning temporary files...$(RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@rm -rf build/ dist/ 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned successfully$(RESET)"

# ============================================================================
# Code Quality
# ============================================================================

format: ## Auto-format code with black and isort
	@echo "$(BOLD)$(YELLOW)Formatting code...$(RESET)"
	@$(UV) run $(BLACK) $(PYTHON_FILES)
	@$(UV) run $(ISORT) $(PYTHON_FILES)
	@echo "$(GREEN)✓ Code formatted$(RESET)"

lint: ## Run code linting checks (black, isort - check only)
	@echo "$(BOLD)$(YELLOW)Running linters...$(RESET)"
	@echo "$(CYAN)→ black (check)$(RESET)"
	@$(UV) run $(BLACK) --check $(PYTHON_FILES) || (echo "$(YELLOW)⚠ Run 'make format' to fix formatting$(RESET)" && exit 1)
	@echo "$(CYAN)→ isort (check)$(RESET)"
	@$(UV) run $(ISORT) --check-only $(PYTHON_FILES) || (echo "$(YELLOW)⚠ Run 'make format' to fix imports$(RESET)" && exit 1)
	@echo "$(GREEN)✓ Linting passed$(RESET)"

type-check: ## Run type checking with mypy
	@echo "$(BOLD)$(YELLOW)Running type checker...$(RESET)"
	@$(UV) run $(MYPY) $(SRC_DIR) || (echo "$(YELLOW)⚠ Type checking found issues$(RESET)" && exit 1)
	@echo "$(GREEN)✓ Type checking passed$(RESET)"

check: lint type-check ## Run all code quality checks (lint + type-check)
	@echo "$(BOLD)$(GREEN)✓ All quality checks passed$(RESET)"

quick-check: ## Fast check (format + lint only, skip type-check)
	@echo "$(BOLD)$(YELLOW)Running quick checks (format + lint)...$(RESET)"
	@$(UV) run $(BLACK) --check $(PYTHON_FILES) || (echo "$(YELLOW)⚠ Run 'make format' to fix formatting$(RESET)" && exit 1)
	@$(UV) run $(ISORT) --check-only $(PYTHON_FILES) || (echo "$(YELLOW)⚠ Run 'make format' to fix imports$(RESET)" && exit 1)
	@echo "$(GREEN)✓ Quick checks passed$(RESET)"

security-check: ## Run security vulnerability checks
	@echo "$(BOLD)$(YELLOW)Running security checks...$(RESET)"
	@command -v bandit >/dev/null 2>&1 || { echo "$(YELLOW)Installing bandit...$(RESET)"; $(UV) pip install bandit; }
	@$(UV) run bandit -r $(SRC_DIR) -ll || echo "$(GREEN)✓ No security issues found$(RESET)"

validate: quick-check test-quick ## Fast validation (quick-check + quick tests)
	@echo "$(BOLD)$(GREEN)✓ Validation complete$(RESET)"

pre-commit: format check ## Format code and run all checks (run before commit)
	@echo "$(BOLD)$(GREEN)✓ Pre-commit checks complete$(RESET)"

# ============================================================================
# Testing
# ============================================================================

test: ## Run all tests
	@echo "$(BOLD)$(CYAN)Running all tests...$(RESET)"
	@$(UV) run $(PYTEST) $(TEST_DIR) -v

test-unit: ## Run unit tests only
	@echo "$(BOLD)$(CYAN)Running unit tests...$(RESET)"
	@$(UV) run $(PYTEST) $(TEST_DIR) -v -m "not integration"

test-integration: ## Run integration tests
	@echo "$(BOLD)$(CYAN)Running integration tests...$(RESET)"
	@$(PYTHON) src/test_claude_to_openai.py

test-quick: ## Run tests without coverage (fast)
	@echo "$(BOLD)$(CYAN)Running quick tests...$(RESET)"
	@$(UV) run $(PYTEST) $(TEST_DIR) -q --tb=short

coverage: ## Run tests with coverage report
	@echo "$(BOLD)$(CYAN)Running tests with coverage...$(RESET)"
	@$(UV) run $(PYTEST) $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/$(RESET)"

# ============================================================================
# Docker
# ============================================================================

docker-build: ## Build Docker image
	@echo "$(BOLD)$(BLUE)Building Docker image...$(RESET)"
ifndef HAS_DOCKER
	$(error Docker is not installed or not running)
endif
	docker compose build

docker-up: ## Start services with Docker Compose
	@echo "$(BOLD)$(BLUE)Starting Docker services...$(RESET)"
ifndef HAS_DOCKER
	$(error Docker is not installed or not running)
endif
	docker compose up -d
	@echo "$(GREEN)✓ Services started$(RESET)"
	@echo "$(CYAN)View logs: make docker-logs$(RESET)"

docker-down: ## Stop Docker services
	@echo "$(BOLD)$(BLUE)Stopping Docker services...$(RESET)"
ifndef HAS_DOCKER
	$(error Docker is not installed or not running)
endif
	docker compose down
	@echo "$(GREEN)✓ Services stopped$(RESET)"

docker-logs: ## Show Docker logs
ifndef HAS_DOCKER
	$(error Docker is not installed or not running)
endif
	docker compose logs -f

docker-restart: docker-down docker-up ## Restart Docker services

docker-clean: docker-down ## Stop and remove Docker containers, volumes
	@echo "$(BOLD)$(YELLOW)Cleaning Docker resources...$(RESET)"
	docker compose down -v --remove-orphans
	@echo "$(GREEN)✓ Docker resources cleaned$(RESET)"

# ============================================================================
# Build & Distribution
# ============================================================================

build: clean ## Build distribution packages
	@echo "$(BOLD)$(GREEN)Building distribution packages...$(RESET)"
	$(UV) build
	@echo "$(GREEN)✓ Build complete - check dist/$(RESET)"

# ============================================================================
# CI/CD
# ============================================================================

ci: install-dev check test ## Run full CI pipeline (install, check, test)
	@echo "$(BOLD)$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "$(BOLD)$(GREEN)✓ CI Pipeline Complete$(RESET)"
	@echo "$(BOLD)$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"

all: clean install-dev check test build ## Run everything (clean, install, check, test, build)
	@echo "$(BOLD)$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"
	@echo "$(BOLD)$(GREEN)✓ All Tasks Complete$(RESET)"
	@echo "$(BOLD)$(GREEN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)"

# ============================================================================
# Utility Targets
# ============================================================================

.PHONY: version
version: ## Show project version
	@echo "$(BOLD)Claude Code Proxy v1.0.0$(RESET)"

.PHONY: info
info: ## Show project information
	@echo "$(BOLD)$(CYAN)Project Information$(RESET)"
	@echo "  Name:         Claude Code Proxy"
	@echo "  Version:      1.0.0"
	@echo "  Python:       >= 3.9"
	@echo "  Source:       $(SRC_DIR)/"
	@echo "  Tests:        $(TEST_DIR)/"
	@echo "  Default Host: $(HOST)"
	@echo "  Default Port: $(PORT)"
	@echo ""
	@echo "$(BOLD)$(CYAN)Environment$(RESET)"
	@echo "  UV:           $(if $(HAS_UV),✓ installed,✗ not found)"
	@echo "  Docker:       $(if $(HAS_DOCKER),✓ installed,✗ not found)"
	@echo "  Python:       $$($(PYTHON) --version 2>&1)"

.PHONY: watch
watch: ## Watch for file changes and auto-run tests
	@echo "$(BOLD)$(CYAN)Watching for changes...$(RESET)"
	@command -v watchexec >/dev/null 2>&1 || { echo "$(RED)Error: watchexec not installed. Install with: cargo install watchexec-cli$(RESET)"; exit 1; }
	watchexec -e py -w $(SRC_DIR) -w $(TEST_DIR) -- make test-quick

.PHONY: env-template
env-template: ## Generate .env template file
	@echo "$(BOLD)$(CYAN)Generating .env.template...$(RESET)"
	@echo "# Claude Code Proxy Configuration" > .env.template
	@echo "" >> .env.template
	@echo "# Required: OpenAI API Key" >> .env.template
	@echo "OPENAI_API_KEY=your-key-here" >> .env.template
	@echo "" >> .env.template
	@echo "# Optional: Security" >> .env.template
	@echo "#ANTHROPIC_API_KEY=your-key-here" >> .env.template
	@echo "" >> .env.template
	@echo "# Optional: Model Configuration" >> .env.template
	@echo "#BIG_MODEL=gpt-4o" >> .env.template
	@echo "#MIDDLE_MODEL=gpt-4o" >> .env.template
	@echo "#SMALL_MODEL=gpt-4o-mini" >> .env.template
	@echo "" >> .env.template
	@echo "# Optional: API Configuration" >> .env.template
	@echo "#OPENAI_BASE_URL=https://api.openai.com/v1" >> .env.template
	@echo "#AZURE_API_VERSION=2024-02-15-preview" >> .env.template
	@echo "" >> .env.template
	@echo "# Optional: Server Settings" >> .env.template
	@echo "#HOST=0.0.0.0" >> .env.template
	@echo "#PORT=8082" >> .env.template
	@echo "#LOG_LEVEL=INFO" >> .env.template
	@echo "$(GREEN)✓ Generated .env.template$(RESET)"
