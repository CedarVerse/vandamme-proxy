# Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies
```bash
# Using UV (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### Step 2: Configure Your Provider

Choose your LLM provider and configure accordingly:

#### OpenAI
```bash
cp .env.example .env
# Edit .env:
# OPENAI_API_KEY="sk-your-openai-key"
```

#### Azure OpenAI
```bash
cp .env.example .env
# Edit .env:
# OPENAI_API_KEY="your-azure-key"
# OPENAI_BASE_URL="https://your-resource.openai.azure.com/openai/deployments/your-deployment"
# AZURE_API_VERSION="2024-02-15-preview"
```

#### Local Models (Ollama)
```bash
cp .env.example .env
# Edit .env:
# OPENAI_API_KEY="dummy-key"
# OPENAI_BASE_URL="http://localhost:11434/v1"
```

### Step 3: Start and Use

```bash
# Start the proxy server
python start_proxy.py

# In another terminal, use with Claude Code
ANTHROPIC_BASE_URL=http://localhost:8082 claude
```

## 🎯 How It Works

| Your Input | Proxy Action | Result |
|-----------|--------------|--------|
| Claude Code sends `claude-3-5-sonnet-20241022` | Passes through unchanged | Provider receives `claude-3-5-sonnet-20241022` |
| Claude Code sends `claude-3-5-haiku-20241022` | Passes through unchanged | Provider receives `claude-3-5-haiku-20241022` |

## 📋 What You Need

- Python 3.9+
- API key for your chosen provider
- Claude Code CLI installed
- 2 minutes to configure

## 🔧 Default Settings
- Server runs on `http://localhost:8082`
- Model names are passed through unchanged
- Supports streaming, function calling, images

## 🧪 Test Your Setup
```bash
# Quick test
python src/test_claude_to_openai.py
```

That's it! Now Claude Code can use any OpenAI-compatible provider! 🎉