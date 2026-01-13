# Getting Started

<cite>
**Referenced Files in This Document**   
- [README.md](file://README.md)
- [QUICKSTART.md](file://QUICKSTART.md)
- [start_proxy.py](file://start_proxy.py)
- [Dockerfile](file://Dockerfile)
- [docker-compose.yml](file://docker-compose.yml)
- [.env.example](file://.env.example)
- [examples/anthropic-direct.env](file://examples/anthropic-direct.env)
- [examples/aws-bedrock.env](file://examples/aws-bedrock.env)
- [examples/google-vertex.env](file://examples/google-vertex.env)
- [examples/multi-provider.env](file://examples/multi-provider.env)
- [pyproject.toml](file://pyproject.toml)
- [src/main.py](file://src/main.py)
- [src/cli/main.py](file://src/cli/main.py)
- [src/cli/commands/server.py](file://src/cli/commands/server.py)
</cite>

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Starting the Server](#starting-the-server)
5. [Making API Requests](#making-api-requests)
6. [Setting Up Model Aliases](#setting-up-model-aliases)
7. [Using the Dashboard](#using-the-dashboard)
8. [Common Setup Issues](#common-setup-issues)
9. [Production Deployment](#production-deployment)
10. [Next Steps](#next-steps)

## Prerequisites

Before setting up vandamme-proxy, ensure you have the following prerequisites installed on your system:

- **Python 3.10 or higher**: The project requires Python 3.10+ as specified in the pyproject.toml file
- **pip or uv**: Package installer for Python (uv is recommended for faster installation)
- **git**: For cloning the repository (if installing from source)
- **curl**: For making API requests to test the proxy
- **API keys**: At least one provider API key (OpenAI, Anthropic, Poe, etc.)

You can verify your Python version by running:
```bash
python --version
```

The project dependencies are listed in pyproject.toml and include FastAPI, Uvicorn, Pydantic, and other essential packages for building and running the proxy server.

**Section sources**
- [pyproject.toml](file://pyproject.toml#L21)
- [README.md](file://README.md#L174)

## Installation

You can install vandamme-proxy using either pip or uv (recommended). The installation process is straightforward and can be completed in a few simple steps.

### Using uv (Recommended)

uv is a fast Python package installer and resolver. To install vandamme-proxy using uv:

```bash
# Install using uv
uv pip install vandamme-proxy

# Verify installation
vdm version
```

### Using pip

If you prefer to use pip, you can install the package as follows:

```bash
# Install using pip
pip install vandamme-proxy

# Verify installation
vdm version
```

### Installing from Source

For development purposes or to contribute to the project, you can install from source:

```bash
# Clone the repository
git clone https://github.com/CedarVerse/vandamme-proxy.git
cd vandamme-proxy

# Install in development mode
make dev-env-setup
source .venv/bin/activate

# Verify installation
vdm version
```

The installation will provide you with the `vdm` CLI command, which is used to manage the proxy server, configure settings, and perform health checks.

**Section sources**
- [README.md](file://README.md#L133-L142)
- [QUICKSTART.md](file://QUICKSTART.md#L9-L33)
- [pyproject.toml](file://pyproject.toml#L57-L58)

## Configuration

vandamme-proxy uses a hierarchical configuration system that allows you to set up your proxy with various providers and customize its behavior. Configuration can be done through environment variables, .env files, or TOML configuration files.

### Configuration Hierarchy

The configuration system follows this priority order (highest to lowest):

1. Environment Variables
2. Local: ./vandamme-config.toml
3. User: ~/.config/vandamme-proxy/vandamme-config.toml
4. Package: src/config/defaults.toml

### Creating a .env File

The easiest way to configure the proxy is by creating a `.env` file in your project root. You can use the `.env.example` file as a template:

```bash
# Copy the example file
cp .env.example .env
```

Then edit the `.env` file to add your API keys and configuration settings.

### Interactive Configuration Setup

Alternatively, you can use the interactive configuration wizard:

```bash
# Start interactive setup
vdm config setup
```

This will guide you through setting up your provider(s), entering API keys, and configuring other options.

### Provider Configuration Examples

The repository includes several example configuration files in the `examples/` directory that demonstrate how to configure different providers:

#### OpenAI Configuration
```bash
# In your .env file
OPENAI_API_KEY="sk-your-openai-key"
VDM_DEFAULT_PROVIDER="openai"
```

#### Anthropic Direct Configuration
Use the example file `examples/anthropic-direct.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_FORMAT=anthropic
VDM_DEFAULT_PROVIDER=anthropic
```

#### AWS Bedrock Configuration
Use the example file `examples/aws-bedrock.env`:
```bash
BEDROCK_API_KEY=your-aws-access-key
BEDROCK_SECRET_KEY=your-aws-secret-key
BEDROCK_BASE_URL=https://bedrock-runtime.us-east-1.amazonaws.com
BEDROCK_API_FORMAT=anthropic
VDM_DEFAULT_PROVIDER=bedrock
```

#### Google Vertex AI Configuration
Use the example file `examples/google-vertex.env`:
```bash
VERTEX_API_KEY=your-vertex-ai-api-key
VERTEX_BASE_URL=https://generativelanguage.googleapis.com/v1beta
VERTEX_API_FORMAT=anthropic
VDM_DEFAULT_PROVIDER=vertex
```

#### Multi-Provider Configuration
Use the example file `examples/multi-provider.env` to configure multiple providers simultaneously:
```bash
# OpenAI Provider
OPENAI_API_KEY=sk-openai-...
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic Direct Provider
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_FORMAT=anthropic

# AWS Bedrock Provider
BEDROCK_API_KEY=your-aws-key
BEDROCK_BASE_URL=https://bedrock-runtime.us-west-2.amazonaws.com
BEDROCK_API_FORMAT=anthropic

# Set default provider
VDM_DEFAULT_PROVIDER=openai
```

### Key Configuration Options

- **Provider API Keys**: Set `{PROVIDER}_API_KEY` for each provider you want to use
- **Default Provider**: Set `VDM_DEFAULT_PROVIDER` to specify which provider to use by default
- **API Format**: Set `{PROVIDER}_API_FORMAT` to "openai" or "anthropic" depending on the provider's API format
- **Server Settings**: Configure `HOST`, `PORT`, and `LOG_LEVEL` for the proxy server

**Section sources**
- [.env.example](file://.env.example)
- [examples/anthropic-direct.env](file://examples/anthropic-direct.env)
- [examples/aws-bedrock.env](file://examples/aws-bedrock.env)
- [examples/google-vertex.env](file://examples/google-vertex.env)
- [examples/multi-provider.env](file://examples/multi-provider.env)
- [README.md](file://README.md#L219-L242)

## Starting the Server

Once you have configured your environment, you can start the vandamme-proxy server using several methods.

### Using the CLI (Recommended)

The recommended way to start the server is using the `vdm` CLI command:

```bash
# Start server in production mode
vdm server start

# Start server with custom host and port
vdm server start --host 0.0.0.0 --port 8082

# Start server in development mode with hot reload
vdm server start --reload
```

When you start the server, you'll see output similar to:

```
🚀 Vandamme Proxy v1.0.0
✅ Configuration loaded successfully
   API Key : sk-openai-...
   Base URL: https://api.openai.com/v1
   Max Tokens Limit: 4096
   Request Timeout : 90s
   Server: 0.0.0.0:8082
   Client API Key Validation: Disabled
```

### Using start_proxy.py

You can also start the server directly using the start_proxy.py script:

```bash
# Make the script executable
chmod +x start_proxy.py

# Start the server
./start_proxy.py
```

### Using Docker

For containerized deployment, you can use Docker and docker-compose:

```bash
# Build and start with Docker Compose
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

The docker-compose.yml file is configured to map port 8082 and mount the .env file:

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

### Server Configuration Options

When starting the server, you can override configuration settings:

- `--host`: Override the server host (default: 0.0.0.0)
- `--port`: Override the server port (default: 8082)
- `--reload`: Enable auto-reload for development
- `--systemd`: Send logs to systemd journal instead of console

**Section sources**
- [start_proxy.py](file://start_proxy.py)
- [Dockerfile](file://Dockerfile)
- [docker-compose.yml](file://docker-compose.yml)
- [src/cli/commands/server.py](file://src/cli/commands/server.py)
- [src/main.py](file://src/main.py)

## Making API Requests

Once the server is running, you can make API requests to the proxy using curl or any HTTP client.

### OpenAI-Compatible Endpoint

To make a request to an OpenAI-compatible endpoint:

```bash
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Anthropic Passthrough Endpoint

To make a request to an Anthropic passthrough endpoint:

```bash
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic:claude-3-5-sonnet-20241022",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Using Provider Prefixes

You can route requests to specific providers using model prefixes:

```bash
# Route to OpenAI
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai:gpt-4o",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Route to Poe
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "poe:gemini-flash",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Testing the Setup

You can verify your setup using the built-in health checks:

```bash
# Check proxy health
vdm health server

# Test upstream provider connectivity
vdm health upstream

# List available models
curl http://localhost:8082/v1/models

# View active model aliases
curl http://localhost:8082/v1/aliases
```

**Section sources**
- [src/api/endpoints.py](file://src/api/endpoints.py)
- [README.md](file://README.md#L199-L211)

## Setting Up Model Aliases

vandamme-proxy supports smart model aliases that allow you to create memorable shortcuts for your models.

### Configuring Aliases

You can configure model aliases using environment variables in your .env file:

```bash
# Configure model aliases
POE_ALIAS_FAST=gemini-flash
POE_ALIAS_HAIKU=gpt-4o-mini
ANTHROPIC_ALIAS_CHAT=claude-3-5-sonnet-20241022
OPENAI_ALIAS_CODE=gpt-4o
```

### Alias Matching Rules

The alias system uses intelligent matching rules:

- **Case-Insensitive**: `fast`, `Fast`, `FAST` all match
- **Substring Matching**: `my-fast-model` matches `FAST` alias
- **Hyphen/Underscore**: `my-alias` and `my_alias` both match `MY_ALIAS`
- **Provider-Scoped**: Each alias is tied to a specific provider
- **Priority Order**: Exact match → Longest substring → Provider order → Alphabetical

### Testing Aliases

After configuring aliases, you can test them through the API:

```bash
# Use the fast alias with Poe provider
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "poe:fast",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# View all active aliases
curl http://localhost:8082/v1/aliases
```

The aliases will be resolved to their target models before the request is forwarded to the provider.

**Section sources**
- [.env.example](file://.env.example#L60-L102)
- [README.md](file://README.md#L270-L291)

## Using the Dashboard

vandamme-proxy includes a built-in dashboard for monitoring and managing your proxy.

### Accessing the Dashboard

Once the server is running, you can access the dashboard at:

```
http://localhost:8082/dashboard/
```

### Dashboard Features

The dashboard provides several features for monitoring your proxy:

- **Active Requests**: Real-time view of active requests with streaming updates
- **Metrics**: Usage metrics, token counts, and performance statistics
- **Model Information**: Details about available models and their usage
- **Configuration**: View current configuration settings
- **Logs**: Access to server logs and request details

### Dashboard Components

The dashboard is built using Dash and includes several components:

- **AG Grid**: For displaying tabular data with filtering and sorting
- **Metrics Visualization**: Charts and graphs for usage metrics
- **Model Browser**: Interface for exploring available models
- **Configuration Viewer**: Display of current configuration settings

You can customize the dashboard by modifying the files in the `src/dashboard/` directory.

**Section sources**
- [src/dashboard/app.py](file://src/dashboard/app.py)
- [src/dashboard/mount.py](file://src/dashboard/mount.py)
- [src/main.py](file://src/main.py#L21-L35)

## Common Setup Issues

Here are some common issues you might encounter when setting up vandamme-proxy and how to resolve them.

### Missing Environment Variables

If you forget to set required environment variables, the server will not start properly. Make sure you have at least one provider API key set:

```bash
# Required environment variable
OPENAI_API_KEY=your-key-here
```

### Incorrect Key Formats

Ensure your API keys are in the correct format. Most API keys should start with a specific prefix:

- OpenAI: `sk-`
- Anthropic: `sk-ant-`
- Poe: No specific prefix required

### Port Conflicts

If port 8082 is already in use, you can change the port in your .env file:

```bash
# Change the port
PORT=8083
```

Or override it when starting the server:

```bash
vdm server start --port 8083
```

### Provider Not Discovered

Providers are auto-discovered based on environment variables. If a provider is not being discovered, ensure you have the correct environment variable name:

```bash
# Correct format: {PROVIDER}_API_KEY
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
POE_API_KEY=your-key
```

### Authentication Failures

If you're getting authentication failures (401/403), check:

1. Your API key is correct
2. The key has the necessary permissions
3. For passthrough providers, ensure clients are providing their API keys

### Request Timeouts

If requests are timing out, you can increase the timeout in your .env file:

```bash
# Increase request timeout
REQUEST_TIMEOUT=120
```

### Debugging Tips

Use these commands to debug issues:

```bash
# Show current configuration
vdm config show

# Validate configuration
vdm config validate

# Check server health
vdm health server

# Test upstream connectivity
vdm health upstream
```

**Section sources**
- [src/main.py](file://src/main.py#L44-L62)
- [src/cli/commands/config.py](file://src/cli/commands/config.py)
- [README.md](file://README.md#L200-L207)

## Production Deployment

For production deployment, consider the following options:

### Docker Deployment

The recommended way to deploy in production is using Docker:

```bash
# Build and start with Docker Compose
docker compose up -d

# Ensure your .env file is properly configured
# The docker-compose.yml will mount it automatically
```

### Systemd Service

For Linux systems, you can create a systemd service:

```bash
# Create systemd service file
sudo tee /etc/systemd/system/vandamme-proxy.service > /dev/null <<EOF
[Unit]
Description=Vandamme Proxy
After=network.target

[Service]
Type=simple
User=vandamme
WorkingDirectory=/opt/vandamme-proxy
Environment=HOST=0.0.0.0
Environment=PORT=8082
ExecStart=/opt/vandamme-proxy/.venv/bin/vdm server start --systemd
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable vandamme-proxy
sudo systemctl start vandamme-proxy
```

### Environment Variables for Production

In production, consider setting these environment variables:

```bash
# Server settings
HOST=0.0.0.0
PORT=8082
LOG_LEVEL=INFO

# Performance settings
MAX_TOKENS_LIMIT=4096
REQUEST_TIMEOUT=90
MAX_RETRIES=2

# Security
PROXY_API_KEY=your-proxy-key  # Require client authentication
```

### Multiple API Keys for High Availability

For production resilience, configure multiple API keys:

```bash
# Multiple keys for automatic round-robin rotation
OPENAI_API_KEY="sk-key1 sk-key2 sk-key3"
ANTHROPIC_API_KEY="sk-ant-prod1 sk-ant-prod2 sk-ant-backup"
```

This provides automatic failover if one key becomes invalid.

**Section sources**
- [docker-compose.yml](file://docker-compose.yml)
- [README.md](file://README.md#L608-L650)

## Next Steps

Now that you have vandamme-proxy up and running, here are some next steps to explore:

### Advanced Configuration

- Explore the full range of configuration options in `.env.example`
- Set up custom headers for specific providers
- Configure multiple providers with different settings
- Implement API key passthrough for multi-tenant scenarios

### Integration with Claude Code

Configure Claude Code to use the proxy:

```bash
# Point Claude Code to the proxy
export ANTHROPIC_BASE_URL=http://localhost:8082

# Use with Claude Code CLI
claude --model openai:gpt-4o "Analyze this code"
claude --model poe:gemini-flash "Quick question"
claude --model fast "Fast response"  # Smart alias
```

### Monitoring and Observability

- Explore the dashboard for monitoring usage
- Set up logging and metrics collection
- Configure alerts for high usage or errors
- Monitor token usage and costs

### Extending Functionality

- Add custom middleware for request/response processing
- Implement caching strategies
- Extend the dashboard with custom visualizations
- Contribute to the project by adding new features

For more information, refer to the comprehensive documentation in the `docs/` directory and the project README.

**Section sources**
- [README.md](file://README.md#L453-L485)
- [docs/](file://docs/)