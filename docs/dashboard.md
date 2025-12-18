# Vandamme Proxy Dashboard Guide

[![Vandamme Proxy](https://img.shields.io/badge/Vandamme-Dashboard-blue.svg)](https://github.com/CedarVerse/vandamme-proxy)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-green.svg)](https://github.com/CedarVerse/vandamme-proxy)
[![Version](https://img.shields.io/badge/Version-v1.0.0-purple.svg)](https://github.com/CedarVerse/vandamme-proxy)

> **The comprehensive monitoring and management interface for your LLM proxy gateway**

---

## 🚀 Quick Start

Get up and running with the dashboard in seconds:

```bash
# 1. Start the proxy server
vdm server start

# 2. Open dashboard in your browser
open http://localhost:8082/dashboard/

# 3. Explore the features!
#    - Overview: System health at a glance
#    - Metrics: Performance and usage analytics
#    - Models: Browse 332+ available models
#    - Aliases: View configured shortcuts
#    - Token Counter: Estimate costs instantly
```

[Screenshot: Dashboard Overview showing all 5 tabs]

---

## 📊 Dashboard Overview

The Vandamme Proxy Dashboard provides a professional, dark-themed interface for monitoring and managing your LLM proxy instance. Built with Dash and Bootstrap components, it delivers real-time insights into your proxy's performance and configuration.

### Key Capabilities

- 🏥 **Health Monitoring** - Real-time provider status and connectivity
- 📈 **Performance Metrics** - Token usage, response times, error rates
- 🔍 **Model Discovery** - Browse and search across all available models
- 🏷️ **Alias Management** - View and understand model shortcuts
- 💰 **Cost Planning** - Interactive token counting for budget optimization
- ⚙️ **Multi-Provider** - Monitor OpenAI, Anthropic, Poe, Azure, Gemini and more

### Target Audience

This guide serves three primary audiences:
- **End Users** - Learn to effectively use the proxy for your AI workflows
- **Operators** - Monitor system health, performance, and troubleshoot issues
- **Developers** - Understand the architecture and extend functionality

---

## 👥 End-User Guide

### Overview Page

The Overview page provides a quick health check of your proxy instance.

#### Health Banner
- **Overall Status**: System health at a glance
  - ✅ **Healthy** - All systems operational
  - ⚠️ **Degraded** - Some issues detected
  - ❌ **Failed** - Critical problems require attention

#### Provider Status Table
- **Provider Name**: Configured LLM providers
- **API Format**: OpenAI or Anthropic compatible
- **Base URL**: Provider endpoint
- **API Key Hash**: Shows key is configured without exposing it
- **Status**: Connection health indicator

#### Key Performance Indicators (KPIs)
The dashboard displays 10 KPI cards in a responsive grid:
- **Total Requests**: Lifetime request count
- **Input/Output Tokens**: Token consumption metrics
- **Tool Calls**: Number of tool invocations
- **Average Duration**: Response time performance
  - 🟢 **< 500ms**: Excellent performance
  - 🟡 **500-2000ms**: Moderate latency
  - 🔴 **> 2000ms**: Needs investigation
- **Error Rate**: Percentage of failed requests
- **Active Requests**: Currently processing

[Screenshot: Overview Page with health banner, provider table, and KPI grid]

### Token Counter Tool

Estimate your costs before making API requests.

#### Features
- **Model Selection**: Dropdown populated with available models
- **System Message**: Optional context field
- **Real-time Counting**: Updates as you type
- **Multi-turn Support**: Add multiple messages
- **Clear Function**: Reset all fields instantly

#### Usage Example
```bash
# Open the token counter
# Navigate to /dashboard/token-counter

# Select your model (e.g., claude-3-5-sonnet-20241022)

# Enter your message:
"You are a helpful assistant. Please analyze this code and provide feedback."

# View estimated tokens: ~47 tokens
```

[Screenshot: Token Counter with model selector and real-time token display]

### Models Browser

Discover and explore the 332+ available models across all configured providers.

#### Search & Filter
- **Real-time Search**: Find models by name or display name
- **Provider Filter**: View models from specific providers
- **Responsive Cards**: Mobile-friendly model display

#### Model Information
Each model card displays:
- **Model ID**: Exact identifier for API calls
- **Display Name**: Human-readable model name
- **Provider Badge**: Color-coded by provider
- **Creation Date**: When model was added

#### Tips for Finding Models
```bash
# Search for specific capabilities
Search: "vision"     # Find models with image support
Search: "turbo"     # Find fast models
Search: "code"      # Find code-optimized models

# Filter by provider
Provider: "openai"  # See only OpenAI models
Provider: "poe"     # See only Poe models
```

[Screenshot: Models Page with search bar and model cards]

### Aliases Reference

View and understand configured model aliases for quick access.

#### Provider Grouping
Aliases are organized by provider in collapsible sections:
- **poe**: Fast access models (haiku, sonnet, opus)
- **zai**: Alternative provider aliases
- **Custom**: Your configured aliases

#### Understanding Mappings
Each alias shows:
- **Alias Name**: The shortcut you use
- **Maps To**: The actual model it resolves to
- **Provider**: Which provider handles the request

#### Using Aliases
```bash
# Instead of full model names:
claude --model poe:grok-4-fast-non-reasoning "Quick question"

# Use the alias:
claude --model fast "Quick question"  # Maps to grok-4-fast-non-reasoning
```

[Screenshot: Aliases Page with expanded provider sections]

---

## 🛠️ Operator Guide

### Health Monitoring

#### System Health Indicators
- **Provider Connectivity**: Real-time status of each provider
- **API Key Validation**: Shows if keys are properly configured
- **Response Times**: Monitor provider latency
- **Uptime Tracking**: System availability over time

#### Health Check Details
```bash
# Manual health check (same as dashboard)
curl http://localhost:8082/health

# Expected response structure:
status: healthy
timestamp: 2025-12-17T21:30:00Z
providers:
  openai:
    api_format: openai
    base_url: https://api.openai.com/v1
    api_key_hash: sha256:...
  poe:
    api_format: openai
    base_url: https://api.poe.com/v1
    api_key_hash: sha256:...
```

#### Test Connection Feature
The "Run test connection" button performs a live test:
- Sends actual request to default provider
- Tests authentication and connectivity
- Returns detailed success/failure information
- Includes response ID on success

### Performance Metrics

#### Timing Indicators
Color-coded performance helps identify issues quickly:
- 🟢 **Green (< 500ms)**: Excellent performance
- 🟡 **Yellow (500-2000ms)**: Acceptable but monitoring
- 🔴 **Red (> 2000ms)**: Requires immediate attention

#### KPI Interpretation
- **Request Volume**: High traffic vs. expected
- **Error Rate**: Spikes indicate provider issues
- **Average Duration**: Trends over time
- **Streaming vs Non-streaming**: Performance comparison

[Screenshot: Metrics Page with color-coded timing indicators]

#### Provider Management
Monitor multiple providers effectively:
- **Response Time Comparison**: Identify fastest providers
- **Success Rates**: Track reliability
- **Cost Efficiency**: Token usage per provider
- **Failover Events**: Automatic switches visible

### Alerting & Troubleshooting

#### Common Performance Issues
1. **High Response Times**
   - Check provider status pages
   - Verify API key limits
   - Consider provider failover

2. **Error Rate Spikes**
   - Review recent provider changes
   - Check rate limits
   - Validate API key validity

3. **Models Not Loading**
   - Verify provider configuration
   - Check network connectivity
   - Review provider-specific settings

#### Diagnostic Commands
```bash
# Check proxy status
curl -v http://localhost:8082/health

# Test specific provider
curl -H "x-api-key: YOUR_KEY" \
     http://localhost:8082/test-connection

# View provider models
curl http://localhost:8082/v1/models?provider=openai

# Check metrics with filter
curl "http://localhost:8082/metrics/running-totals?provider=poe"

# Enable debug logging
LOG_LEVEL=DEBUG vdm server start
```

---

## 👨‍💻 Developer Guide

### Architecture Overview

```
FastAPI Server (http://localhost:8082)
├── /dashboard (WSGI mount)
│   ├── Dash Application
│   │   ├── Layout & Navigation
│   │   ├── Callbacks (Real-time updates)
│   │   └── State Management
│   ├── Pages/
│   │   ├── Overview (Health, KPIs, Provider status)
│   │   ├── Metrics (Charts, Tables, Filters)
│   │   ├── Models (Search, Cards, Pagination)
│   │   ├── Aliases (Groups, Mappings, Search)
│   │   └── Token Counter (Interactive tool)
│   └── Components/
│       ├── UI (Reusable elements)
│       ├── Data Sources (API clients)
│       └── Normalization (Data transformation)
└── API Endpoints
    ├── /health (YAML) - System status
    ├── /v1/models (JSON) - Available models
    ├── /v1/aliases (JSON) - Model shortcuts
    ├── /v1/messages (JSON) - Chat completions
    ├── /metrics/running-totals (YAML) - Usage stats
    └── /test-connection (JSON) - Connectivity test
```

### API Integration

Direct access to dashboard data sources:

```bash
# System health (YAML format)
curl http://localhost:8082/health

# Available models (JSON format)
curl http://localhost:8082/v1/models | jq '.data | length'
# Returns: 332

# Model aliases (JSON format)
curl http://localhost:8082/v1/aliases | jq '.total'
# Returns: 6

# Running metrics (YAML format)
curl http://localhost:8082/metrics/running-totals

# Test connectivity (JSON format)
curl http://localhost:8082/test-connection
```

### Customization

#### Adding New Pages
1. Create layout function in `src/dashboard/pages.py`
```python
def my_custom_page() -> dbc.Container:
    return dbc.Container([
        dbc.Row(dbc.Col(html.H2("My Custom Page"))),
        # Add your components here
    ], fluid=True, className="py-3")
```

2. Add route in `src/dashboard/app.py`
```python
if pathname == "/dashboard/my-custom":
    return my_custom_page()
```

3. Add navigation link
```python
dbc.NavLink("My Custom", href="/dashboard/my-custom", active="exact")
```

#### Custom Components
Create reusable UI components in `src/dashboard/components/ui.py`:
```python
def my_component(data: dict[str, Any]) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([
            html.H4(data.get("title")),
            html.P(data.get("description"))
        ])
    )
```

#### Extending Metrics
Add new data sources in `src/dashboard/data_sources.py`:
```python
async def fetch_my_metrics(*, cfg: DashboardConfig) -> dict[str, Any]:
    url = f"{cfg.api_base_url}/my-custom-endpoint"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return resp.json()
```

### Testing

#### Unit Tests
Test individual components and data sources:
```bash
# Run dashboard unit tests
make test-unit tests/dashboard/

# Test specific file
python -m pytest tests/dashboard/test_normalize.py -v
```

#### Dashboard Smoke Tests
```python
# From tests/dashboard/test_dashboard_app.py
def test_dashboard_creation():
    cfg = DashboardConfig(api_base_url="http://localhost:8082")
    app = create_dashboard(cfg=cfg)
    assert app is not None
```

#### API Endpoint Testing
```python
# Test data sources directly
import asyncio
from src.dashboard.data_sources import fetch_models

async def test_models_endpoint():
    cfg = DashboardConfig(api_base_url="http://localhost:8082")
    models = await fetch_models(cfg=cfg)
    assert models.get("object") == "list"
    assert len(models.get("data", [])) > 0
```

---

## 🔧 Advanced Features

### Real-time Updates

The dashboard updates automatically with configurable intervals:

#### Polling Controls
- **Metrics Page**: Toggle polling on/off
- **Intervals**: 5s, 10s, 30s options
- **Overview**: Fixed 10s interval
- **Models/Aliases**: 30s/60s intervals

#### Performance Considerations
- Minimal overhead (~10KB per refresh)
- Can disable polling in production
- Uses existing API endpoints (no additional load)

### Multi-Provider Monitoring

#### Provider Comparison
- Response time rankings
- Success rate comparison
- Cost per token analysis
- Geographic distribution effects

#### Failover Visualization
- Automatic switch events visible
- Primary/secondary provider status
- Load distribution across keys

### Export & Automation

#### Data Export Options
```bash
# Export metrics as YAML
curl http://localhost:8082/metrics/running-totals > metrics.yaml

# Export models list as JSON
curl http://localhost:8082/v1/models > models.json

# Export aliases configuration
curl http://localhost:8082/v1/aliases > aliases.json
```

#### Cron-based Monitoring
```bash
#!/bin/bash
# health-check.sh
RESPONSE=$(curl -s http://localhost:8082/health)
if echo "$RESPONSE" | grep -q "status: degraded"; then
    echo "Alert: Proxy is degraded!" | mail -s "Vandamme Alert" admin@example.com
fi
```

#### Grafana Integration
- Use `/metrics/running-totals` endpoint
- Parse YAML format for time-series data
- Create dashboards for provider performance

---

## 📚 Reference Section

### Quick Commands Cheat Sheet

```bash
# Dashboard access
open http://localhost:8082/dashboard/

# System health check
curl http://localhost:8082/health

# List all models
curl http://localhost:8082/v1/models | jq '.data | length'
# Output: 332

# View model aliases
curl http://localhost:8082/v1/aliases | jq '.aliases'
# Output: { "poe": {...}, "zai": {...} }

# Get running totals
curl http://localhost:8082/metrics/running-totals

# Test connectivity
curl http://localhost:8082/test-connection

# Check specific provider models
curl "http://localhost:8082/v1/models?provider=poe"

# Metrics with filters
curl "http://localhost:8082/metrics/running-totals?provider=openai&model=gpt*"
```

### Configuration Impact

#### Required Settings for Full Functionality
- **LOG_REQUEST_METRICS=true**: Enables metrics collection
- **{PROVIDER}_API_KEY**: At least one provider configured
- **PORT**: Default 8082 (dashboard adjusts automatically)

#### Optional Enhancements
- **VDM_DEFAULT_PROVIDER**: Sets default for test connection
- **LOG_LEVEL=DEBUG**: Detailed dashboard troubleshooting
- **PROXY_API_KEY**: Dashboard access control

### Related Documentation

- **[Model Aliases](model-aliases.md)** - Configure smart model shortcuts
- **[Provider Routing](provider-routing-guide.md)** - Multi-provider setup
- **[Multi-API Keys](multi-api-keys.md)** - High availability configuration
- **[API Key Passthrough](api-key-passthrough.md)** - Multi-tenant deployments
- **[Makefile Workflows](makefile-workflows.md)** - Development and testing

---

## ❓ Troubleshooting FAQ

### Dashboard Not Loading

**Issue**: Browser shows "Not Found" error
```bash
# Check if proxy is running
curl http://localhost:8082/health

# Check dashboard mount
curl http://localhost:8082/dashboard/

# View server logs
vdm server start --log-level DEBUG
```

**Solution**: Ensure proxy server is running and dashboard dependencies installed

### Metrics Showing Zeros

**Issue**: All KPIs show 0 values
```bash
# Check if metrics are enabled
grep LOG_REQUEST_METRICS .env

# Verify endpoint access
curl http://localhost:8082/metrics/running-totals
```

**Solution**: Set `LOG_REQUEST_METRICS=true` in environment or .env file

### Models Not Appearing

**Issue**: Models page shows "No models found"
```bash
# Test models endpoint directly
curl http://localhost:8082/v1/models

# Check provider configuration
curl http://localhost:8082/health | jq '.providers'
```

**Solution**: Verify provider API keys and base URLs are correctly configured

### Performance Issues

**Issue**: Dashboard loads slowly or times out
```bash
# Check response times
time curl http://localhost:8082/health

# Monitor resource usage
htop | grep python
```

**Common Causes**:
- Slow provider response times
- Network connectivity issues
- Large provider model lists
- Metrics collection overhead

**Solutions**:
- Increase polling intervals
- Disable unused providers
- Optimize network routes

### Permission Errors

**Issue**: 401 Unauthorized errors
```bash
# Check if proxy API key is required
curl -I http://localhost:8082/health

# Test with API key if configured
curl -H "x-api-key: YOUR_KEY" http://localhost:8082/dashboard/
```

**Solution**: Provide correct `PROXY_API_KEY` or disable authentication

### Browser Compatibility

**Supported Browsers**:
- ✅ Chrome/Chromium (Recommended)
- ✅ Firefox (Full support)
- ⚠️ Safari (Partial support)
- ❌ Internet Explorer (Not supported)

**Requirements**:
- JavaScript must be enabled
- Modern browser with ES6 support
- WebSocket support for real-time features

---

## 🎯 Getting Help

For additional support:
1. **Check the logs**: `vdm server start --log-level DEBUG`
2. **Review related docs**: See Related Documentation section
3. **Search issues**: [GitHub Issues](https://github.com/CedarVerse/vandamme-proxy/issues)
4. **Community**: Join discussions in GitHub Discussions

---

*Last updated: 2025-12-17*
*Dashboard version: v1.0.0*