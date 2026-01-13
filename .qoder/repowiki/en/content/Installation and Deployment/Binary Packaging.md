# Binary Packaging

<cite>
**Referenced Files in This Document**   
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md)
- [Makefile](file://Makefile)
- [scripts/release.py](file://scripts/release.py)
- [scripts/version.py](file://scripts/version.py)
- [src/cli/main.py](file://src/cli/main.py)
- [src/config/defaults.toml](file://src/config/defaults.toml)
- [pyproject.toml](file://pyproject.toml)
- [docker-compose.yml](file://docker-compose.yml)
</cite>

## Table of Contents
1. [Overview](#overview)
2. [Available Binaries](#available-binaries)
3. [Installation from Binaries](#installation-from-binaries)
4. [Building Binaries Locally](#building-binaries-locally)
5. [Configuration](#configuration)
6. [Deployment](#deployment)
7. [Binary Size Optimization](#binary-size-optimization)
8. [Troubleshooting](#troubleshooting)
9. [Release Management](#release-management)
10. [Docker Integration](#docker-integration)

## Overview

The Vandamme Proxy CLI tool (`vdm`) is packaged as standalone binary executables using Nuitka, enabling execution without requiring a Python installation. These binaries are distributed via GitHub Releases and support multiple platforms including Linux, macOS, and Windows. The build process is orchestrated through the `make build-cli` workflow, which compiles the Python application into a single executable file with embedded dependencies and configuration.

The binary packaging system leverages Nuitka's `--onefile` and `--standalone` modes to create self-contained executables. Configuration files from `src/config/` are bundled into the binary using the `--include-data-files` directive, ensuring that default configurations are available at runtime without external dependencies.

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L1-L201)
- [Makefile](file://Makefile#L34-L384)

## Available Binaries

Pre-built binaries are available for the following platforms:

- **Linux**: `vdm-linux-x86_64`
- **macOS**: `vdm-darwin-x86_64` (compatible with Apple Silicon via Rosetta 2)
- **Windows**: `vdm-windows-x86_64.exe`

These binaries are generated through automated GitHub Actions workflows triggered by semantic version tags. Each binary is named according to the platform and architecture convention to ensure clear identification and compatibility.

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L11-L14)

## Installation from Binaries

### Download

To install the Vandamme Proxy CLI from pre-built binaries:

1. Visit [GitHub Releases](https://github.com/elifarley/vandamme-proxy/releases)
2. Download the appropriate binary for your platform
3. Make the binary executable (Linux/macOS):

```bash
chmod +x vdm-linux-x86_64  # or vdm-darwin-x86_64
```

### Verify Installation

After making the binary executable, verify the installation:

```bash
./vdm-linux-x86_64 --version
```

### Usage

The compiled binary supports all CLI commands:

```bash
# Start server
./vdm-linux-x86_64 server start

# Check health
./vdm-linux-x86_64 health

# View models
./vdm-linux-x86_64 models list
```

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L18-L47)

## Building Binaries Locally

### Requirements

- Python 3.10+
- UV package manager
- Nuitka 2.0+
- **Linux**: `patchelf` (install via `sudo apt install patchelf` or `sudo dnf install patchelf`)

### Build Process

The local build process is managed through the Makefile's `build-cli` target:

```bash
# Setup development environment (includes Nuitka)
make dev-env-init
make dev-deps-sync

# Build CLI binary for current platform
make build-cli
```

The `build-cli` target automatically detects the platform and architecture, then compiles the binary using Nuitka with the following configuration:

- Output directory: `dist/nuitka/`
- Platform-specific naming: `vdm-{platform}-{arch}`
- Embedded configuration files from `src/config/*.toml`
- Anti-bloat plugin enabled for size optimization

The build output is placed in `dist/nuitka/` with appropriate platform naming, such as `vdm-linux-x86_64` for Linux systems.

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L51-L72)
- [Makefile](file://Makefile#L350-L384)

## Configuration

Binaries automatically embed configuration files from `src/config/*.toml` during the build process. The primary configuration file `defaults.toml` contains default provider settings and fallback aliases for various AI models. At runtime, configuration can be overridden through environment variables:

```bash
# Set API keys
export OPENAI_API_KEY="your-key"

# Optional: Set proxy authentication
export PROXY_API_KEY="proxy-auth-key"

# Start server
./vdm-linux-x86_64 server start
```

The configuration system prioritizes environment variables over embedded defaults, allowing users to customize behavior without modifying the binary.

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L84-L95)
- [src/config/defaults.toml](file://src/config/defaults.toml#L1-L89)
- [pyproject.toml](file://pyproject.toml#L124-L128)

## Deployment

### Systemd Service (Linux)

For Linux deployments, the binary can be configured as a systemd service:

```bash
# 1. Copy binary
sudo cp vdm-linux-x86_64 /usr/local/bin/vdm
sudo chmod +x /usr/local/bin/vdm

# 2. Create environment file
sudo cat > /etc/vandamme-proxy.env << EOF
OPENAI_API_KEY=sk-your-key
HOST=0.0.0.0
PORT=8082
LOG_LEVEL=INFO
EOF

# 3. Create systemd service
sudo cat > /etc/systemd/system/vandamme-proxy.service << EOF
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
EOF

# 4. Start service
sudo systemctl daemon-reload
sudo systemctl enable vandamme-proxy
sudo systemctl start vandamme-proxy
```

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L99-L136)

## Binary Size Optimization

Binaries are optimized for size using Nuitka's `anti-bloat` plugin, which removes unnecessary modules and reduces the final binary footprint. Typical binary sizes are:

- **Linux**: ~20-25 MB
- **macOS**: ~22-28 MB
- **Windows**: ~18-23 MB

The build configuration excludes non-essential modules like tests and dashboard components using `--nofollow-import-to` directives, further reducing binary size. Configuration files are selectively bundled using `--include-data-files=src/config/*.toml=src/config/`, ensuring only necessary TOML files are included.

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L176-L183)
- [Makefile](file://Makefile#L376-L378)

## Troubleshooting

### Permission Issues

If encountering "Permission Denied" errors on Linux or macOS:

```bash
chmod +x vdm-*
```

### Missing libstdc++ in Alpine Containers

When using the binary in Alpine-based containers, ensure libstdc++ is installed:

```dockerfile
FROM alpine:latest
RUN apk add --no-cache libstdc++
COPY vdm-linux-x86_64 /usr/local/bin/vdm
RUN chmod +x /usr/local/bin/vdm
ENTRYPOINT ["/usr/local/bin/vdm", "server", "start"]
```

### Port Conflicts

If the default port (8082) is already in use:

```bash
PORT=8083 ./vdm server start
```

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L149-L168)
- [docker-compose.yml](file://docker-compose.yml#L1-L10)

## Release Management

The release process is automated through the `scripts/release.py` script, which handles version management and binary publishing workflows. Key release targets in the Makefile include:

- `version`: Show current version
- `version-bump`: Bump version (patch/minor/major)
- `tag-release`: Create and push git tag
- `release`: Complete release (tag + publish via GitHub Actions)

The release workflow automatically triggers GitHub Actions to build binaries for all platforms when a semantic version tag is pushed. The `release.py` script validates release readiness, runs tests, and manages version tagging.

**Section sources**
- [scripts/release.py](file://scripts/release.py#L1-L202)
- [scripts/version.py](file://scripts/version.py#L1-L99)
- [Makefile](file://Makefile#L462-L509)

## Docker Integration

The Vandamme Proxy can be containerized using Docker, with the binary as the entrypoint:

```dockerfile
FROM alpine:latest
RUN apk add --no-cache libstdc++
COPY vdm-linux-x86_64 /usr/local/bin/vdm
RUN chmod +x /usr/local/bin/vdm
ENTRYPOINT ["/usr/local/bin/vdm", "server", "start"]
```

The `docker-compose.yml` file defines a service that maps port 8082 and mounts the environment configuration:

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

**Section sources**
- [BINARY_PACKAGING.md](file://BINARY_PACKAGING.md#L140-L145)
- [docker-compose.yml](file://docker-compose.yml#L1-L10)