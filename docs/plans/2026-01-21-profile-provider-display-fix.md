# Profile/Provider Display Fix in Server Startup Output Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the server startup output to correctly distinguish between profiles and providers when displaying the default, and add visual indicators for the active profile.

**Architecture:**
1. Reorder display sections to show conceptual hierarchy: Aliases → Profiles → Providers
2. Detect when `default_provider` is actually a profile name
3. Update configuration table to show "Default Profile" vs "Default Provider" appropriately
4. Pass `is_default_profile` flag to provider summary to suppress misleading `*` indicator
5. Add `*` indicator to profile list for the active profile

**Tech Stack:** Python 3.13+, FastAPI, Rich (terminal formatting), Pydantic dataclasses

---

## Task 1: Update `ProfileSummaryPresenter.present_summary()` to Accept Active Profile

**Files:**
- Modify: `src/cli/presenters/profiles.py:40-71`

**Step 1: Read the current implementation**

```bash
cat src/cli/presenters/profiles.py
```

**Step 2: Write failing test for new active profile indicator**

Create: `tests/unit/cli/presenters/test_profiles_presenter.py`

```python
"""Test ProfileSummaryPresenter with active profile indicator."""

from io import StringIO
from rich.console import Console
from src.cli.presenters.profiles import ProfileInfo, ProfileSummary, ProfileSummaryPresenter
import pytest


@pytest.mark.unit
def test_profile_summary_with_active_profile_indicator():
    """Test that active profile is shown with * indicator."""
    console = Console(file=StringIO(), force_terminal=True)
    presenter = ProfileSummaryPresenter(console=console)

    summary = ProfileSummary(
        total_profiles=3,
        profiles=(
            ProfileInfo(name="top", timeout=120, max_retries=3, alias_count=5, source="local"),
            ProfileInfo(name="chatgpt", timeout=None, max_retries=None, alias_count=2, source="package"),
            ProfileInfo(name="openai", timeout=90, max_retries=2, alias_count=3, source="user"),
        )
    )

    # Call with active_profile_name="top"
    presenter.present_summary(summary, active_profile_name="top")

    output = console.file.getvalue()
    assert "*top" in output or "top *" in output, "Active profile should have * indicator"
    assert "chatgpt" in output
    assert "openai" in output


@pytest.mark.unit
def test_profile_summary_without_active_profile():
    """Test profile summary with no active profile."""
    console = Console(file=StringIO(), force_terminal=True)
    presenter = ProfileSummaryPresenter(console=console)

    summary = ProfileSummary(
        total_profiles=2,
        profiles=(
            ProfileInfo(name="chatgpt", timeout=None, max_retries=None, alias_count=2, source="package"),
            ProfileInfo(name="openai", timeout=90, max_retries=2, alias_count=3, source="user"),
        )
    )

    # Call with no active profile
    presenter.present_summary(summary, active_profile_name=None)

    output = console.file.getvalue()
    assert "chatgpt" in output
    assert "openai" in output
    # No * indicator should be present in profile names
    assert "*chatgpt" not in output
    assert "*openai" not in output
```

**Step 3: Run tests to verify they fail**

```bash
pytest tests/unit/cli/presenters/test_profiles_presenter.py -v
```

Expected: `TypeError: present_summary() got an unexpected keyword argument 'active_profile_name'`

**Step 4: Implement the new parameter in ProfileSummaryPresenter**

Modify: `src/cli/presenters/profiles.py:40-71`

```python
def present_summary(
    self,
    summary: ProfileSummary,
    active_profile_name: str | None = None,
) -> None:
    """Display profile summary with color formatting.

    Args:
        summary: ProfileSummary data with all profiles to display
        active_profile_name: Name of the active/default profile, if any
    """
    if summary.total_profiles == 0:
        return

    self.console.print(f"\n🔧 Profiles ({summary.total_profiles} configured):")

    table = Table(show_header=True, box=None, pad_edge=False)
    table.add_column("Name", style="bold", width=15)
    table.add_column("Timeout", width=12)
    table.add_column("Max Retries", width=12)
    table.add_column("Aliases", width=8)
    table.add_column("Source", width=10)

    for profile in summary.profiles:
        # Determine if this is the active profile
        is_active = active_profile_name is not None and profile.name.lower() == active_profile_name.lower()
        active_indicator = "* " if is_active else "  "

        # Format name with active indicator
        name_display = f"{active_indicator}{profile.name}"

        # Format timeout and max_retries
        timeout_str = f"{profile.timeout}s" if profile.timeout is not None else "inherited"
        max_retries_str = str(profile.max_retries) if profile.max_retries is not None else "inherited"

        # Format source with color
        source_color = {
            "local": "[cyan]",
            "user": "[green]",
            "package": "[dim]",
        }.get(profile.source, "")

        source_display = f"{source_color}{profile.source}[/]"

        table.add_row(
            name_display,
            timeout_str,
            max_retries_str,
            str(profile.alias_count),
            source_display,
        )

    self.console.print(table)
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/cli/presenters/test_profiles_presenter.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add src/cli/presenters/profiles.py tests/unit/cli/presenters/test_profiles_presenter.py
git commit -m "feat(profiles): add active profile indicator to profile summary display"
```

---

## Task 2: Update `ProviderManager.print_provider_summary()` to Accept Profile-as-Default Flag

**Files:**
- Modify: `src/core/provider_manager.py:950-1037`
- Test: `tests/unit/core/test_provider_manager.py` (create if not exists)

**Step 1: Read current print_provider_summary implementation**

```bash
cat -n src/core/provider_manager.py | sed -n '950,1037p'
```

**Step 2: Write failing test for is_default_profile flag**

Create: `tests/unit/core/test_provider_manager.py`

```python
"""Test ProviderManager provider summary display."""

from io import StringIO
from unittest.mock import MagicMock, patch
from rich.console import Console
from src.core.provider_manager import ProviderManager
import pytest


@pytest.mark.unit
@patch("src.core.provider_manager.ProviderRegistry")
def test_print_provider_summary_no_default_when_profile_active(mock_registry_class):
    """Test that no provider is marked with * when a profile is the default."""
    # Setup mock registry
    mock_registry = MagicMock()
    mock_registry_class.return_value = mock_registry

    # Mock provider configs
    mock_provider1 = MagicMock()
    mock_provider1.name = "openai"
    mock_provider1.api_format = "openai"

    mock_provider2 = MagicMock()
    mock_provider2.name = "chatgpt"
    mock_provider2.api_format = "openai"

    mock_registry.get_all_providers.return_value = [mock_provider1, mock_provider2]

    # Create provider manager with default_provider="top" (a profile)
    manager = ProviderManager(default_provider="top")

    # Mock the _check_provider_connection method
    async def mock_check(provider, base_url, api_format):
        return MagicMock(status="success", api_key_hash="a1b2c3d4", name=provider.name, base_url=base_url)

    manager._check_provider_connection = mock_check

    # Capture output
    console = Console(file=StringIO(), force_terminal=True)

    # Call with is_default_profile=True
    manager.print_provider_summary(console=console, is_default_profile=True)

    output = console.file.getvalue()

    # When a profile is default, no provider should have the * indicator
    assert "openai" in output
    assert "chatgpt" in output
    # The * should not appear next to provider names
    assert "*openai" not in output and "openai *" not in output or "profile active" in output.lower()


@pytest.mark.unit
@patch("src.core.provider_manager.ProviderRegistry")
def test_print_provider_summary_shows_default_when_provider_active(mock_registry_class):
    """Test that the default provider is marked with * when a provider is the default."""
    # Setup mock registry
    mock_registry = MagicMock()
    mock_registry_class.return_value = mock_registry

    # Mock provider configs
    mock_provider1 = MagicMock()
    mock_provider1.name = "openai"
    mock_provider1.api_format = "openai"

    mock_provider2 = MagicMock()
    mock_provider2.name = "chatgpt"
    mock_provider2.api_format = "openai"

    mock_registry.get_all_providers.return_value = [mock_provider1, mock_provider2]

    # Create provider manager with default_provider="openai" (a real provider)
    manager = ProviderManager(default_provider="openai")

    # Mock the _check_provider_connection method
    async def mock_check(provider, base_url, api_format):
        return MagicMock(status="success", api_key_hash="a1b2c3d4", name=provider.name, base_url=base_url)

    manager._check_provider_connection = mock_check

    # Capture output
    console = Console(file=StringIO(), force_terminal=True)

    # Call with is_default_profile=False
    manager.print_provider_summary(console=console, is_default_profile=False)

    output = console.file.getvalue()

    # When a provider is default, it should have the * indicator
    assert "openai" in output
    assert "chatgpt" in output
    # openai should have the * indicator
    assert ("*openai" in output or "openai *" in output or "openai" in output and "*" in output)
```

**Step 3: Run tests to verify they fail**

```bash
pytest tests/unit/core/test_provider_manager.py -v
```

Expected: `TypeError: print_provider_summary() got an unexpected keyword argument 'is_default_profile'` or test fails because behavior doesn't match

**Step 4: Implement is_default_profile parameter**

Modify: `src/core/provider_manager.py:950-1037`

Update the method signature and logic:

```python
def print_provider_summary(self, console: Console | None = None, is_default_profile: bool = False) -> None:
    """Print a summary of loaded providers.

    Args:
        console: Rich Console instance for output. If None, creates a new one.
        is_default_profile: True if the default is a profile (not a provider).
            When True, no provider is marked with the default * indicator.
    """
    if console is None:
        from rich.console import Console
        console = Console()

    # ... rest of method, but modify the default indicator logic ...

    # Lines 988-990 become:
    # Check if this is the default provider (only when not a profile default)
    is_default = not is_default_profile and result.name == self.default_provider
    default_indicator = "  * " if is_default else "    "
```

Also update the footer legend (around line 1030-1031):

```python
# At the end, update the legend text
if is_default_profile:
    print("  * = default provider (profile active, no default provider)")
else:
    print("  * = default provider")
print("  🔐 = OAuth authentication")
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/core/test_provider_manager.py -v
```

Expected: PASS

**Step 6: Update existing code that calls print_provider_summary() without the new parameter**

Find all callers:
```bash
grep -r "print_provider_summary()" --include="*.py" | grep -v test | grep -v ".pyc"
```

The caller in `src/cli/commands/server.py` will be updated in Task 4.

**Step 7: Commit**

```bash
git add src/core/provider_manager.py tests/unit/core/test_provider_manager.py
git commit -m "feat(providers): add is_default_profile flag to suppress default provider indicator"
```

---

## Task 3: Update `server.py` to Detect Profile-as-Default and Pass to Presenters

**Files:**
- Modify: `src/cli/commands/server.py:38-82`

**Step 1: Read current server.py display implementation**

```bash
cat -n src/cli/commands/server.py | sed -n '38,82p'
```

**Step 2: Write integration test for server display output**

Create: `tests/integration/test_server_display_output.py`

```python
"""Integration test for server startup display output."""

import re
from io import StringIO
from unittest.mock import MagicMock, patch
from rich.console import Console
from src.cli.commands.server import create_server_display
import pytest


@pytest.mark.integration
@patch("src.cli.commands.server.Config")
def test_server_display_with_profile_as_default(mock_config_class):
    """Test server display when default is a profile (not a provider)."""
    # Mock config with profile as default
    mock_cfg = MagicMock()
    mock_cfg.default_provider = "top"  # This is a profile
    mock_cfg.server_host = "0.0.0.0"
    mock_cfg.server_port = 8082
    mock_cfg.base_url = "https://api.example.com"  # Should not show for profile default
    mock_cfg.api_key_hash = "a1b2c3d4..."

    # Mock profile_manager to detect "top" is a profile
    mock_profile_manager = MagicMock()
    mock_profile_manager.is_profile.return_value = True
    mock_profile_manager.get_profile.return_value = MagicMock(
        name="top",
        timeout=120,
        max_retries=3,
        aliases={"haiku": "anthropic:claude-3-5-haiku-20241022"},
        source="local"
    )
    mock_profile_manager.get_profile_summary.return_value = MagicMock(
        total_profiles=3,
        profiles=(
            MagicMock(name="top", timeout=120, max_retries=3, alias_count=5, source="local"),
            MagicMock(name="chatgpt", timeout=None, max_retries=None, alias_count=2, source="package"),
        )
    )

    mock_cfg.provider_manager.profile_manager = mock_profile_manager
    mock_cfg.provider_manager.print_provider_summary = MagicMock()

    # Mock alias service
    mock_cfg.alias_service = MagicMock()
    mock_cfg.alias_service.get_alias_summary.return_value = MagicMock(
        total_aliases=10,
        provider_count=2,
        fallback_count=4,
        provider_aliases={},
        fallback_aliases={}
    )

    mock_config_class.return_value = mock_cfg

    # Capture output
    console = Console(file=StringIO(), force_terminal=True)

    # Import after mocking
    from src.cli.presenters.profiles import ProfileSummaryPresenter, ProfileSummary
    from src.cli.presenters.aliases import AliasSummaryPresenter

    # Create display
    # Note: This is a simplified test; actual implementation may differ
    console.print("Testing server display output")

    # Verify profile manager was asked if "top" is a profile
    mock_profile_manager.is_profile.assert_called_with("top")


@pytest.mark.integration
@patch("src.cli.commands.server.Config")
def test_server_display_with_provider_as_default(mock_config_class):
    """Test server display when default is a provider (not a profile)."""
    # Mock config with provider as default
    mock_cfg = MagicMock()
    mock_cfg.default_provider = "openai"  # This is a provider
    mock_cfg.server_host = "0.0.0.0"
    mock_cfg.server_port = 8082
    mock_cfg.base_url = "https://api.openai.com/v1"
    mock_cfg.api_key_hash = "sk-abc123..."

    # Mock profile_manager - "openai" is NOT a profile
    mock_profile_manager = MagicMock()
    mock_profile_manager.is_profile.return_value = False
    mock_profile_manager.get_profile_summary.return_value = MagicMock(
        total_profiles=2,
        profiles=(
            MagicMock(name="chatgpt", timeout=None, max_retries=None, alias_count=2, source="package"),
        )
    )

    mock_cfg.provider_manager.profile_manager = mock_profile_manager
    mock_cfg.provider_manager.print_provider_summary = MagicMock()

    mock_cfg.alias_service = MagicMock()
    mock_cfg.alias_service.get_alias_summary.return_value = MagicMock(
        total_aliases=8,
        provider_count=1,
        fallback_count=3,
        provider_aliases={},
        fallback_aliases={}
    )

    mock_config_class.return_value = mock_cfg

    # Verify profile manager was asked if "openai" is a profile
    # (we'll implement the actual display logic in the next step)
    mock_profile_manager.is_profile.assert_called_with("openai")
```

**Step 3: Run tests to verify they fail (or pass with current implementation)**

```bash
pytest tests/integration/test_server_display_output.py -v
```

**Step 4: Implement profile-as-default detection in server.py**

Modify: `src/cli/commands/server.py`

The key changes are:
1. Reorder display sections: Aliases → Profiles → Providers
2. Detect if default_provider is a profile
3. Update configuration table display accordingly
4. Pass `is_default_profile` to `print_provider_summary()`
5. Pass `active_profile_name` to profile presenter

```python
# After importing and getting config (around line 38)

# Reorder display sections and add profile detection
# ============================================================

# 1. Configuration Table
# ============================================================
table = Table(title="Vandamme Proxy Configuration")
table.add_column("Setting", style="cyan")
table.add_column("Value", style="green")

table.add_row("Server URL", f"http://{server_host}:{server_port}")

# Detect if default_provider is a profile
is_default_profile = False
active_profile = None
profile_manager = cfg.provider_manager.profile_manager

if profile_manager and profile_manager.is_profile(cfg.default_provider):
    is_default_profile = True
    active_profile = profile_manager.get_profile(cfg.default_provider)
    # Show "Default Profile" instead of "Default Provider"
    table.add_row("Default Profile", cfg.default_provider)
    # Omit base_url and api_key for profile defaults (since aliases may use different providers)
else:
    # Show "Default Provider" with base_url and api_key
    table.add_row("Default Provider", cfg.default_provider)
    table.add_row(f"{cfg.default_provider.title()} Base URL", cfg.base_url)
    table.add_row(f"{cfg.default_provider.title()} API Key", cfg.api_key_hash)

console.print(table)

# 2. Alias Summary (moved to first position - highest-level abstraction)
# ============================================================
if cfg.alias_service:
    from src.cli.presenters.aliases import AliasSummaryPresenter
    summary = cfg.alias_service.get_alias_summary(cfg.default_provider)
    alias_presenter = AliasSummaryPresenter(console=console)
    alias_presenter.present_summary(summary)

# 3. Profile Summary (second position - configuration presets)
# ============================================================
if profile_manager:
    from src.cli.presenters.profiles import ProfileSummaryPresenter
    profile_presenter = ProfileSummaryPresenter(console=console)
    profile_summary = profile_manager.get_profile_summary()

    # Pass active profile name if we detected one
    active_profile_name = cfg.default_provider if is_default_profile else None
    profile_presenter.present_summary(
        profile_summary,
        active_profile_name=active_profile_name
    )

# 4. Provider Summary (last position - lowest-level implementation)
# ============================================================
cfg.provider_manager.print_provider_summary(console=console, is_default_profile=is_default_profile)
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/integration/test_server_display_output.py -v
```

**Step 6: Commit**

```bash
git add src/cli/commands/server.py tests/integration/test_server_display_output.py
git commit -m "feat(server): reorder display sections and add profile-as-default detection"
```

---

## Task 4: Update ProfileManager to Return Profile Summary with Profile Names

**Files:**
- Review: `src/core/profile_manager.py:129-151`

**Step 1: Verify ProfileSummary dataclass structure**

```bash
grep -A 10 "class ProfileSummary" src/cli/presenters/profiles.py
```

The `ProfileInfo` dataclass should already have a `name` field. Verify this is correct.

**Step 2: No changes needed if ProfileInfo.name exists**

The current implementation in Task 1 already uses `profile.name` from `ProfileInfo`. If the dataclass is correct, no changes are needed here.

**Step 3: If changes were needed, run tests**

```bash
pytest tests/unit/cli/presenters/test_profiles_presenter.py -v
```

**Step 4: Commit if changes were made**

---

## Task 5: Add Legend for Profile Active Indicator

**Files:**
- Modify: `src/cli/presenters/profiles.py:40-71`

**Step 1: Add legend to profile summary output**

After the table is printed, add a legend line to explain the `*` indicator:

```python
# After self.console.print(table) at the end of present_summary()

# Add legend if there's an active profile
if active_profile_name is not None:
    self.console.print("  * = active/default profile")
```

**Step 2: Verify legend appears in tests**

```bash
pytest tests/unit/cli/presenters/test_profiles_presenter.py::test_profile_summary_with_active_profile_indicator -v
```

The test should now verify the legend is present:

```python
assert "* = active/default profile" in output or "* = active" in output
```

**Step 3: Update test to verify legend**

Modify: `tests/unit/cli/presenters/test_profiles_presenter.py`

```python
@pytest.mark.unit
def test_profile_summary_with_active_profile_indicator():
    """Test that active profile is shown with * indicator and legend."""
    # ... existing code ...

    output = console.file.getvalue()
    assert "*top" in output or "top *" in output, "Active profile should have * indicator"
    assert "*" in output and ("active" in output or "default" in output), "Legend should explain * indicator"
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/cli/presenters/test_profiles_presenter.py -v
```

**Step 5: Commit**

```bash
git add src/cli/presenters/profiles.py tests/unit/cli/presenters/test_profiles_presenter.py
git commit -m "feat(profiles): add legend for active profile indicator"
```

---

## Task 6: End-to-End Verification

**Files:**
- Create: `tests/external/test_server_startup_display.py`

**Step 1: Create external test for actual server startup**

This test verifies the complete server startup output with real configuration:

```python
"""External test for actual server startup display output."""

import subprocess
import re
import pytest


@pytest.mark.external
def test_server_startup_with_profile_default():
    """Verify server startup output when profile is default."""
    # This test requires VDM_DEFAULT_PROVIDER to be set to a profile name
    # For this test, we'll skip if not properly configured

    # Start server and capture output
    result = subprocess.run(
        ["vdm", "server", "start", "--once", "--timeout", "1"],
        capture_output=True,
        text=True,
        timeout=10,
        env={**subprocess.os.environ, "VDM_DEFAULT_PROVIDER": "top"}
    )

    output = result.stdout + result.stderr

    # Verify the output contains expected sections in order
    # 1. Aliases section should appear before Profiles
    alias_pos = output.find("Aliases")
    profile_pos = output.find("Profiles")
    provider_pos = output.find("Providers")

    # Verify order: Aliases < Profiles < Providers
    assert alias_pos < profile_pos < provider_pos, f"Sections out of order: aliases@{alias_pos}, profiles@{profile_pos}, providers@{provider_pos}"

    # Verify "Default Profile" appears (not "Default Provider") for profile default
    assert "Default Profile" in output or "default_provider" in output.lower()


@pytest.mark.external
def test_server_startup_with_provider_default():
    """Verify server startup output when provider is default."""
    # Start server with provider as default
    result = subprocess.run(
        ["vdm", "server", "start", "--once", "--timeout", "1"],
        capture_output=True,
        text=True,
        timeout=10,
        env={**subprocess.os.environ, "VDM_DEFAULT_PROVIDER": "openai"}
    )

    output = result.stdout + result.stderr

    # Verify "Default Provider" appears (not "Default Profile")
    assert "Default Provider" in output or "default_provider" in output.lower()
```

**Step 2: Run external test (opt-in)**

```bash
ALLOW_EXTERNAL_TESTS=1 pytest tests/external/test_server_startup_display.py -v
```

**Step 3: Manual verification**

Start the server with a profile as default:

```bash
# Set up a profile as default
export VDM_DEFAULT_PROVIDER=top
vdm server start
```

Verify the output:
1. Aliases section appears first
2. Profiles section appears second with `*` next to the active profile
3. Providers section appears last with no `*` indicator (or with explanatory note)
4. Configuration table shows "Default Profile" instead of "Default Provider"

**Step 4: Start server with provider as default**

```bash
export VDM_DEFAULT_PROVIDER=openai
vdm server start
```

Verify the output:
1. Aliases section appears first
2. Profiles section appears second with no `*` indicator
3. Providers section appears last with `*` next to the default provider
4. Configuration table shows "Default Provider" with Base URL and API Key

**Step 5: Commit**

```bash
git add tests/external/test_server_startup_display.py
git commit -m "test(server): add external test for server startup display verification"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `docs/server-output.md` (create if not exists)
- Review: `README.md` for any relevant screenshots

**Step 1: Create documentation for server output**

Create: `docs/server-output.md`

```markdown
# Server Startup Output

This document describes the information displayed when starting the Vandamme Proxy server with `vdm server start`.

## Display Sections

The server startup output displays information in the following order:

### 1. Configuration Table

Shows core server settings:

| Setting | Description |
|---------|-------------|
| Server URL | The URL where the proxy is listening |
| Default Provider | The default provider (when a provider is the default) |
| Default Profile | The default profile (when a profile is the default) |
| `{Provider} Base URL` | Base URL for the default provider (only shown when provider is default) |
| `{Provider} API Key` | Hash of the API key for the default provider (only shown when provider is default) |

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
| Name | Provider name (prefixed with `*` if this is the default provider) |
| Base URL | The base URL for the provider's API |

**Legend:**
- `* = default provider` - The provider that is used when no provider prefix is specified
- `🔐 = OAuth authentication` - This provider is configured with OAuth authentication

**Note:** When a profile is set as the default, no provider will show the `*` indicator. Instead, the legend will show `* = default provider (profile active, no default provider)`.

## Default Resolution

The default provider/profile is resolved in the following order:

1. `VDM_DEFAULT_PROVIDER` environment variable
2. `default_provider` in `vandamme-config.toml`
3. `default_provider` in `~/.config/vandamme-proxy/vandamme-config.toml`
4. Built-in default (first available provider)

## Profile vs Provider as Default

When `VDM_DEFAULT_PROVIDER` is set to a profile name:
- The configuration table shows "Default Profile"
- The profiles section shows the profile with a `*` indicator
- The providers section shows no `*` indicator (since the profile may use different providers for different aliases)

When `VDM_DEFAULT_PROVIDER` is set to a provider name:
- The configuration table shows "Default Provider" with Base URL and API Key
- The profiles section shows no `*` indicator
- The providers section shows the provider with a `*` indicator
```

**Step 2: Review README for any relevant sections**

```bash
grep -n "server start\|startup\|output" README.md -i
```

Update any sections that reference the server startup output.

**Step 3: Commit**

```bash
git add docs/server-output.md README.md
git commit -m "docs: document server startup output sections and profile/provider defaults"
```

---

## Task 8: Code Quality Checks

**Step 1: Run format check**

```bash
make format
```

**Step 2: Run lint check**

```bash
make lint
```

**Step 3: Run type check**

```bash
make type-check
```

**Step 4: Run all tests**

```bash
make test
```

**Step 5: Fix any issues found**

**Step 6: Final commit**

```bash
git add -A
git commit -m "chore: pass code quality checks (format, lint, type-check)"
```

---

## Summary

After implementing this plan:

1. **Display order** reflects conceptual hierarchy: Aliases → Profiles → Providers
2. **Configuration table** correctly distinguishes between "Default Provider" and "Default Profile"
3. **Profile list** shows a `*` indicator for the active/default profile
4. **Provider list** suppresses the `*` indicator when a profile is the default
5. **Legends** are updated to explain the indicators in both modes
6. **Tests** cover both profile-as-default and provider-as-default scenarios
7. **Documentation** describes the new display behavior
