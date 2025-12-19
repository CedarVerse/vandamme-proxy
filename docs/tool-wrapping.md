# Tool Wrapping with VDM

This guide explains how to use the `vdm wrap` command to seamlessly run CLI tools through the Vandamme proxy.

## Overview

The `vdm wrap` command automatically manages the proxy server lifecycle and configures CLI tools to use it. This provides a transparent way to route tool requests through the proxy without manual configuration.

## Key Features

- **Automatic Proxy Management**: Starts the proxy if needed, reuses existing instances
- **Intelligent Argument Processing**: Only processes `--port` and `--host` arguments, passes everything else through
- **Clean Shutdown**: Automatically stops the proxy when the wrapped tool exits (only if wrap started it)
- **Multiple Tool Support**: Works with Claude, Gemini, and other tools
- **Concurrent Sessions**: Multiple terminal windows share the same proxy instance

## Usage

### Basic Syntax

```bash
vdm wrap <tool> [wrap-options] [tool-arguments]
```

- `<tool>`: The CLI tool to wrap (e.g., `claude`, `gemini`)
- `[wrap-options]`: Options for the wrap command (currently `--port` and `--host`)
- `[tool-arguments]`: All other arguments are passed through to the tool

### Examples

#### Basic Claude Usage

```bash
# Start Claude through the proxy
vdm wrap claude

# Pass arguments to Claude
vdm wrap claude --model sonnet --dangerously-skip-permissions

# Use custom proxy port
vdm wrap claude --port 9999 --model opus

# Use custom host and port
vdm wrap claude --host 127.0.0.1 --port 8083
```

#### Using the claude.vdm Alias

For convenience, a `claude.vdm` command is available that automatically wraps Claude:

```bash
# Same as 'vdm wrap claude'
claude.vdm

# Pass arguments directly
claude.vdm --model sonnet --help

# With wrap-specific arguments
claude.vdm --port 9999 --model haiku
```

#### Gemini Support

```bash
# Wrap Gemini CLI
vdm wrap gemini

# With custom port
vdm wrap gemini --port 8083
```

## Wrap Options

The wrap command recognizes only these arguments:

- `--port <number>`: Override the proxy port for this session (temporary)
- `--host <address>`: Override the proxy host for this session (temporary)

All other arguments are passed through unchanged to the wrapped tool.

## Proxy Lifecycle

### First Run

When you run `vdm wrap` for the first time:
1. It checks if the proxy is already running
2. If not running, it starts the proxy automatically
3. Tracks that it started the proxy for cleanup

### Subsequent Runs

When you run `vdm wrap` in another terminal:
1. It detects the existing proxy instance
2. Reuses the running proxy
3. Does not shut down the proxy on exit

### Cleanup

- The proxy is only shut down if the wrap command started it
- If the proxy was already running, it remains running
- Multiple wrap sessions can share the same proxy instance

## Configuration

The wrap command uses the existing proxy configuration:

- Default host: `127.0.0.1` (or `HOST` environment variable)
- Default port: `8082` (or `PORT` environment variable)
- Wrap-specific options (`--port`, `--host`) are temporary overrides

No additional configuration is needed for the wrap command itself.

## Settings Files

### Claude Settings

The Claude wrapper creates a minimal settings file automatically:

```json
{}
```

Or optionally with a default model:
```json
{
  "model": "sonnet"
}
```

The settings file is created in a temporary location and cleaned up automatically.

### Model Resolution

Model aliases are handled by the proxy, not the wrap command. For example:

```bash
vdm wrap claude --model haiku
```

The proxy will resolve "haiku" to the actual model name based on your provider configuration.

## Troubleshooting

### Proxy Won't Start

If the proxy fails to start:
1. Check if the port is already in use
2. Try a different port with `--port`
3. Check your proxy configuration (API keys, etc.)

```bash
# Try with a different port
vdm wrap claude --port 9999
```

### Tool Not Found

If you get an "Unknown tool" error:
```bash
Error: Unknown tool 'toolname'. Supported tools: claude, gemini
```

Check that you're using a supported tool name.

### Proxy Already Running on Different Port

If you have a proxy running on a different port:
```bash
# Specify the port of the running proxy
vdm wrap claude --port 9999
```

### Connection Issues

If the wrapped tool can't connect:
1. Verify the proxy is running: `curl http://127.0.0.1:8082/health`
2. Check your API key configuration
3. Look at the proxy logs for errors

## Best Practices

1. **Use the alias**: For Claude, prefer `claude.vdm` for convenience
2. **Port consistency**: Use the same port across sessions to avoid multiple proxy instances
3. **Check logs**: Enable verbose logging with `-v` to debug issues
4. **Cleanup**: The wrap command handles cleanup automatically, no manual intervention needed

## Adding Support for New Tools

To add support for a new tool:

1. Create a new wrapper class in `src/cli/wrap/wrappers.py`
2. Implement the required methods:
   - `get_tool_command()`: Return the base command
   - `prepare_environment()`: Set up environment variables
   - `create_settings_file()`: Create any needed config files

Example:
```python
class NewToolWrapper(BaseWrapper):
    def get_tool_command(self) -> List[str]:
        return ["newtool"]

    def prepare_environment(self, extra_args: List[str]) -> dict:
        env = os.environ.copy()
        env["NEWTOOL_API_BASE_URL"] = self.proxy_url
        return env

# Register the wrapper
def get_wrapper(tool_name: str, proxy_url: str) -> Optional[BaseWrapper]:
    wrappers = {
        "claude": ClaudeWrapper,
        "gemini": GeminiWrapper,
        "newtool": NewToolWrapper,  # Add this
    }
    # ... rest of function
```