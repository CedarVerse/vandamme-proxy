# Configuration Hierarchy

<cite>
**Referenced Files in This Document**
- [alias_config.py](file://src/core/alias_config.py)
- [defaults.toml](file://src/config/defaults.toml)
- [config.py](file://src/core/config.py)
- [alias_manager.py](file://src/core/alias_manager.py)
- [test_alias_config.py](file://tests/core/test_alias_config.py)
- [config.py](file://src/cli/commands/config.py)
- [README.md](file://README.md)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
This document explains the three-tiered configuration system used by the application. It covers how environment variables (highest priority), TOML configuration files (medium priority), and hardcoded defaults (lowest priority) are merged to produce the final runtime configuration. The focus is on the AliasConfigLoader’s loading order and merge strategy, the specific file paths searched, and how local project configurations override user-level settings, which in turn override package defaults. Practical examples illustrate how values are resolved and overridden, and the implications for production deployments versus development workflows.

## Project Structure
The configuration system spans several modules:
- Alias configuration loader: loads and merges TOML files from three locations and caches the result.
- Package defaults: bundled TOML with baseline provider and alias settings.
- Runtime configuration: reads environment variables and applies them on top of the merged alias configuration.
- Alias manager: loads environment-based aliases and merges them with fallback aliases from TOML.

```mermaid
graph TB
subgraph "Configuration Sources"
ENV["Environment Variables<br/>Highest Priority"]
TOML_LOCAL["Local TOML<br/>./vandamme-config.toml"]
TOML_USER["User TOML<br/>~/.config/vandamme-proxy/vandamme-config.toml"]
TOML_PKG["Package Defaults<br/>src/config/defaults.toml"]
end
subgraph "Loading Pipeline"
AC["AliasConfigLoader<br/>load_config()"]
AM["AliasManager<br/>_load_aliases()"]
CFG["Runtime Config<br/>src/core/config.py"]
end
ENV --> AM
TOML_LOCAL --> AC
TOML_USER --> AC
TOML_PKG --> AC
AC --> AM
AM --> CFG
```

**Diagram sources**
- [alias_config.py](file://src/core/alias_config.py#L30-L39)
- [alias_manager.py](file://src/core/alias_manager.py#L201-L208)
- [config.py](file://src/core/config.py#L16-L47)

**Section sources**
- [alias_config.py](file://src/core/alias_config.py#L30-L39)
- [defaults.toml](file://src/config/defaults.toml#L1-L89)
- [config.py](file://src/core/config.py#L16-L47)
- [alias_manager.py](file://src/core/alias_manager.py#L201-L208)

## Core Components
- AliasConfigLoader: Loads and merges TOML configuration from three paths, with higher-priority files overriding lower-priority ones. It caches the merged configuration and logs provider/alias counts.
- Package defaults: A bundled TOML file containing provider sections and default aliases.
- Runtime Config: Reads environment variables and applies them on top of the merged alias configuration.
- Alias Manager: Loads environment-based aliases and merges them with fallback aliases from TOML.

Key behaviors:
- Loading order: package defaults (lowest) → user config → local override (highest).
- Merge strategy: later files override earlier files for both provider settings and aliases.
- Caching: AliasConfigLoader caches the merged configuration to avoid repeated file I/O.
- Environment overrides: Environment variables take precedence over TOML for runtime settings.

**Section sources**
- [alias_config.py](file://src/core/alias_config.py#L41-L155)
- [defaults.toml](file://src/config/defaults.toml#L5-L89)
- [config.py](file://src/core/config.py#L16-L98)
- [alias_manager.py](file://src/core/alias_manager.py#L214-L269)

## Architecture Overview
The configuration pipeline integrates environment variables, TOML files, and defaults into a unified runtime configuration. The AliasConfigLoader is responsible for merging TOML sources, while environment variables are handled separately in the runtime configuration and alias manager.

```mermaid
sequenceDiagram
participant App as "Application"
participant Loader as "AliasConfigLoader"
participant FS as "Filesystem"
participant AM as "AliasManager"
participant Env as "Environment"
participant Runtime as "Runtime Config"
App->>Loader : load_config()
Loader->>FS : Read package defaults.toml
FS-->>Loader : Defaults
Loader->>FS : Read ~/.config/vandamme-proxy/vandamme-config.toml
FS-->>Loader : User config
Loader->>FS : Read ./vandamme-config.toml
FS-->>Loader : Local override
Loader->>Loader : Merge (later overrides earlier)
Loader-->>App : Merged config
App->>AM : _load_aliases()
AM->>Env : Scan environment for <PROVIDER>_ALIAS_* variables
Env-->>AM : Explicit aliases
AM->>AM : Merge explicit aliases over fallbacks
App->>Runtime : Initialize runtime config
Runtime->>Env : Read environment variables
Runtime->>Loader : get_defaults()
Loader-->>Runtime : default-provider
Runtime-->>App : Final runtime config
```

**Diagram sources**
- [alias_config.py](file://src/core/alias_config.py#L41-L155)
- [alias_manager.py](file://src/core/alias_manager.py#L214-L269)
- [config.py](file://src/core/config.py#L16-L98)

## Detailed Component Analysis

### AliasConfigLoader: Three-Tier TOML Loading and Merge Strategy
AliasConfigLoader defines the three search paths and implements a strict override order:
- Lowest priority: package defaults (src/config/defaults.toml)
- Medium priority: user-level config (~/.config/vandamme-proxy/vandamme-config.toml)
- Highest priority: local project config (./vandamme-config.toml)

The loader iterates through the paths in reverse order so that later files override earlier ones. It extracts provider sections and aliases, normalizes alias names to lowercase, and merges provider settings and aliases into a single dictionary under “providers” and “defaults”.

Caching behavior:
- The loader caches the merged configuration in a module-level variable and logs provider/alias counts only once per process.
- A reset_cache method clears the cache for test isolation.

```mermaid
flowchart TD
Start(["load_config()"]) --> CheckCache["Check cache and force_reload flag"]
CheckCache --> |Cached and not forced| ReturnCache["Return cached config"]
CheckCache --> |Not cached or forced| InitMerged["Initialize merged_config with defaults and providers"]
InitMerged --> IteratePaths["Iterate paths in reverse order"]
IteratePaths --> Exists{"Path exists?"}
Exists --> |No| NextPath["Next path"]
Exists --> |Yes| ReadFile["Read TOML file"]
ReadFile --> Parse["Parse TOML"]
Parse --> ExtractDefaults["Extract defaults section"]
Parse --> ExtractProviders["Extract provider sections"]
ExtractProviders --> MergeProviders["Merge provider settings (later overrides earlier)"]
MergeProviders --> ExtractAliases["Extract aliases and lowercase keys"]
ExtractAliases --> MergeAliases["Merge aliases (later overrides earlier)"]
MergeAliases --> NextPath
NextPath --> DoneIterating{"All paths processed?"}
DoneIterating --> |No| IteratePaths
DoneIterating --> |Yes| Cache["Cache merged config"]
Cache --> LogOnce["Log provider/alias counts once"]
LogOnce --> ReturnMerged["Return merged config"]
```

**Diagram sources**
- [alias_config.py](file://src/core/alias_config.py#L41-L155)

**Section sources**
- [alias_config.py](file://src/core/alias_config.py#L30-L39)
- [alias_config.py](file://src/core/alias_config.py#L75-L155)
- [alias_config.py](file://src/core/alias_config.py#L215-L224)

### Package Defaults: Baseline Configuration
The package defaults file provides baseline provider settings and aliases. It includes sections for multiple providers and their default aliases. The runtime configuration can override the default provider via environment variables.

Examples of sections and keys:
- defaults.default-provider
- provider sections (e.g., openai, poe, anthropic) with base-url, api-format, timeout, max-retries, and aliases subsections

These defaults are loaded last and thus can be overridden by user or local TOML files.

**Section sources**
- [defaults.toml](file://src/config/defaults.toml#L5-L89)

### Runtime Configuration: Environment Variables Override
The runtime configuration reads environment variables and applies them on top of the merged alias configuration. Notable behaviors:
- VDM_DEFAULT_PROVIDER overrides the default-provider from TOML.
- Provider-specific variables (e.g., {PROVIDER}_API_KEY, {PROVIDER}_BASE_URL) are read and validated.
- Other settings (HOST, PORT, LOG_LEVEL, timeouts, retries, etc.) are read from environment variables with sensible defaults.

This ensures environment variables take precedence over TOML for runtime behavior.

**Section sources**
- [config.py](file://src/core/config.py#L16-L98)

### Alias Manager: Environment-Based Aliases Overriding Fallbacks
The alias manager loads explicit aliases from environment variables and merges them with fallback aliases from TOML. The explicit aliases take precedence over fallbacks.

Key points:
- Environment aliases are loaded using the pattern {PROVIDER}_ALIAS_{NAME}=TARGET.
- Aliases are normalized to lowercase.
- Fallback aliases are applied only for providers that are known (either configured or present in environment variable names).

**Section sources**
- [alias_manager.py](file://src/core/alias_manager.py#L201-L208)
- [alias_manager.py](file://src/core/alias_manager.py#L214-L269)
- [alias_manager.py](file://src/core/alias_manager.py#L301-L336)
- [alias_manager.py](file://src/core/alias_manager.py#L338-L382)

### Example Scenarios: How Values Are Resolved and Overridden
Below are practical examples derived from the test suite and configuration logic. These illustrate how the three-tier hierarchy resolves values.

- Local override overrides user config and package defaults:
  - Local TOML sets poe.base-url to a custom value and adds new aliases.
  - User TOML sets poe.base-url and a new alias.
  - Package defaults define poe.base-url and default aliases.
  - Result: local values take precedence; missing values fall back to user; missing values fall back to package defaults.

- New aliases in user config are merged:
  - Local TOML adds a new alias.
  - User TOML adds another new alias.
  - Result: both new aliases are present; local overrides existing aliases; user fills missing ones.

- Provider settings override hierarchy:
  - Local TOML sets poe.timeout.
  - User TOML sets poe.base-url.
  - Result: local timeout overrides; user base-url overrides; missing values from package defaults.

- Case-insensitive alias normalization:
  - Local TOML defines aliases with uppercase names.
  - Result: aliases are stored in lowercase.

- Invalid or malformed TOML is handled gracefully:
  - Invalid TOML is skipped; the loader continues with available files and falls back to package defaults.

These scenarios are verified by the test suite and reflect the documented merge strategy.

**Section sources**
- [test_alias_config.py](file://tests/core/test_alias_config.py#L62-L137)
- [test_alias_config.py](file://tests/core/test_alias_config.py#L178-L192)
- [test_alias_config.py](file://tests/core/test_alias_config.py#L193-L214)
- [test_alias_config.py](file://tests/core/test_alias_config.py#L215-L240)
- [test_alias_config.py](file://tests/core/test_alias_config.py#L241-L263)

## Dependency Analysis
The configuration system exhibits clear separation of concerns:
- AliasConfigLoader depends on filesystem access and TOML parsing to build a merged configuration.
- AliasManager depends on AliasConfigLoader for fallback aliases and on environment variables for explicit aliases.
- Runtime Config depends on environment variables and on AliasConfigLoader for default-provider resolution.

```mermaid
graph TB
AC["AliasConfigLoader"] --> FS["Filesystem"]
AC --> TOML["tomli"]
AM["AliasManager"] --> AC
AM --> ENV["Environment"]
RC["Runtime Config"] --> ENV
RC --> AC
```

**Diagram sources**
- [alias_config.py](file://src/core/alias_config.py#L14-L18)
- [alias_manager.py](file://src/core/alias_manager.py#L226-L230)
- [config.py](file://src/core/config.py#L28-L32)

**Section sources**
- [alias_config.py](file://src/core/alias_config.py#L14-L18)
- [alias_manager.py](file://src/core/alias_manager.py#L226-L230)
- [config.py](file://src/core/config.py#L28-L32)

## Performance Considerations
- Caching: AliasConfigLoader caches the merged configuration to avoid repeated file I/O. Tests confirm cache reuse and explicit cache invalidation via reset_cache.
- Lazy loading: Runtime configuration and alias manager defer heavy initialization until needed.
- Minimal parsing overhead: Only provider sections and defaults are processed; aliases are extracted and normalized efficiently.

Recommendations:
- Prefer environment variables for frequently changing settings to avoid file I/O.
- Keep TOML files minimal and focused to reduce parsing time.
- Use reset_cache in tests to ensure deterministic behavior.

**Section sources**
- [alias_config.py](file://src/core/alias_config.py#L22-L24)
- [alias_config.py](file://src/core/alias_config.py#L215-L224)
- [test_alias_config.py](file://tests/core/test_alias_config.py#L162-L177)

## Troubleshooting Guide
Common issues and resolutions:
- Missing tomli dependency: The loader fails fast with a clear message if tomli is unavailable. Install the dependency and retry.
- Invalid TOML files: The loader logs warnings and skips invalid files, falling back to available configurations.
- Missing aliases section: If a TOML file lacks an aliases section, the loader continues and uses defaults.
- Malformed aliases: Non-string targets are ignored; ensure aliases map to valid string values.
- Case sensitivity: Aliases are normalized to lowercase; ensure environment variables use uppercase names consistently.
- Cache staleness: Use reset_cache in tests or force reload to refresh configuration.

**Section sources**
- [alias_config.py](file://src/core/alias_config.py#L57-L74)
- [alias_config.py](file://src/core/alias_config.py#L138-L140)
- [test_alias_config.py](file://tests/core/test_alias_config.py#L178-L192)
- [test_alias_config.py](file://tests/core/test_alias_config.py#L215-L240)
- [alias_config.py](file://src/core/alias_config.py#L215-L224)

## Conclusion
The configuration hierarchy provides a robust, layered approach to managing application settings:
- Environment variables take highest priority for runtime behavior.
- TOML files provide structured, portable configuration with a clear override order.
- Package defaults ensure sensible defaults when no user configuration is present.
- The AliasConfigLoader enforces a predictable merge strategy, and caching improves performance.
- The alias manager complements this by applying environment-based aliases over fallbacks.

This design supports flexible development workflows (local overrides) and production deployments (environment-driven configuration) while maintaining reliability and clarity.