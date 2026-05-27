# Server Startup Output

This document describes the information displayed when starting the Vandamme Proxy server with `vdm server start`.

## Display Sections

The server startup output displays information in the following order:

### 1. Configuration Table

Shows core server settings:

| Setting | Description |
|---------|-------------|
| Server URL | The URL where the proxy is listening |
| Default Target | The Default Target (when a provider is the default) |
| Default Profile | The default profile (when a profile is the default) |
| `{Provider} Base URL` | Base URL for the Default Target (only shown when provider is default) |
| `{Provider} API Key` | Hash of the API key for the Default Target (only shown when provider is default) |
| Bridge | Bridge provider and URL (only shown when `--bridge` is used) |

**Note:** When a profile is set as the default, the Base URL and API Key rows are omitted because profile aliases may point to different providers.

### 2. Aliases Section

Shows configured model aliases with grouping:
- Total count of aliases
- Number of provider-specific aliases
- Number of fallback (default) aliases
- Per-provider alias listings
- Fallback alias listings

### 3. Profiles Section

Shows configured profiles:

| Column | Description |
|--------|-------------|
| Name | Profile name (prefixed with `*` if this is the active/default profile) |
| Timeout | Request timeout in seconds, or "inherited" to use provider default |
| Max Retries | Maximum retry attempts, or "inherited" to use provider default |
| Aliases | Number of aliases defined in this profile |
| Source | Where the profile is defined: "local", "user", or "package" |

**Legend:**
- `* = active/default profile` - The profile that is currently set as the default

### 4. Providers Section

Shows active and configured providers:

| Column | Description |
|--------|-------------|
| Status | ✅ (success) or ❌ (failed/error) |
| SHA256 | First 8 characters of the API key hash |
| Name | Provider name (prefixed with `*` if this is the Default Target) |
| Base URL | The base URL for the provider's API |

**Legend:**
- `* = Default Target` - The provider that is used when no provider prefix is specified
- `🔐 = OAuth authentication` - This provider is configured with OAuth authentication

**Note:** When a profile is set as the default, no provider will show the `*` indicator. Instead, the legend will show `* = Default Target (profile active, no Default Target)`.

## Default Resolution

The Default Target/profile is resolved in the following order:

1. `VDM_DEFAULT_TARGET` environment variable
2. `default_provider` in `vandamme-config.toml`
3. `default_provider` in `~/.config/vandamme-proxy/vandamme-config.toml`
4. Built-in default (first available provider)

## Profile vs Provider as Default

When `VDM_DEFAULT_TARGET` is set to a profile name:
- The configuration table shows "Default Profile"
- The profiles section shows the profile with a `*` indicator
- The providers section shows no `*` indicator (since the profile may use different providers for different aliases)

When `VDM_DEFAULT_TARGET` is set to a provider name:
- The configuration table shows "Default Target" with Base URL and API Key
- The profiles section shows no `*` indicator
- The providers section shows the provider with a `*` indicator
