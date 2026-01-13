# Installation and Deployment

<cite>
**Referenced Files in This Document**   
- [Dockerfile](file://Dockerfile)
- [docker-compose.yml](file://docker-compose.yml)
- [Makefile](file://Makefile)
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md)
- [docs/makefile-workflows.md](file://docs/makefile-workflows.md)
- [print-env.sh](file://print-env.sh)
- [pyproject.toml](file://pyproject.toml)
- [start_proxy.py](file://start_proxy.py)
- [src/main.py](file://src/main.py)
- [src/config/defaults.toml](file://src/config/defaults.toml)
- [src/cli/commands/health.py](file://src/cli/commands/health.py)
- [src/api/routers/v1.py](file://src/api/routers/v1.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Direct Python Installation](#direct-python-installation)
3. [Docker Containerization](#docker-containerization)
4. [Binary Packaging](#binary-packaging)
5. [Production Considerations](#production-considerations)
6. [Scaling and Load Balancing](#scaling-and-load-balancing)
7. [Security Best Practices](#security-best-practices)
8. [Troubleshooting Guide](#troubleshooting-guide)

## Introduction
This document provides comprehensive guidance for installing and deploying the Vandamme Proxy server. The proxy serves as an intermediary that converts Claude API requests to OpenAI-compatible API calls, enabling seamless integration with various AI providers. Multiple deployment pathways are supported, including direct Python installation, Docker containerization, and standalone binary packaging. The document covers configuration, environment setup, production considerations, scaling strategies, and security best practices to ensure reliable and secure deployment.

## Direct Python Installation

The Vandamme Proxy can be installed directly using Python package managers. The recommended approach uses `uv`, a modern Python package installer and resolver, though `pip` is also supported as an alternative.

### Installation via UV (Recommended)
The project includes a Makefile that streamlines the installation process using `uv`. To set up the development environment:

```bash
make dev-env-init
make dev-deps-sync
```

These commands create a virtual environment and install all dependencies, including the CLI tools. The `uv` tool is used to sync dependencies as specified in the `pyproject.toml` and `uv.lock` files, ensuring reproducible builds.

### Installation via Pip
For environments where `uv` is not available, the proxy can be installed using `pip`:

```bash
pip install vandamme-proxy
```

Dependencies are defined in `pyproject.toml` and include FastAPI for the web framework, uvicorn as the ASGI server, and various other packages for configuration, logging, and API integration.

### Running the Server
After installation, the server can be started using the CLI:

```bash
vdm server start
```

Alternatively, the server can be run directly:

```bash
python start_proxy.py
```

The server reads configuration from environment variables or a `.env` file. Essential environment variables include `OPENAI_API_KEY`, with optional settings for `HOST`, `PORT`, and `LOG_LEVEL`. Example configuration files are provided in the `examples/` directory, such as `anthropic-direct.env` and `multi-provider.env`.

**Section sources**
- [pyproject.toml](file://pyproject.toml#L1-L159)
- [Makefile](file://Makefile#L1-L570)
- [start_proxy.py](file://start_proxy.py#L1-L14)
- [src/main.py](file://src/main.py#L1-L105)

## Docker Containerization

Docker provides a containerized deployment option that encapsulates the application and its dependencies, ensuring consistency across different environments.

### Dockerfile Analysis
The Dockerfile uses a multi-stage build approach with the `ghcr.io/astral-sh/uv:bookworm-slim` base image, which is a minimal Debian-based image with `uv` pre-installed. The build process is straightforward:

```dockerfile
FROM ghcr.io/astral-sh/uv:bookworm-slim

ADD . /app
WORKDIR /app
RUN uv sync --locked
CMD ["uv", "run", "start_proxy.py"]
```

This Dockerfile copies the entire project into the container, sets the working directory, synchronizes dependencies using `uv sync --locked` to ensure the lockfile is up to date, and starts the server using `uv run`. The use of `--locked` ensures that the installed packages match exactly what is specified in the lockfile, preventing dependency drift.

### Docker Compose Configuration
The project includes a `docker-compose.yml` file for orchestrating the proxy service:

```yaml
services:
  proxy:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - 8082:8082
    volumes:
      - ./.env:/app/.env
```

This configuration builds the image from the current context using the specified Dockerfile, maps port 8082 from the host to the container, and mounts the `.env` file from the host to the container to provide environment variables. This setup allows for easy configuration injection without rebuilding the image.

### Environment Variable Injection
Environment variables are injected into the container through the mounted `.env` file. This file should contain the necessary API keys and configuration settings. For example:

```bash
OPENAI_API_KEY=your-key-here
HOST=0.0.0.0
PORT=8082
LOG_LEVEL=INFO
```

The `docker-compose.yml` file can be extended to include additional services, such as a reverse proxy or database, if needed.

### Volume Mounting for Configuration
Configuration files can be mounted into the container using Docker volumes. The `docker-compose.yml` already mounts the `.env` file, but additional configuration files from the `config/` directory can also be mounted if required. This allows for dynamic configuration updates without rebuilding the container.

### Network Setup
The default Docker Compose configuration exposes port 8082, allowing external access to the proxy. For more complex network setups, additional network configurations can be added to the `docker-compose.yml` file, such as custom networks or external network attachments.

**Section sources**
- [Dockerfile](file://Dockerfile#L1-L11)
- [docker-compose.yml](file://docker-compose.yml#L1-L10)
- [src/main.py](file://src/main.py#L1-L105)

## Binary Packaging

The Vandamme Proxy can be packaged into standalone binary executables using Nuitka, allowing deployment without requiring a Python installation.

### Makefile Workflows for Binary Packaging
The Makefile includes targets for building and managing binary packages. The `build-cli` target compiles the CLI tool into a standalone binary:

```bash
make build-cli
```

This command uses Nuitka to create a one-file executable, including necessary data files such as configuration TOML files. The binary is output to the `dist/nuitka/` directory with a platform-specific name, such as `vdm-linux-x86_64` for Linux systems.

### Building Binaries for Different Platforms
The `build-cli` target automatically detects the platform and architecture, generating appropriate binary names. For cross-platform builds, the GitHub Actions workflow can be used to build binaries for Linux, macOS, and Windows simultaneously. This is triggered by pushing a semantic version tag:

```bash
git tag 1.2.3
git push origin 1.2.3
```

The GitHub Actions workflow then builds and packages the binaries for all supported platforms, making them available in the GitHub Releases section.

### Binary Distribution
Pre-built binaries are available on the [GitHub Releases](https://github.com/elifarley/vandamme-proxy/releases) page. Users can download the appropriate binary for their platform, make it executable, and run it directly:

```bash
chmod +x vdm-linux-x86_64
./vdm-linux-x86_64 server start
```

The binaries include embedded configuration files and rely on environment variables for runtime configuration, ensuring a seamless deployment experience.

**Section sources**
- [Makefile](file://Makefile#L350-L392)
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L1-L201)

## Production Considerations

Deploying the Vandamme Proxy in a production environment requires attention to process management, logging, and health monitoring to ensure reliability and maintainability.

### Process Managers
For Linux systems, the proxy can be managed using systemd as a service. The `BINARY_PACKAGING.md` document provides an example systemd service configuration:

```ini
[Unit]
Description=Vandamme Proxy Server
After=network.target

[Service]
Type=simple
User=vandamme
EnvironmentFile=/etc/vandamme-proxy.env
ExecStart=/usr/local/bin/vdm server start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

This service configuration runs the proxy as a dedicated user, loads environment variables from a configuration file, and automatically restarts the service if it fails. The service can be enabled and started using standard systemd commands.

### Logging Integration
The proxy uses Python's logging module with custom formatters and filters defined in the `src/core/logging/` directory. Logs are configured based on the `LOG_LEVEL` environment variable, with options for DEBUG, INFO, WARNING, ERROR, and CRITICAL levels. Access logs are only enabled at the DEBUG level to reduce verbosity in production.

Log messages are output to stdout, making them easily collectible by container orchestration systems or logging agents. The logging configuration suppresses noisy HTTP client logs unless in DEBUG mode, ensuring clean and relevant log output.

### Health Check Endpoints
The proxy exposes health check endpoints to monitor its status and connectivity. The `/health` endpoint returns a 200 status if the server is running:

```bash
curl -s http://localhost:8082/health | python -m json.tool
```

Additionally, the CLI provides health check commands:

```bash
vdm health server
vdm health upstream
```

The `server` command checks the proxy's availability, while the `upstream` command verifies connectivity to the upstream OpenAI API by testing the API key and base URL. These health checks are essential for integration with load balancers and monitoring systems.

**Section sources**
- [src/main.py](file://src/main.py#L1-L105)
- [src/cli/commands/health.py](file://src/cli/commands/health.py#L1-L126)
- [src/core/logging/configuration.py](file://src/core/logging/configuration.py)
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L98-L136)

## Scaling and Load Balancing

When deploying multiple proxy instances, proper scaling and load balancing strategies are essential to handle increased traffic and ensure high availability.

### Horizontal Scaling
Multiple proxy instances can be deployed across different servers or containers. Each instance operates independently, forwarding requests to the upstream API provider. This allows for horizontal scaling by adding more instances as needed.

### Load Balancer Configuration
A load balancer, such as NGINX or HAProxy, can distribute incoming requests across multiple proxy instances. For example, an NGINX configuration might look like:

```nginx
upstream vandamme_proxy {
    server 192.168.1.10:8082;
    server 192.168.1.11:8082;
    server 192.168.1.12:8082;
}

server {
    listen 80;
    location / {
        proxy_pass http://vandamme_proxy;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

This configuration distributes requests in a round-robin fashion across three proxy instances. Session persistence is not required since each request is stateless.

### Health Checks for Load Balancers
The load balancer should be configured to use the proxy's health check endpoint to monitor instance health. Unhealthy instances are automatically removed from the pool, ensuring traffic is only routed to healthy servers.

### Scaling Considerations
When scaling the proxy, consider the rate limits and quotas of the upstream API provider. Multiple proxy instances share the same API key, so the total request rate must stay within the provider's limits. If higher throughput is needed, consider using multiple API keys with different providers or requesting higher rate limits from the provider.

**Section sources**
- [src/api/routers/v1.py](file://src/api/routers/v1.py#L1-L34)
- [src/main.py](file://src/main.py#L1-L105)

## Security Best Practices

Securing the Vandamme Proxy deployment is critical to protect API keys and prevent unauthorized access.

### API Key Protection
The primary API key (`OPENAI_API_KEY`) must be kept confidential and never exposed in client-side code or public repositories. The proxy can also be configured with a `PROXY_API_KEY` for client authentication:

```bash
PROXY_API_KEY=sk-ant-client-...
```

When set, clients must provide this exact API key in their requests. The proxy validates the key before forwarding the request to the upstream API, adding an additional layer of security.

### Network Isolation
The proxy should be deployed in a secure network environment, with access restricted to trusted clients. Firewall rules should limit incoming connections to the proxy's port (default 8082) to only authorized IP addresses or networks.

In containerized deployments, network policies can be used to isolate the proxy container from other services. Docker's built-in networking features allow for the creation of custom networks that restrict communication between containers.

### Environment Variable Security
Environment variables containing sensitive information, such as API keys, should be managed securely. Avoid hardcoding values in configuration files that might be committed to version control. Instead, use environment variable files (`.env`) that are excluded from version control via `.gitignore`.

For production deployments, consider using a secrets management system, such as HashiCorp Vault or AWS Secrets Manager, to store and retrieve sensitive configuration values.

### Regular Security Audits
Regularly audit dependencies for known vulnerabilities using tools like `bandit`, which is included in the Makefile's `security-check` target:

```bash
make security-check
```

This command runs a security scan on the codebase, identifying potential security issues. Dependencies should also be kept up to date to benefit from security patches.

**Section sources**
- [src/main.py](file://src/main.py#L1-L105)
- [src/core/security.py](file://src/core/security.py)
- [Makefile](file://Makefile#L249-L253)

## Troubleshooting Guide

This section addresses common deployment issues and provides solutions for dependency conflicts, container startup failures, and other problems.

### Dependency Conflicts
Dependency conflicts can occur when multiple packages require different versions of the same dependency. To resolve conflicts:

1. Clean the environment:
```bash
make clean
```

2. Reinstall dependencies:
```bash
make dev-deps-sync
```

3. Check for outdated dependencies:
```bash
make deps-check
```

The `uv sync --locked` command ensures that dependencies match the lockfile exactly, preventing version mismatches.

### Container Startup Failures
If the Docker container fails to start, check the logs:

```bash
make docker-logs
```

Common issues include missing `.env` files or incorrect file permissions. Ensure the `.env` file is mounted correctly and contains the required API keys. If the container exits immediately, verify that the `CMD` in the Dockerfile is correct and that the `start_proxy.py` script is executable.

### Configuration Issues
Configuration problems often stem from incorrect environment variables. Use the `print-env.sh` script to debug environment variables:

```bash
./print-env.sh OPENAI_API_KEY
```

This script prints the value of a given environment variable, helping to verify that variables are set correctly. If the proxy fails to start, check that `OPENAI_API_KEY` is set and valid.

### Health Check Failures
If the health check fails, verify that the server is running and accessible:

```bash
make health
```

This command checks the `/health` endpoint and reports the response time. If the server is not running, start it with `make dev` or `vdm server start`. If the upstream API check fails, ensure that the `OPENAI_API_KEY` is correct and has sufficient permissions.

### General Debugging
For general debugging, increase the log level to DEBUG:

```bash
LOG_LEVEL=DEBUG vdm server start
```

This provides more detailed log output, including access logs and HTTP client requests. The logs can help identify issues with request processing or external API calls.

**Section sources**
- [print-env.sh](file://print-env.sh#L1-L10)
- [Makefile](file://Makefile#L147-L150)
- [src/cli/commands/health.py](file://src/cli/commands/health.py#L1-L126)
- [src/main.py](file://src/main.py#L1-L105)