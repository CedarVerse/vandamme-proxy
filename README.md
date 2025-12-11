# Vandamme Proxy

A proxy server that converts Claude API requests to OpenAI-compatible API calls. Enables **Claude Code** to simultaneously work with various LLM providers including Poe, OpenAI, Azure OpenAI, and any OpenAI- or Anthropic-compatible API.

![Vandamme Proxy](demo.png)

## Features

- **Full Claude API Compatibility**: Complete `/v1/messages` endpoint support
- **Multiple Provider Support**: Poe, OpenAI, Azure OpenAI, local models (Ollama), etc
- **Model Routing**: Claude model names are routed to the corresponding provider (according to the provider prefix)
- **Model Aliases**: Create aliases for models using `VDM_ALIAS_*` environment variables
- **Function Calling**: Complete tool use support with proper conversion
- **Streaming Responses**: Real-time SSE streaming support
- **Image Support**: Base64 encoded image input
- **Custom Headers**: Automatic injection of custom HTTP headers for API requests
- **Error Handling**: Comprehensive error handling and logging

## Quick Start

### 1. Install Dependencies

```bash
# Quick start (recommended)
make init-dev
source .venv/bin/activate
```

### 2. Configure

```bash
# Interactive configuration setup
vdm config setup

# Or manually create .env file
cp .env.example .env
# Edit .env and add your API configuration
# Note: Environment variables are automatically loaded from .env file
```

### 3. Start Server

```bash
# Using the vdm CLI (recommended)
vdm server start

# Or with development mode
vdm server start --reload

# Or direct run
python start_proxy.py

# Or with docker compose
docker compose up -d
```

### 4. Check Configuration

```bash
# Show current configuration
vdm config show

# Validate configuration
vdm config validate

# Check API connectivity
vdm health upstream
```

### 5. Use with Claude Code

```bash
# If ANTHROPIC_API_KEY is not set in the proxy:
ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY="any-value" claude

# If ANTHROPIC_API_KEY is set in the proxy:
ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY="exact-matching-key" claude
```

## Configuration

The application automatically loads environment variables from a `.env` file in the project root using `python-dotenv`. You can also set environment variables directly in your shell.

### Environment Variables

**Required:**

- `OPENAI_API_KEY` - Your API key for the target provider

**Security:**

- `ANTHROPIC_API_KEY` - Expected Anthropic API key for client validation
  - If set, clients must provide this exact API key to access the proxy
  - If not set, any API key will be accepted

**Model Configuration:**

- `ANTHROPIC_DEFAULT_HAIKU_MODEL` - Choose a model that is cheap and fast
- `ANTHROPIC_DEFAULT_SONNET_MODEL` - Choose a middle-ground model (`glm-4.6` for instance)
- `ANTHROPIC_DEFAULT_OPUS_MODEL` - Choose a model that gives the very best results

**API Configuration:**

- `OPENAI_BASE_URL` - API base URL (default: `https://api.openai.com/v1`)

**Server Settings:**

- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8082`)
- `LOG_LEVEL` - Logging level (default: `WARNING`)

**Performance:**

- `MAX_TOKENS_LIMIT` - Token limit (default: `4096`)
- `REQUEST_TIMEOUT` - Request timeout in seconds (default: `90`)

**Model Aliases:**

- `VDM_ALIAS_*` - Create model aliases for flexible model selection
  - Supports case-insensitive substring matching
  - Example: `VDM_ALIAS_HAIKU=poe:gpt-4o-mini`

**Custom Headers:**

- `CUSTOM_HEADER_*` - Custom headers for API requests (e.g., `CUSTOM_HEADER_ACCEPT`, `CUSTOM_HEADER_AUTHORIZATION`)
  - Uncomment in `.env` file to enable custom headers

### Custom Headers Configuration

Add custom headers to your API requests by setting environment variables with the `CUSTOM_HEADER_` prefix:

```bash
# Uncomment to enable custom headers
# CUSTOM_HEADER_ACCEPT="application/jsonstream"
# CUSTOM_HEADER_CONTENT_TYPE="application/json"
# CUSTOM_HEADER_USER_AGENT="your-app/1.0.0"
# CUSTOM_HEADER_AUTHORIZATION="Bearer your-token"
# CUSTOM_HEADER_X_API_KEY="your-api-key"
# CUSTOM_HEADER_X_CLIENT_ID="your-client-id"
# CUSTOM_HEADER_X_CLIENT_VERSION="1.0.0"
# CUSTOM_HEADER_X_REQUEST_ID="unique-request-id"
# CUSTOM_HEADER_X_TRACE_ID="trace-123"
# CUSTOM_HEADER_X_SESSION_ID="session-456"
```

### Header Conversion Rules

Environment variables with the `CUSTOM_HEADER_` prefix are automatically converted to HTTP headers:

- Environment variable: `CUSTOM_HEADER_ACCEPT`
- HTTP Header: `ACCEPT`

- Environment variable: `CUSTOM_HEADER_X_API_KEY`
- HTTP Header: `X-API-KEY`

- Environment variable: `CUSTOM_HEADER_AUTHORIZATION`
- HTTP Header: `AUTHORIZATION`

### Supported Header Types

- **Content Type**: `ACCEPT`, `CONTENT-TYPE`
- **Authentication**: `AUTHORIZATION`, `X-API-KEY`
- **Client Identification**: `USER-AGENT`, `X-CLIENT-ID`, `X-CLIENT-VERSION`
- **Tracking**: `X-REQUEST-ID`, `X-TRACE-ID`, `X-SESSION-ID`

### Usage Example

```bash
# Basic configuration
OPENAI_API_KEY="sk-your-openai-api-key-here"
OPENAI_BASE_URL="https://api.openai.com/v1"

# Enable custom headers (uncomment as needed)
CUSTOM_HEADER_ACCEPT="application/jsonstream"
CUSTOM_HEADER_CONTENT_TYPE="application/json"
CUSTOM_HEADER_USER_AGENT="my-app/1.0.0"
CUSTOM_HEADER_AUTHORIZATION="Bearer my-token"
```

The proxy will automatically include these headers in all API requests to the target LLM provider.

### Model Aliases Configuration

Model aliases allow you to create memorable names for models and enable case-insensitive substring matching for flexible model selection.

```bash
# Basic tier-based aliases
VDM_ALIAS_HAIKU=poe:gpt-4o-mini
VDM_ALIAS_SONNET=openai:gpt-4o
VDM_ALIAS_OPUS=anthropic:claude-3-opus-20240229

# Custom aliases
VDM_ALIAS_CHAT=anthropic:claude-3-5-sonnet-20241022
VDM_ALIAS_FAST=poe:gpt-4o-mini
VDM_ALIAS_SMART=openai:o1-preview

# Provider-specific aliases
VDM_ALIAS_OPENAI_FAST=openai:gpt-4o-mini
VDM_ANTHROPIC_FAST=anthropic:claude-3-5-haiku-20241022
```

#### Alias Resolution Rules

1. **Case-Insensitive Matching**: `VDM_ALIAS_FAST` matches "fast", "FAST", "FastModel", etc.
2. **Substring Matching**: Any model name containing "haiku" will match `VDM_ALIAS_HAIKU`
3. **Flexible Hyphen/Underscore Matching**: Aliases match model names regardless of hyphen/underscore usage
   - `VDM_ALIAS_MY_ALIAS` matches both "my-alias" and "my_alias"
   - `VDM_ALIAS_MY_MODEL` matches "oh-this-is-my-model-right" and "oh-this-is-my_model-right"
4. **Provider Prefix Support**: Alias values can include provider prefixes (e.g., "poe:gpt-4o-mini")
5. **Priority Order**:
   - Exact matches first
   - Longest substring match
   - Alphabetical order for ties

#### API Usage

```bash
# List all configured aliases
curl http://localhost:8082/v1/aliases

# Use alias in requests (substring matching)
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "my-haiku-model",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
# This resolves to "poe:gpt-4o-mini" if VDM_ALIAS_HAIKU is set
```

### Provider Examples

#### OpenAI

```bash
OPENAI_API_KEY="sk-your-openai-key"
OPENAI_BASE_URL="https://api.openai.com/v1"
```

#### Azure OpenAI

```bash
OPENAI_API_KEY="your-azure-key"
OPENAI_BASE_URL="https://your-resource.openai.azure.com/openai/deployments/your-deployment"
AZURE_API_VERSION="2024-02-15-preview"
```

#### Local Models (Ollama)

```bash
OPENAI_API_KEY="dummy-key"  # Required but can be dummy
OPENAI_BASE_URL="http://localhost:11434/v1"
```

#### Other Providers

Any OpenAI-compatible API can be used by setting the appropriate `OPENAI_BASE_URL`.

## Provider Loading Behavior

The proxy automatically discovers and loads providers based on environment variables:

### Provider Discovery

- Only providers with `{PROVIDER}_API_KEY` set are discovered
- Providers without an API key are silently ignored (no warnings)
- For special providers (OpenAI, Poe), `BASE_URL` defaults to their standard endpoints if not provided

### Provider Status

When the proxy starts, it displays a summary of active providers:

```
📊 Active Providers:
   openai (a1b2c3d4) - https://api.openai.com/v1
   poe (e5f6g7h8) - https://api.poe.com/v1
   ⚠️ openrouter (i9j0k1l2) - Missing BASE_URL

2 providers ready for requests
```

- ✅ **Success**: Provider is fully configured and ready
- ⚠️ **Partial**: Provider has API key but missing BASE_URL (configure it to enable)
- The 8-character hash identifies which API key is being used

### Special Provider Defaults

| Provider | Default BASE_URL | API Key Required |
|----------|------------------|------------------|
| OpenAI   | `https://api.openai.com/v1` | Yes |
| Poe      | `https://api.poe.com/v1` | Yes |
| Others   | None (must be provided) | Yes |

### Troubleshooting

**Q: Why do I see warnings about failed providers?**
A: The proxy only warns about providers that have an API key but are missing configuration. Providers without any configuration are not mentioned.

**Q: How do I check which providers are loaded?**
A: Run `vdm test providers` to see the current provider status.

## Usage Examples

### Basic Chat

```python
import httpx

response = httpx.post(
    "http://localhost:8082/v1/messages",
    json={
        "model": "claude-3-5-sonnet-20241022",  # Passed through unchanged
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
)
```

## Integration with Claude Code

This proxy is designed to work seamlessly with Claude Code CLI:

```bash
# Start the proxy
python start_proxy.py

# Use Claude Code with the proxy
ANTHROPIC_BASE_URL=http://localhost:8082 claude

# Or set permanently
export ANTHROPIC_BASE_URL=http://localhost:8082
claude
```

## Testing

Test proxy functionality and configuration:

```bash
# Run all tests
make test

# Run comprehensive integration tests
make test-integration

# Run unit tests
make test-unit

# Test configuration
vdm test connection

# Test model mappings
vdm test models

# Check API connectivity
vdm health upstream

# Validate configuration
vdm config validate
```

## VDM CLI Reference

The `vdm` command-line tool provides elegant management of the proxy server:

```bash
# Get help
vdm --help

# Start the server
vdm server start
vdm server start --host 0.0.0.0 --port 8082
vdm server start --reload  # Development mode

# Configuration management
vdm config show      # Show current configuration
vdm config validate  # Validate configuration
vdm config env       # Show environment variables
vdm config setup     # Interactive setup

# Health checks
vdm health server    # Check proxy server
vdm health upstream  # Check upstream API

# Testing
vdm test connection  # Test API connectivity
vdm test models      # Test model mappings

# Version info
vdm version
```

## Development

### Using Make (recommended)

```bash
# Initialize development environment
make init-dev

# Run server using CLI
vdm server start

# Run development server with hot reload
make dev

# Format code
make format

# Type checking
make type-check

# Run all code quality checks
make check

# Run tests
make test
```

### Using UV

```bash
# Install dependencies
uv sync --extra cli  # Include CLI dependencies

# Run server using CLI
vdm server start

# Or run directly
uv run python start_proxy.py

# Format code
make format

# Type checking
make type-check

# Run all code quality checks
make check
```

### Project Structure

```
claude-code-proxy/
├── src/
│   ├── main.py                     # Main server
│   ├── test_claude_to_openai.py    # Tests
│   └── [other modules...]
├── start_proxy.py                  # Startup script
├── .env.example                    # Config template
└── README.md                       # This file
```

## Performance

- **Async/await** for high concurrency
- **Connection pooling** for efficiency
- **Streaming support** for real-time responses
- **Configurable timeouts** and retries
- **Smart error handling** with detailed logging

## License

MIT License
