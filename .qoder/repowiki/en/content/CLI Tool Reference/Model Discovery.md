# Model Discovery

<cite>
**Referenced Files in This Document**   
- [models.py](file://src/cli/commands/models.py)
- [model_manager.py](file://src/core/model_manager.py)
- [alias_manager.py](file://src/core/alias_manager.py)
- [resolver.py](file://src/core/alias/resolver.py)
- [service.py](file://src/top_models/service.py)
- [endpoints.py](file://src/api/endpoints.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Model Discovery Commands](#model-discovery-commands)
3. [Model Aliasing System](#model-aliasing-system)
4. [Provider Model Information](#provider-model-information)
5. [Practical Use Cases](#practical-use-cases)
6. [Common Issues and Troubleshooting](#common-issues-and-troubleshooting)
7. [Architecture Overview](#architecture-overview)

## Introduction

The model discovery system in Vandamme Proxy provides comprehensive tools for exploring available AI models across all configured providers. This documentation covers the CLI commands for model discovery, the model aliasing system, and practical guidance for selecting appropriate models for specific tasks. The system integrates with the model manager and alias system to provide a unified interface for model exploration and selection.

**Section sources**
- [models.py](file://src/cli/commands/models.py#L1-L88)
- [model_manager.py](file://src/core/model_manager.py#L1-L117)

## Model Discovery Commands

The CLI provides several commands for discovering and exploring available models across all configured providers. The primary command is `vdm models top`, which retrieves curated top models from the server.

### Top Models Command

The `top` command displays curated top models with various filtering and output options:

```bash
vdm models top --base-url http://localhost:8082 --limit 10 --refresh --provider openrouter --sub-provider openai --json
```

The command supports the following options:
- `--base-url`: Vandamme proxy base URL (default: http://localhost:8082)
- `--limit`: Maximum number of models to show (1-50)
- `--refresh`: Bypass cache and fetch fresh data
- `--provider`: Filter by provider (top-level source, e.g., openrouter)
- `--sub-provider`: Filter by sub-provider (e.g., openai, google)
- `--json`: Print JSON output instead of formatted table

The command retrieves model data from the `/top-models` endpoint and displays it in a formatted table with columns for Provider, Sub-provider, Model, Context, Avg $/M, Capabilities, and Source (cache or live).

**Section sources**
- [models.py](file://src/cli/commands/models.py#L16-L88)

## Model Aliasing System

The model aliasing system provides flexible model name resolution with case-insensitive substring matching, where aliases are scoped to specific providers. This system allows users to create shorthand references to models and affects discovery results.

### Alias Resolution Process

The alias resolution process follows these steps:
1. Determine provider context (from explicit prefix or default provider)
2. Apply alias resolution scoped to that provider (if aliases are configured)
3. Parse provider prefix from resolved value
4. Return provider and actual model name

The system supports provider-specific `<PROVIDER>_ALIAS_*` environment variables, such as:
- `POE_ALIAS_HAIKU=grok-4.1-fast-non-reasoning`
- `OPENAI_ALIAS_FAST=gpt-4o-mini`
- `ANTHROPIC_ALIAS_CHAT=claude-3-5-sonnet-20241022`

### Literal Model Names

Literal model names prefixed with '!' bypass alias resolution and use the exact model name provided. This allows users to bypass alias resolution when needed.

```mermaid
classDiagram
class AliasManager {
+dict[str, dict[str, str]] aliases
+dict[str, dict[str, str]] _fallback_aliases
+str | None _default_provider
+bool _loaded
+AliasResolverCache _cache
+AliasResolverChain _resolver_chain
+resolve_alias(model : str, provider : str | None) str | None
+get_all_aliases() dict[str, dict[str, str]]
+get_explicit_aliases() dict[str, dict[str, str]]
+has_aliases() bool
+get_alias_count() int
+get_fallback_aliases() dict[str, dict[str, str]]
+invalidate_cache() None
+get_cache_stats() CacheStats
}
class AliasResolverChain {
+list[AliasResolver] _resolvers
+Logger _logger
+resolve(context : ResolutionContext) ResolutionResult
}
class AliasResolver {
<<abstract>>
+name : str
+can_resolve(context : ResolutionContext) bool
+resolve(context : ResolutionContext) ResolutionResult | None
}
class LiteralPrefixResolver {
+name : str
+can_resolve(context : ResolutionContext) bool
+resolve(context : ResolutionContext) ResolutionResult | None
}
class ChainedAliasResolver {
+int DEFAULT_MAX_CHAIN_LENGTH
+int _max_chain_length
+name : str
+can_resolve(context : ResolutionContext) bool
+resolve(context : ResolutionContext) ResolutionResult | None
}
class SubstringMatcher {
+name : str
+can_resolve(context : ResolutionContext) bool
+resolve(context : ResolutionContext) ResolutionResult | None
}
class MatchRanker {
+name : str
+can_resolve(context : ResolutionContext) bool
+resolve(context : ResolutionContext, matches : list[Match] | None) ResolutionResult | None
}
class ResolutionContext {
+str model
+str | None provider
+str default_provider
+dict[str, dict[str, str]] aliases
+dict[str, Any] metadata
+with_updates(**kwargs : Any) ResolutionContext
}
class ResolutionResult {
+str resolved_model
+str | None provider
+bool was_resolved
+tuple[str, ...] resolution_path
+tuple[Match, ...] matches
}
class Match {
+str provider
+str alias
+str target
+int length
+bool is_exact
}
class CacheEntry {
+str resolved_model
+float timestamp
+int generation
}
class CacheStats {
+int size
+int max_size
+int hits
+int misses
+str hit_rate
+int generation
}
class AliasResolverCache {
+float ttl_seconds
+int max_size
+dict[str, CacheEntry] _cache
+int _generation
+int _hits
+int _misses
+get(key : str) str | None
+put(key : str, value : str) None
+invalidate() None
+clear() None
+hit_rate() float
+get_stats() CacheStats
}
AliasManager --> AliasResolverChain : "uses"
AliasResolverChain --> AliasResolver : "composes"
LiteralPrefixResolver --> AliasResolver : "implements"
ChainedAliasResolver --> AliasResolver : "implements"
SubstringMatcher --> AliasResolver : "implements"
MatchRanker --> AliasResolver : "implements"
AliasManager --> AliasResolverCache : "uses"
AliasResolverChain --> ResolutionContext : "uses"
AliasResolverChain --> ResolutionResult : "returns"
SubstringMatcher --> Match : "creates"
MatchRanker --> Match : "ranks"
AliasResolverCache --> CacheEntry : "stores"
AliasResolverCache --> CacheStats : "returns"
</mermaid>
**Diagram sources **
- [alias_manager.py](file : //src/core/alias_manager.py#L1-L634)
- [resolver.py](file : //src/core/alias/resolver.py#L1-L524)
**Section sources**
- [model_manager.py](file : //src/core/model_manager.py#L19-L91)
- [alias_manager.py](file : //src/core/alias_manager.py#L1-L634)
- [resolver.py](file : //src/core/alias/resolver.py#L1-L524)
## Provider Model Information
The model discovery system integrates with multiple providers to gather comprehensive model information. The `/top-models` endpoint serves as the primary interface for retrieving model data.
### Top Models Service
The TopModelsService retrieves curated model recommendations from configured sources (openrouter or manual_rankings). The service applies exclusions and suggests aliases based on model characteristics.
```mermaid
sequenceDiagram
    participant CLI as "CLI Command"
    participant HTTP as "HTTP Client"
    participant API as "API Endpoint"
    participant Service as "TopModelsService"
    participant Source as "TopModelsSource"
    
    CLI->>HTTP: vdm models top --limit 10
    HTTP->>API: GET /top-models?limit=10
    API->>Service: await get_top_models(limit=10)
    Service->>Source: await fetch_models()
    Source-->>Service: Return models
    Service->>Service: Apply exclusions
    Service->>Service: Suggest aliases
    Service-->>API: Return TopModelsResult
    API-->>HTTP: JSON response
    HTTP-->>CLI: Formatted table
</mermaid>

**Diagram sources **
- [service.py](file://src/top_models/service.py#L1-L216)
- [endpoints.py](file://src/api/endpoints.py#L1345-L1418)

### Model Attributes

The system provides detailed information about each model, including:
- Provider and sub-provider
- Model ID and name
- Context window size
- Pricing information (input/output per million tokens)
- Capabilities (tools, vision, reasoning, etc.)
- Performance characteristics

**Section sources**
- [service.py](file://src/top_models/service.py#L1-L216)
- [types.py](file://src/top_models/types.py#L1-L61)
- [endpoints.py](file://src/api/endpoints.py#L1345-L1418)

## Practical Use Cases

The model discovery system supports various practical use cases for selecting appropriate models for specific tasks.

### Finding Models by Name

To find models by name, use the search functionality in the dashboard or filter by provider:

```bash
# Search for models with "vision" capability
vdm models top --provider openrouter --json | grep -i vision

# Find models from a specific provider
vdm models top --provider openrouter --sub-provider openai
```

### Selecting Models by Capability

When selecting models for specific tasks, consider their capabilities:
- **Programming tasks**: Look for models with high context windows and strong reasoning capabilities
- **Vision tasks**: Select models with vision capability
- **Cost-sensitive applications**: Choose models with lower average cost per million tokens
- **Real-time applications**: Opt for models with fast response times

### Performance-Based Selection

To select models based on performance characteristics:
- **Long context needs**: Use `top-longctx` suggested alias for the model with the longest context window
- **Cost efficiency**: Use `top-cheap` suggested alias for the most cost-effective model
- **Top overall**: Use `top` suggested alias for the highest-ranked model

**Section sources**
- [docs/dashboard.md](file://docs/dashboard.md#L115-L143)
- [planning/top-models-implementation.md](file://planning/top-models-implementation.md#L36-L394)

## Common Issues and Troubleshooting

Several common issues may arise when using the model discovery system. Understanding these issues and their solutions can help maintain smooth operation.

### Stale Model Caches

When model information appears outdated, the cache may be stale. To resolve this:
1. Use the `--refresh` flag with the `top` command to bypass the cache
2. Verify the cache TTL settings in the configuration
3. Check that the server has internet connectivity to refresh from remote sources

### Provider API Connectivity Problems

If provider API connectivity issues occur:
1. Verify API keys are correctly configured in environment variables
2. Check network connectivity between the proxy and provider APIs
3. Review provider status pages for any service outages
4. Test connectivity using the health check commands

### Alias Resolution Issues

For problems with alias resolution:
1. Verify alias environment variables are correctly formatted
2. Check for circular references in alias chains
3. Use the `!` prefix to bypass alias resolution for testing
4. Review the alias manager logs for resolution details

**Section sources**
- [model_manager.py](file://src/core/model_manager.py#L34-L73)
- [alias_manager.py](file://src/core/alias_manager.py#L383-L458)
- [resolver.py](file://src/core/alias/resolver.py#L175-L271)

## Architecture Overview

The model discovery system follows a modular architecture with clear separation of concerns between components.

```mermaid
graph TD
subgraph "CLI Interface"
CLI[CLI Commands]
end
subgraph "API Layer"
API[/top-models Endpoint]
end
subgraph "Service Layer"
Service[TopModelsService]
Source[TopModelsSource]
end
subgraph "Data Layer"
Cache[Models Cache]
Config[Configuration]
end
CLI --> API
API --> Service
Service --> Source
Service --> Cache
Service --> Config
Source --> Cache
Source --> Config
```

The system integrates with the model manager and alias system to provide a comprehensive model discovery experience. The CLI commands retrieve data from the API endpoint, which in turn uses the TopModelsService to fetch and process model information from various sources.

**Diagram sources **
- [models.py](file://src/cli/commands/models.py#L1-L88)
- [endpoints.py](file://src/api/endpoints.py#L1345-L1418)
- [service.py](file://src/top_models/service.py#L1-L216)

**Section sources**
- [models.py](file://src/cli/commands/models.py#L1-L88)
- [endpoints.py](file://src/api/endpoints.py#L1345-L1418)
- [service.py](file://src/top_models/service.py#L1-L216)