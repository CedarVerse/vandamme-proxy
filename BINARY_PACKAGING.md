# Vandamme Proxy - Binary Packaging Guide

This document provides instructions for packaging the Vandamme Proxy CLI tool into standalone binary executables using Nuitka.

## Overview

The `vdm` CLI tool is compiled into standalone binaries that can run without requiring Python installation. Users can download pre-built binaries from [GitHub Releases](https://github.com/elifarley/vandamme-proxy/releases).

## Available Binaries

Pre-built binaries are available for:
- **Linux**: `vdm-linux-x86_64`
- **macOS**: `vdm-darwin-x86_64` (runs on Apple Silicon via Rosetta 2)
- **Windows**: `vdm-windows-x86_64.exe`

## Installation from Binaries

### Download

1. Visit [GitHub Releases](https://github.com/elifarley/vandamme-proxy/releases)
2. Download the appropriate binary for your platform
3. Make it executable (Linux/macOS):

```bash
chmod +x vdm-linux-x86_64  # or vdm-darwin-x86_64
```

### Verify Installation

```bash
./vdm-linux-x86_64 --version
```

### Usage

The binary supports all CLI commands:

```bash
# Start server
./vdm-linux-x86_64 server start

# Check health
./vdm-linux-x86_64 health

# View models
./vdm-linux-x86_64 models list
```

## Building Binaries Locally

### Requirements

- Python 3.10+
- UV package manager
- Nuitka 2.0+
- **Linux**: `patchelf` (install via `sudo apt install patchelf` or `sudo dnf install patchelf`)

### Installation

```bash
# Install development dependencies (includes Nuitka)
make install-dev
```

### Build for Current Platform

```bash
# Build CLI binary
make build-cli

# Output: dist/nuitka/vdm-{platform}-{arch}
```

### Build for All Platforms

Use the provided GitHub Actions workflow:

1. Push a semantic version tag: `git tag 1.2.3 && git push origin 1.2.3`
2. GitHub Actions automatically builds binaries for all platforms
3. Find binaries in the GitHub Release

## Configuration

Binaries embed required configuration files (`src/config/*.toml`) automatically. Additional configuration via environment variables:

```bash
# Set API keys
export OPENAI_API_KEY="your-key"

# Optional: Set proxy authentication
export ANTHROPIC_API_KEY="proxy-auth-key"

# Start server
./vdm-linux-x86_64 server start
```

## Deployment

### Systemd Service (Linux)

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

### Docker

```dockerfile
FROM alpine:latest
RUN apk add --no-cache libstdc++
COPY vdm-linux-x86_64 /usr/local/bin/vdm
RUN chmod +x /usr/local/bin/vdm
ENTRYPOINT ["/usr/local/bin/vdm", "server", "start"]
```

## Troubleshooting

### Permission Denied (Linux/macOS)

```bash
chmod +x vdm-*
```

### Missing API Keys

```bash
export OPENAI_API_KEY="your-key"
./vdm server start
```

### Port Already in Use

```bash
# Use different port
PORT=8083 ./vdm server start
```

### Version Check

```bash
./vdm --version
```

## Binary Size

Typical binary sizes:
- **Linux**: ~20-25 MB
- **macOS**: ~22-28 MB
- **Windows**: ~18-23 MB

Binaries are compiled with `--enable-plugin=anti-bloat` for size optimization.

## Security

- Binaries include no hardcoded credentials
- API keys provided via environment variables
- Run as non-root user recommended
- Verify binary integrity: checksums provided in releases

## Support

For issues or questions:
- [GitHub Issues](https://github.com/elifarley/vandamme-proxy/issues)
- [Documentation](https://github.com/elifarley/vandamme-proxy/blob/main/README.md)

---

_Updated for Nuitka 2.0+ | Last updated: 2025-12-26_
