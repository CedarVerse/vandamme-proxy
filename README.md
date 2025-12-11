# Vandamme Proxy

**The Universal LLM Gateway for Multi-Provider AI Development**

[![ci](https://github.com/CedarVerse/vandamme-proxy/actions/workflows/ci.yml/badge.svg)](https://github.com/CedarVerse/vandamme-proxy/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/vandamme-proxy)](https://pypi.org/project/vandamme-proxy/)
[![Python](https://img.shields.io/pypi/pyversions/vandamme-proxy)](https://pypi.org/project/vandamme-proxy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Transform any AI client into a powerful command center for OpenAI, Anthropic, Poe, Azure, Gemini, and any compatible API. Supercharge Claude Code CLI with intelligent routing, smart aliases, and zero-configuration provider switching.

---

## Why Vandamme Proxy?

### 🚀 For Claude Code Users

Break free from single-provider limitations. Route requests to any LLM provider with simple model prefixes:

```bash
claude --model openai:gpt-4o "Analyze this code"
claude --model poe:gemini-flash "Quick question"
claude --model fast "Fast response needed"  # Smart alias
```

### 🌐 For LLM Gateway Users

A lightweight, production-ready proxy with:
- **Zero-Configuration Discovery** - Providers auto-configured from environment variables
- **Dual API Format Support** - Native OpenAI conversion + Anthropic passthrough
- **Smart Model Aliases** - Case-insensitive substring matching for cleaner workflows
- **Secure API Key Passthrough** - Multi-tenant deployments with `!PASSTHRU` sentinel
- **Extensible Middleware** - Chain-of-responsibility pattern for custom logic

---

## Features at a Glance

### Core Capabilities
- **Universal Provider Support** - OpenAI, Anthropic, Poe, Azure OpenAI, Google Gemini, AWS Bedrock, Google Vertex AI, or any OpenAI/Anthropic-compatible API
- **Dynamic Provider Routing** - Route by model prefix (`provider:model`) with automatic fallback to default provider
- **Smart Model Aliases** - `VDM_ALIAS_*` with case-insensitive substring matching ([Learn more →](docs/model-aliases.md))
- **Dual API Formats** - Native OpenAI conversion + Anthropic passthrough in one instance ([Learn more →](ANTHROPIC_API_SUPPORT.md))

### Security & Multi-Tenancy
- **Secure API Key Passthrough** - `!PASSTHRU` sentinel for client-provided keys ([Learn more →](docs/api-key-passthrough.md))
- **Mixed-Mode Authentication** - Static keys + passthrough simultaneously per provider
- **Per-Provider Configuration** - Isolated settings, custom headers, API versions

### Developer Experience
- **Powerful CLI (`vdm`)** - Server management, health checks, configuration validation
- **Auto-Discovery** - Providers configured via `{PROVIDER}_API_KEY` environment variables
- **Production Features** - Metrics endpoints, observability, connection pooling, full streaming support
- **Extensible Middleware** - Built-in support for Google Gemini thought signatures, easy to extend

---

## How It Works

```
┌──────────────────────────────────────────────────────┐
│            Your AI Application                       │
│      (Claude Code CLI, Custom Clients)               │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
       ┌───────────────────────────────────┐
       │    Vandamme Proxy Gateway         │
       │    http://localhost:8082          │
       │                                   │
       │  ┌─────────────────────────────┐ │
       │  │  Smart Alias Engine         │ │
       │  │  "fast" → "poe:gemini-flash"│ │
       │  └─────────────────────────────┘ │
       │                                   │
       │  ┌─────────────────────────────┐ │
       │  │  Dynamic Provider Router    │ │
       │  │  Dual Format Handler        │ │
       │  └─────────────────────────────┘ │
       └───────────────┬───────────────────┘
                       │
       ┌───────────────┼────────────┬─────────────┐
       │               │            │             │
       ▼               ▼            ▼             ▼
   ┌────────┐     ┌─────────┐  ┌────────┐   ┌─────────┐
   │ OpenAI │     │Anthropic│  │  Poe   │   │  Azure  │
   │        │     │ Format: │  │(!PASS  │   │ Gemini  │
   │ Static │     │Anthropic│  │ THRU)  │   │ Custom  │
   │  Key   │     │         │  │        │   │         │
   └────────┘     └─────────┘  └────────┘   └─────────┘
```

**Request Flow:**
1. Client sends request to Vandamme Proxy
2. Smart alias resolution (if applicable)
3. Provider routing based on model prefix
4. Format selection (OpenAI conversion vs Anthropic passthrough)
5. Response transformation and middleware processing

---

## 🚀 Quick Start

### Installation

```bash
# Using pip (recommended)
pip install vandamme-proxy

# Or using uv (fastest)
uv pip install vandamme-proxy

# Verify CLI is available
vdm version
```

### Configure Providers

```bash
# Interactive setup (recommended)
vdm config setup

# Or manually create .env file
cat > .env << 'EOF'
# Provider API Keys
OPENAI_API_KEY=sk-your-openai-key
POE_API_KEY=!PASSTHRU  # Client provides key per-request
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_API_FORMAT=anthropic  # Direct passthrough (no conversion)

# Smart Aliases
VDM_ALIAS_FAST=poe:gemini-flash
VDM_ALIAS_CHAT=anthropic:claude-3-5-sonnet-20241022
VDM_ALIAS_CODE=openai:gpt-4o

# Default Provider (when no prefix specified)
VDM_DEFAULT_PROVIDER=openai
EOF
```

### Start the Server

```bash
# Development mode (hot reload)
vdm server start --reload

# Production mode
vdm server start --host 0.0.0.0 --port 8082
```

### Use with Claude Code CLI

```bash
# Point Claude Code to the proxy
export ANTHROPIC_BASE_URL=http://localhost:8082

# Use provider routing
claude --model openai:gpt-4o "Analyze this code"
claude --model poe:gemini-flash "Quick question"

# Use smart aliases
claude --model fast "Fast response needed"
claude --model chat "Deep conversation"

# For passthrough providers (!PASSTHRU), provide your API key
ANTHROPIC_API_KEY=your-poe-key claude --model poe:gemini-flash "..."
```

### Verify Your Setup

```bash
# Check server health
vdm health server

# Test upstream provider connectivity
vdm health upstream

# Show current configuration
vdm config show

# View active model aliases
curl http://localhost:8082/v1/aliases
```

**Next Steps:**
- 📚 [Detailed Setup Guide](QUICKSTART.md)
- 🔧 [Development Workflows](docs/makefile-workflows.md)

---

## 📖 Core Concepts

### Provider Prefix Routing

Route requests by prefixing model names with the provider identifier:

```bash
# Format: provider:model_name
claude --model openai:gpt-4o         # Routes to OpenAI
claude --model poe:gemini-flash      # Routes to Poe
claude --model anthropic:claude-3    # Routes to Anthropic
claude --model gpt-4o                # Routes to VDM_DEFAULT_PROVIDER
```

Providers are auto-discovered from environment variables:
- `OPENAI_API_KEY` → creates "openai" provider
- `POE_API_KEY` → creates "poe" provider
- `CUSTOM_API_KEY` → creates "custom" provider

**[Complete Routing Guide →](docs/provider-routing-guide.md)**

---

### Smart Model Aliases

Create memorable shortcuts with powerful substring matching:

```bash
# .env configuration
VDM_ALIAS_FAST=poe:gemini-flash
VDM_ALIAS_HAIKU=poe:gpt-4o-mini
VDM_ALIAS_CHAT=anthropic:claude-3-5-sonnet-20241022
```

**Intelligent Matching Rules:**
- **Case-Insensitive:** `fast`, `Fast`, `FAST` all match
- **Substring Matching:** `my-fast-model` matches `FAST` alias
- **Hyphen/Underscore:** `my-alias` and `my_alias` both match `VDM_ALIAS_MY_ALIAS`
- **Priority Order:** Exact match → Longest substring → Alphabetical

**[Model Aliases Guide →](docs/model-aliases.md)**

---

### Dual API Format Support

**OpenAI Format (default):**
```bash
PROVIDER_API_FORMAT=openai  # Requests converted to/from OpenAI format
```

**Anthropic Format (passthrough):**
```bash
PROVIDER_API_FORMAT=anthropic  # Zero conversion overhead, direct passthrough
```

**Mix formats in a single instance:**
```bash
OPENAI_API_FORMAT=openai         # Conversion mode
ANTHROPIC_API_FORMAT=anthropic   # Passthrough mode
BEDROCK_API_FORMAT=anthropic     # AWS Bedrock passthrough
```

This enables using Claude natively on AWS Bedrock, Google Vertex AI, or any Anthropic-compatible endpoint without conversion overhead.

**[Anthropic API Support Guide →](ANTHROPIC_API_SUPPORT.md)**

---

### Secure API Key Passthrough

Enable client-provided API keys with the `!PASSTHRU` sentinel:

```bash
# Proxy stores and uses a static API key
OPENAI_API_KEY=sk-your-static-key

# Client provides their own key per-request
POE_API_KEY=!PASSTHRU
```

**Use Cases:**
- **Multi-Tenant Deployments** - Each client uses their own API keys
- **Cost Distribution** - Clients pay for their own API usage
- **Client Autonomy** - Users maintain control of their credentials
- **Gradual Migration** - Move providers to passthrough one at a time

**[API Key Passthrough Guide →](docs/api-key-passthrough.md)**

---

## Vandamme Proxy vs Alternatives

| Feature | Vandamme Proxy | LiteLLM | OpenRouter |
|---------|---------------|---------|------------|
| **Provider Routing** | ✅ Prefix-based (`provider:model`) | ✅ Config-based | ✅ Unified namespace |
| **Smart Aliases** | ✅ Substring matching + priorities | ❌ Exact match only | ❌ Not supported |
| **Dual API Formats** | ✅ OpenAI + Anthropic native | ✅ OpenAI only | ✅ OpenAI only |
| **API Key Passthrough** | ✅ `!PASSTHRU` sentinel | ⚠️ Limited support | ✅ Native support |
| **Mixed Auth Modes** | ✅ Static + Passthrough per-provider | ❌ Global only | ❌ Global only |
| **Middleware System** | ✅ Chain-of-responsibility | ⚠️ Limited hooks | ❌ Not extensible |
| **Claude Code Integration** | ✅ Zero-config | ⚠️ Manual setup | ⚠️ Manual setup |
| **Self-Hosted** | ✅ Full control | ✅ Full control | ❌ Cloud service only |
| **vdm CLI** | ✅ Integrated tooling | ❌ Not provided | ❌ Not provided |

### When to Choose Vandamme Proxy

**Choose Vandamme if you:**
- Use Claude Code CLI and want seamless multi-provider support
- Need flexible per-provider API key passthrough for multi-tenant scenarios
- Want smart model aliases with substring matching
- Require Anthropic-format native passthrough (AWS Bedrock, Google Vertex AI)
- Prefer lightweight design with minimal dependencies
- Want extensible middleware for custom request/response logic

**Choose LiteLLM if you:**
- Need enterprise-grade load balancing and automatic failover
- Require extensive logging and observability integrations
- Want managed caching layers and retry strategies

**Choose OpenRouter if you:**
- Prefer a managed cloud service over self-hosting
- Want access to exclusive model partnerships and providers
- Don't require self-hosted infrastructure

---

## 📚 Documentation

### Getting Started
- 📚 [Quick Start Guide](QUICKSTART.md) - Get running in 5 minutes
- 🏗️ [Architecture Overview](CLAUDE.md) - Deep dive into design decisions
- 🔧 [Development Workflows](docs/makefile-workflows.md) - Makefile targets and best practices

### Feature Guides
- 🌐 [Multi-Provider Routing](docs/provider-routing-guide.md) - Complete routing and configuration guide
- 🏷️ [Smart Model Aliases](docs/model-aliases.md) - Alias configuration and matching rules
- 🔑 [API Key Passthrough](docs/api-key-passthrough.md) - Security and multi-tenancy patterns
- 🔄 [Anthropic API Support](ANTHROPIC_API_SUPPORT.md) - Dual-format operation details

### Reference
- **API Endpoints:**
  - `POST /v1/messages` - Chat completions
  - `POST /v1/messages/count_tokens` - Token counting
  - `GET /v1/models` - List available models
  - `GET /v1/aliases` - View active model aliases
  - `GET /health` - Health check with provider status
  - `GET /metrics/running-totals` - Usage metrics

---

## 🛠️ Development

### Setup

```bash
# Initialize development environment
make init-dev

# Start development server with hot reload
make dev
```

### Testing

```bash
# Run all tests
make test

# Run code quality checks
make check

# Format code
make format
```

### Contributing

We welcome contributions! Please see our development guide for details on:
- Setting up your development environment
- Running tests and quality checks
- Submitting pull requests

**[Complete Development Guide →](docs/makefile-workflows.md)**

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Community

- **Issues:** [GitHub Issues](https://github.com/CedarVerse/vandamme-proxy/issues)
- **Repository:** [GitHub](https://github.com/CedarVerse/vandamme-proxy)

---

Built with ❤️ for the AI development community
