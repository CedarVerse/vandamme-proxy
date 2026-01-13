# Direct Installation

<cite>
**Referenced Files in This Document**   
- [pyproject.toml](file://pyproject.toml)
- [Makefile](file://Makefile)
- [start_proxy.py](file://start_proxy.py)
- [src/main.py](file://src/main.py)
- [src/cli/main.py](file://src/cli/main.py)
- [src/core/config.py](file://src/core/config.py)
- [.env.example](file://.env.example)
- [README.md](file://README.md)
- [QUICKSTART.md](file://QUICKSTART.md)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Installation via Package Managers](#installation-via-package-managers)
3. [Development Environment Setup](#development-environment-setup)
4. [Configuration Management](#configuration-management)
5. [Running the Server](#running-the-server)
6. [Makefile Workflows](#makefile-workflows)
7. [Common Issues and Troubleshooting](#common-issues-and-troubleshooting)
8. [Conclusion](#conclusion)

## Introduction

The Vandamme Proxy is a lightweight, production-ready gateway that enables seamless integration between Claude Code CLI and multiple LLM providers including OpenAI, Anthropic, Poe, Azure, and others. This document provides comprehensive guidance for direct Python installation of the proxy, covering installation methods, environment configuration, server execution, and development workflows.

The proxy operates by intercepting requests from Claude Code CLI and routing them to the appropriate LLM provider based on model prefixes or smart aliases. It supports both OpenAI-compatible API conversion and direct Anthropic passthrough, making it versatile for various deployment scenarios.

**Section sources**
- [README.md](file://README.md#L1-L692)
- [QUICKSTART.md](file://QUICKSTART.md#L1-L263)

## Installation via Package Managers

### Using uv Package Manager

The recommended installation method uses `uv`, a modern Python package installer and resolver that offers significantly faster performance compared to traditional tools.

```bash
# Install Vandamme Proxy using uv
uv pip install vandamme-proxy

# Verify the installation
vdm version
```

The `uv` tool automatically handles dependency resolution and installation in an isolated environment. After installation, the `vdm` CLI command becomes available for managing the proxy server.

### Using pip Package Manager

For users who prefer the standard Python package manager, `pip` can also be used to install the proxy:

```bash
# Install using pip
pip install vandamme-proxy

# Verify the installation
vdm version
```

Both installation methods register the `vdm` command-line interface, which provides various subcommands for server management, configuration, and health checks.

The dependencies are defined in the `pyproject.toml` file, which specifies the required packages including FastAPI for the web framework, uvicorn as the ASGI server, pydantic for data validation, and python-dotenv for environment variable management.

```toml
[project]
name = "vandamme-proxy"
requires-python = ">=3.10"
dependencies = [
    "fastapi[standard]>=0.115.11",
    "uvicorn>=0.34.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "openai>=1.54.0",
    "respx>=0.22.0",
    "tomli>=2.0.0",
    "dash[cli]>=3.3.0",
    "dash-bootstrap-components[cli]>=2.0.4",
    "dash-ag-grid>=31.2.0",
]
```

The CLI tool is registered through the `project.scripts` section in `pyproject.toml`, which creates executable commands that map to functions in the codebase:

```toml
[project.scripts]
vdm = "src.cli.main:app"
"claude.vdm" = "src.cli.main:claude_alias"
```

This configuration enables the `vdm` command to invoke the Typer-based CLI application and the `claude.vdm` wrapper that intercepts Claude Code CLI parameters.

**Section sources**
- [pyproject.toml](file://pyproject.toml#L1-L159)
- [README.md](file://README.md#L133-L142)
- [QUICKSTART.md](file://QUICKSTART.md#L9-L18)

## Development Environment Setup

### Initialize Development Environment

For development purposes, the project provides a Makefile with targets to initialize and manage the development environment. The first step is to create a virtual environment using uv:

```bash
# Initialize development environment
make dev-env-init
```

This command creates a `.venv` directory with a Python virtual environment. The Makefile target ensures that the environment is properly configured and ready for dependency installation.

### Synchronize Development Dependencies

After initializing the environment, dependencies must be synchronized using the dev extras specified in the project configuration:

```bash
# Install dependencies and CLI tools
make dev-deps-sync
```

This command runs `uv sync --extra cli --editable`, which installs the project in editable mode along with all development and CLI dependencies. The process also verifies the installation by checking that the `vdm` command is available and functional.

The development dependencies are defined in both `pyproject.toml` and `Makefile`, with the latter providing additional tools for testing and code quality:

```makefile
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.25.0",
]
```

The Makefile also includes a verification step that checks both the CLI command availability and Python module imports to ensure a successful installation:

```makefile
check-install: ## Verify that installation was successful
	@printf "$(BOLD)$(BLUE)🔍 Verifying installation...$(RESET)\n"
	@printf "$(CYAN)Checking vdm command...$(RESET)\n"
	@if [ -f ".venv/bin/vdm" ]; then \
		printf "$(GREEN)✅ vdm command found$(RESET)\n"; \
		.venv/bin/vdm version; \
	else \
		printf "$(RED)❌ vdm command not found$(RESET)\n"; \
		printf "$(YELLOW)💡 Run 'make dev-env-init' to install CLI$(RESET)\n"; \
		exit 1; \
	fi
	@printf "$(CYAN)Checking Python imports...$(RESET)\n"
	@$(UV) run python -c "import src.cli.main; print('$(GREEN)✅ CLI module imports successfully$(RESET)')" || exit 1
	@printf "$(BOLD)$(GREEN)✅ Installation verified successfully$(RESET)\n"
```

**Section sources**
- [Makefile](file://Makefile#L114-L134)
- [pyproject.toml](file://pyproject.toml#L35-L45)

## Configuration Management

### Environment Variables and .env Files

The Vandamme Proxy uses a hierarchical configuration system that combines environment variables, `.env` files, and TOML configuration files. Settings from higher levels override those from lower levels in the following order:

1. Environment Variables (highest priority)
2. Local: `./vandamme-config.toml`
3. User: `~/.config/vandamme-proxy/vandamme-config.toml`
4. Package: `src/config/defaults.toml` (lowest priority)

The `.env.example` file provides a comprehensive template for configuration options, including API keys, provider settings, server parameters, and advanced features.

```bash
# Required: Your OpenAI API key
OPENAI_API_KEY="sk-your-openai-api-key-here"

# Optional: Default provider for models without prefixes
VDM_DEFAULT_PROVIDER="poe"

# Server settings
HOST="0.0.0.0"
PORT="8082"
LOG_LEVEL="INFO"

# Performance settings
MAX_TOKENS_LIMIT="4096"
MIN_TOKENS_LIMIT="100"
REQUEST_TIMEOUT="90"
MAX_RETRIES="2"
```

To use the configuration, copy the example file to `.env` and modify the values according to your requirements:

```bash
# Create configuration file from template
cp .env.example .env

# Edit the configuration
nano .env
```

### Configuration Processing

The configuration system is implemented in `src/core/config.py`, which processes environment variables and provides default values when necessary. The `Config` class initializes various settings including the default provider, API keys, base URLs, and server parameters.

```python
class Config:
    def __init__(self) -> None:
        # First, check if default provider is set via environment variable
        env_default_provider = os.environ.get("VDM_DEFAULT_PROVIDER")
        
        if env_default_provider:
            self.default_provider = env_default_provider
            self.default_provider_source = "env"
        else:
            # Try to load from TOML configuration
            try:
                from src.core.alias_config import AliasConfigLoader
                loader = AliasConfigLoader()
                defaults = loader.get_defaults()
                toml_default = defaults.get("default-provider")
                if toml_default:
                    self.default_provider = toml_default
                    self.default_provider_source = "toml"
                else:
                    self.default_provider = "openai"
                    self.default_provider_source = "system"
            except Exception as e:
                logger.debug(f"Failed to load default provider from config: {e}")
                self.default_provider = "openai"
                self.default_provider_source = "system"
```

The configuration also handles provider-specific settings, such as API keys, base URLs, and custom headers, allowing for flexible multi-provider setups.

**Section sources**
- [.env.example](file://.env.example#L1-L152)
- [src/core/config.py](file://src/core/config.py#L1-L200)
- [README.md](file://README.md#L217-L243)

## Running the Server

### Using start_proxy.py

The proxy server can be started directly using the `start_proxy.py` script, which adds the source directory to the Python path and imports the main application:

```python
#!/usr/bin/env python3
"""Start Claude Code Proxy server."""

import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.main import main

if __name__ == "__main__":
    main()
```

To run the server using this method:

```bash
# Start the proxy server
python start_proxy.py
```

### Using uvicorn Directly

Alternatively, the server can be started using uvicorn directly, which provides more control over server parameters:

```bash
# Run with uvicorn
uvicorn src.main:app --host 0.0.0.0 --port 8082 --reload

# With custom host and port
uvicorn src.main:app --host localhost --port 9000 --log-level info
```

The `--reload` flag enables hot reloading during development, automatically restarting the server when code changes are detected.

### Using the vdm CLI

The recommended method for production use is through the `vdm` CLI, which provides a user-friendly interface for server management:

```bash
# Start server with default settings
vdm server start

# Start with custom host and port
vdm server start --host 0.0.0.0 --port 8080

# Start with auto-reload for development
vdm server start --reload
```

The CLI command processes the configuration and displays a summary table before starting the server:

```python
table = Table(title="Vandamme Proxy Configuration")
table.add_column("Setting", style="cyan")
table.add_column("Value", style="green")

table.add_row("Server URL", f"http://{server_host}:{server_port}")
table.add_row("Default Provider", config.default_provider)
table.add_row(f"{config.default_provider.title()} Base URL", config.base_url)
table.add_row(f"{config.default_provider.title()} API Key", config.api_key_hash)
```

The server implementation in `src/main.py` configures logging, loads the configuration, and starts the uvicorn server with appropriate parameters:

```python
def main() -> None:
    # Configure logging FIRST before any console output
    from src.core.logging.configuration import configure_root_logging
    configure_root_logging(use_systemd=False)

    # Configuration summary
    print("🚀 Vandamme Proxy v1.0.0")
    print("✅ Configuration loaded successfully")
    print(f"   API Key : {config.api_key_hash}")
    print(f"   Base URL: {config.base_url}")
    print(f"   Max Tokens Limit: {config.max_tokens_limit}")
    print(f"   Request Timeout : {config.request_timeout}s")
    print(f"   Server: {config.host}:{config.port}")
    
    # Start server
    uvicorn.run(
        "src.main:app",
        host=config.host,
        port=config.port,
        log_level=log_level,
        access_log=(log_level == "debug"),
        reload=False,
    )
```

**Section sources**
- [start_proxy.py](file://start_proxy.py#L1-L14)
- [src/main.py](file://src/main.py#L1-L105)
- [src/cli/commands/server.py](file://src/cli/commands/server.py#L1-L114)

## Makefile Workflows

The project includes a comprehensive Makefile that defines workflows for development, testing, and deployment. These targets simplify common tasks and ensure consistency across different environments.

### Development Workflows

```makefile
dev: dev-deps-sync ## Sync deps and run server with hot reload
	@printf "$(BOLD)$(BLUE)Starting development server with auto-reload...$(RESET)\n"
	$(UV) run uvicorn src.main:app --host $(HOST) --port $(PORT) --reload --log-level $(shell echo $(LOG_LEVEL) | tr '[:upper:]' '[:lower:]')
```

The `dev` target synchronizes dependencies and starts the server with hot reload enabled, making it ideal for development.

### Health Checks

```makefile
health: ## Check proxy server health
	@printf "$(BOLD)$(CYAN)Checking server health...$(RESET)\n"
	@curl -s http://localhost:$(PORT)/health | $(PYTHON) -m json.tool || printf "$(YELLOW)Server not running on port $(PORT)$(RESET)\n"
```

This target uses curl to check the health endpoint and verify that the server is running properly.

### Utility Commands

The Makefile includes several utility commands for environment management:

```makefile
doctor: ## Run environment health check (read-only, fast)
	@printf "$(BOLD)$(CYAN)🩺 Doctor - Environment Health Check$(RESET)\n"
	@printf "\n"
	@printf "$(BOLD)$(YELLOW)System Information:$(RESET)\n"
	@printf "  OS:           $$(uname -s)\n"
	@printf "  Architecture: $$(uname -m)\n"
	@printf "  Kernel:       $$(uname -r)\n"
	@printf "\n"
	@printf "$(BOLD)$(YELLOW)Tool Availability:$(RESET)\n"
	@command -v uv >/dev/null 2>&1 && printf "  UV:           $(GREEN)✓ installed$(RESET)\n" || printf "  UV:           $(RED)✗ not found$(RESET)\n"
	@command -v python3 >/dev/null 2>&1 && printf "  Python 3:     $(GREEN)✓ installed$$($(PYTHON) --version 2>&1)$(RESET)\n" || printf "  Python 3:     $(RED)✗ not found$(RESET)\n"
```

The `doctor` target provides a comprehensive overview of the system environment, checking for the presence of required tools like uv, Python, Docker, and Git.

### Testing Workflows

```makefile
test: ## Run all tests except e2e (unit + integration, no API calls)
	@printf "$(BOLD)$(CYAN)Running all tests (excluding e2e)...$(RESET)\n"
	@# First run unit tests
	@$(UV) run $(PYTEST) $(TEST_DIR) -v -m unit
	@# Then try integration tests if server is running
	@if curl -s http://localhost:$(PORT)/health > /dev/null 2>&1 || \
	   curl -s http://localhost:18082/health > /dev/null 2>&1; then \
		printf "$(YELLOW)Server detected, running integration tests...$(RESET)\n"; \
		$(UV) run $(PYTEST) $(TEST_DIR) -v -m "integration and not e2e" || printf "$(YELLOW)⚠ Some integration tests failed$(RESET)\n"; \
	else \
		printf "$(YELLOW)⚠ Server not running, skipping integration tests$(RESET)\n"; \
		printf "$(CYAN)To run integration tests:$(RESET)\n"; \
		printf "  1. Start server: make dev\n"; \
		printf "  2. Run: make test-integration\n"; \
	fi
```

The testing targets are organized into unit, integration, and end-to-end categories, allowing for flexible test execution based on the development phase.

**Section sources**
- [Makefile](file://Makefile#L1-L570)
- [README.md](file://README.md#L488-L538)

## Common Issues and Troubleshooting

### Missing uv Binary

If the `uv` binary is not found during installation or dependency synchronization, install it using the official installation script:

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH if necessary
export PATH="$HOME/.local/bin:$PATH"
```

The Makefile includes explicit checks for the presence of uv and provides helpful error messages when it's missing:

```makefile
ifndef HAS_UV
	$(error UV is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh)
endif
```

### Incorrect Python Version

The proxy requires Python 3.10 or higher, as specified in the `pyproject.toml` file:

```toml
requires-python = ">=3.10"
```

Verify your Python version with:

```bash
python3 --version
```

If you have multiple Python versions installed, ensure that the correct version is used by uv or pip:

```bash
# Use specific Python version
uv --python 3.11 pip install vandamme-proxy
```

### Dependency Conflicts

When dependency conflicts occur, try the following steps:

1. Clean the environment and reinstall dependencies:

```bash
# Clean temporary files and caches
make clean

# Reinitialize environment
make dev-env-init

# Sync dependencies
make dev-deps-sync
```

2. Check for outdated dependencies:

```bash
# Check for outdated packages
make deps-check
```

3. If conflicts persist, create a fresh virtual environment:

```bash
# Remove existing environment
rm -rf .venv

# Reinitialize
make dev-env-init
make dev-deps-sync
```

### Configuration Issues

Common configuration problems include missing API keys or incorrect environment variables. Verify your configuration with:

```bash
# Check server health
vdm health server

# Validate configuration
vdm config validate

# Show current configuration
vdm config show
```

Ensure that your `.env` file is properly formatted and contains the required API keys for your chosen providers.

**Section sources**
- [Makefile](file://Makefile#L127-L129)
- [pyproject.toml](file://pyproject.toml#L21-L33)
- [README.md](file://README.md#L512-L522)

## Conclusion

The Vandamme Proxy provides a flexible and powerful solution for routing LLM requests across multiple providers. Through direct Python installation using either uv or pip, developers can quickly set up the proxy and begin leveraging its capabilities.

The installation process is streamlined through the use of modern Python tooling, with uv providing faster dependency resolution and installation. The development environment setup is simplified with Makefile targets that handle virtual environment creation and dependency synchronization.

Configuration is managed through environment variables and `.env` files, following a hierarchical system that allows for flexible overrides. The proxy can be started using multiple methods, including direct script execution, uvicorn, or the vdm CLI, with options for custom host and port settings.

The comprehensive Makefile provides workflows for development, testing, and maintenance, making it easy to manage the proxy throughout its lifecycle. Common issues such as missing dependencies or configuration errors can be addressed through the provided troubleshooting guidance.

By following this documentation, users can successfully install and configure the Vandamme Proxy for both development and production use cases.

**Section sources**
- [README.md](file://README.md#L1-L692)
- [QUICKSTART.md](file://QUICKSTART.md#L1-L263)
- [pyproject.toml](file://pyproject.toml#L1-L159)