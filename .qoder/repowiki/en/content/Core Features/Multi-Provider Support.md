# Multi-Provider Support

<cite>
**Referenced Files in This Document**
- [provider_manager.py](file://src/core/provider_manager.py)
- [provider_registry.py](file://src/core/provider/provider_registry.py)
- [client_factory.py](file://src/core/provider/client_factory.py)
- [middleware_manager.py](file://src/core/provider/middleware_manager.py)
- [api_key_rotator.py](file://src/core/provider/api_key_rotator.py)
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py)
- [default_selector.py](file://src/core/provider/default_selector.py)
- [error_types.py](file://src/core/error_types.py)
- [error_handling.py](file://src/api/services/error_handling.py)
- [provider_config.py](file://src/core/provider_config.py)
- [client.py](file://src/core/client.py)
- [anthropic_client.py](file://src/core/anthropic_client.py)
- [defaults.toml](file://src/config/defaults.toml)
- [alias_config.py](file://src/core/alias_config.py)
- [model_manager.py](file://src/core/model_manager.py)
- [provider_context.py](file://src/api/services/provider_context.py)
- [multi-provider.env](file://examples/multi-provider.env)
- [anthropic-direct.env](file://examples/anthropic-direct.env)
- [aws-bedrock.env](file://examples/aws-bedrock.env)
- [google-vertex.env](file://examples/google-vertex.env)
- [test_request_orchestrator_error_paths.py](file://tests/api/orchestrator/test_request_orchestrator_error_paths.py)
</cite>

## Update Summary
This document has been updated to reflect the enhanced provider system architecture that splits the monolithic ProviderManager into focused, single-responsibility components. Key improvements include:
- A provider registry for storing and retrieving configurations
- A client factory for dynamic client creation and caching
- A middleware manager for lifecycle management of middleware chains
- An API key rotator for thread-safe round-robin rotation
- A provider config loader implementing hierarchical configuration merging
- A default provider selector with intelligent fallback
- Improved error handling using an ErrorType enum and ErrorResponseBuilder pattern
- Comprehensive unit tests covering provider integration and error scenarios

These changes enable better modularity, clearer separation of concerns, and improved reliability when managing multiple upstream providers.

## Table of Contents
1. [Introduction](#introduction)
2. [ProviderManager Architecture](#providermanager-architecture)
3. [Provider Routing Mechanism](#provider-routing-mechanism)
4. [Configuration Management](#configuration-management)
5. [Factory Pattern and Client Creation](#factory-pattern-and-client-creation)
6. [Hierarchical Configuration Loading](#hierarchical-configuration-loading)
7. [Error Handling and Validation](#error-handling-and-validation)
8. [Performance Considerations](#performance-considerations)
9. [Integration with Alias System](#integration-with-alias-system)
10. [Practical Configuration Examples](#practical-configuration-examples)

## Introduction
The vandamme-proxy multi-provider system now implements a modular architecture centered around a facade ProviderManager coordinating specialized components. This design improves maintainability, testability, and scalability when integrating multiple LLM providers such as OpenAI, Anthropic, Poe, Azure, Gemini, and AWS Bedrock. The system supports explicit routing via 'provider:model' syntax, default provider selection with fallback, and robust configuration loading from environment variables and TOML files. Enhanced error handling and middleware management further strengthen reliability and observability.

## ProviderManager Architecture
The ProviderManager remains the central coordinator, but it now delegates responsibilities to dedicated components:
- ProviderRegistry: stores and retrieves provider configurations
- ClientFactory: creates and caches provider clients
- ProviderConfigLoader: loads and merges provider configurations
- DefaultProviderSelector: selects a valid default provider with fallback
- MiddlewareManager: owns and initializes middleware chains
- ApiKeyRotator: manages round-robin key rotation

```mermaid
classDiagram
class ProviderManager {
+default_provider : str
+default_provider_source : str
+load_provider_configs()
+get_client(provider_name, client_api_key)
+get_next_provider_api_key(provider_name)
+get_provider_config(provider_name)
+list_providers()
+print_provider_summary()
+initialize_middleware()
+cleanup_middleware()
+parse_model_name(model)
}
class ProviderRegistry {
+register(config)
+get(provider_name)
+list_all()
+exists(provider_name)
+clear()
}
class ClientFactory {
+get_or_create_client(config)
+has_client(provider_name)
+clear()
}
class ProviderConfigLoader {
+scan_providers()
+load_provider(provider_name, require_api_key)
+load_provider_with_result(provider_name)
+get_custom_headers(provider_prefix)
}
class DefaultProviderSelector {
+select(available_providers)
+configured_default
+actual_default
}
class MiddlewareManager {
+initialize_sync()
+initialize()
+cleanup()
+is_initialized
}
class ApiKeyRotator {
+get_next_key(provider_name, api_keys)
+reset_rotation(provider_name)
}
ProviderManager --> ProviderRegistry : "stores/retrieves"
ProviderManager --> ClientFactory : "creates/caches"
ProviderManager --> ProviderConfigLoader : "loads configs"
ProviderManager --> DefaultProviderSelector : "fallback logic"
ProviderManager --> MiddlewareManager : "initializes"
ProviderManager --> ApiKeyRotator : "rotation"
```

**Diagram sources**
- [provider_manager.py](file://src/core/provider_manager.py#L30-L120)
- [provider_registry.py](file://src/core/provider/provider_registry.py#L1-L66)
- [client_factory.py](file://src/core/provider/client_factory.py#L1-L81)
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L1-L251)
- [default_selector.py](file://src/core/provider/default_selector.py#L1-L86)
- [middleware_manager.py](file://src/core/provider/middleware_manager.py#L1-L66)
- [api_key_rotator.py](file://src/core/provider/api_key_rotator.py#L1-L54)

**Section sources**
- [provider_manager.py](file://src/core/provider_manager.py#L30-L120)
- [provider_registry.py](file://src/core/provider/provider_registry.py#L1-L66)
- [client_factory.py](file://src/core/provider/client_factory.py#L1-L81)
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L1-L251)
- [default_selector.py](file://src/core/provider/default_selector.py#L1-L86)
- [middleware_manager.py](file://src/core/provider/middleware_manager.py#L1-L66)
- [api_key_rotator.py](file://src/core/provider/api_key_rotator.py#L1-L54)

## Provider Routing Mechanism
Requests can target a specific provider using the 'provider:model' syntax. When omitted, the default provider is used. The ProviderManager’s parse_model_name method extracts the provider and model, delegating to the ProviderRegistry and ProviderConfigLoader for configuration retrieval. The ModelManager and ProviderContext coordinate alias resolution and provider context construction.

```mermaid
sequenceDiagram
participant Client
participant ModelManager
participant ProviderManager
participant ProviderContext
Client->>ModelManager : resolve_model("anthropic : claude-3-5-sonnet")
ModelManager->>ProviderManager : parse_model_name("anthropic : claude-3-5-sonnet")
ProviderManager-->>ModelManager : ("anthropic", "claude-3-5-sonnet")
ModelManager->>ProviderContext : resolve_provider_context()
ProviderContext->>ProviderManager : get_provider_config("anthropic")
ProviderManager-->>ProviderContext : ProviderConfig
ProviderContext-->>ModelManager : ProviderContext
ModelManager-->>Client : ("anthropic", "claude-3-5-sonnet")
Client->>ModelManager : resolve_model("gpt-4o")
ModelManager->>ProviderManager : parse_model_name("gpt-4o")
ProviderManager-->>ModelManager : (default_provider, "gpt-4o")
ModelManager->>ProviderContext : resolve_provider_context()
ProviderContext->>ProviderManager : get_provider_config(default_provider)
ProviderManager-->>ProviderContext : ProviderConfig
ProviderContext-->>ModelManager : ProviderContext
ModelManager-->>Client : (default_provider, "gpt-4o")
```

**Diagram sources**
- [provider_manager.py](file://src/core/provider_manager.py#L421-L431)
- [model_manager.py](file://src/core/model_manager.py#L19-L91)
- [provider_context.py](file://src/api/services/provider_context.py#L21-L58)

**Section sources**
- [provider_manager.py](file://src/core/provider_manager.py#L421-L431)
- [model_manager.py](file://src/core/model_manager.py#L19-L91)
- [provider_context.py](file://src/api/services/provider_context.py#L21-L58)

## Configuration Management
Provider configurations are loaded from environment variables and merged with TOML defaults. The ProviderConfigLoader scans for {PROVIDER}_API_KEY patterns, resolves base URLs with precedence (environment > TOML > defaults), and applies provider-specific settings like API format, timeouts, retries, and custom headers. The DefaultProviderSelector chooses a valid default provider, falling back to the first available if the configured default is missing.

```mermaid
flowchart TD
Start([Configuration Loading]) --> EnvScan["Scan Environment Variables"]
EnvScan --> DefaultProvider["Load Default Provider"]
DefaultProvider --> AdditionalProviders["Load Additional Providers"]
AdditionalProviders --> TOMLCheck["Check TOML Configuration"]
TOMLCheck --> EnvOverride["Override with Environment Variables"]
EnvOverride --> Validation["Validate Configuration"]
Validation --> Result["Store Provider Config"]
Result --> DefaultSelection["Select Default Provider"]
DefaultSelection --> End([Configuration Complete])
style Start fill:#f9f,stroke:#333
style End fill:#f9f,stroke:#333
```

**Diagram sources**
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L36-L187)
- [default_selector.py](file://src/core/provider/default_selector.py#L33-L86)
- [defaults.toml](file://src/config/defaults.toml#L1-L89)

**Section sources**
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L36-L187)
- [default_selector.py](file://src/core/provider/default_selector.py#L33-L86)
- [defaults.toml](file://src/config/defaults.toml#L1-L89)

## Factory Pattern and Client Creation
The ClientFactory dynamically creates and caches provider clients based on ProviderConfig.api_format. It supports both OpenAI-style and Anthropic-style APIs, and handles passthrough providers by initializing clients without static API keys. Cached clients avoid repeated HTTP connection setup and reduce latency.

```mermaid
classDiagram
class ClientFactory {
+get_or_create_client(config)
+has_client(provider_name)
+clear()
}
class OpenAIClient {
+create_chat_completion(request)
+create_chat_completion_stream(request)
}
class AnthropicClient {
+create_chat_completion(request)
+create_chat_completion_stream(request)
}
ClientFactory --> OpenAIClient : "creates"
ClientFactory --> AnthropicClient : "creates"
```

**Diagram sources**
- [client_factory.py](file://src/core/provider/client_factory.py#L1-L81)
- [client.py](file://src/core/client.py#L32-L352)
- [anthropic_client.py](file://src/core/anthropic_client.py#L25-L271)

**Section sources**
- [client_factory.py](file://src/core/provider/client_factory.py#L1-L81)
- [client.py](file://src/core/client.py#L32-L352)
- [anthropic_client.py](file://src/core/anthropic_client.py#L25-L271)

## Hierarchical Configuration Loading
The system follows a strict precedence order: environment variables override TOML, which override package defaults. ProviderConfigLoader encapsulates this logic, while ProviderManager integrates it into runtime initialization and middleware setup.

```mermaid
graph TD
A[Environment Variables] --> |Highest Priority| B[Local vandamme-config.toml]
B --> |Medium Priority| C[User vandamme-config.toml]
C --> |Lowest Priority| D[Package defaults.toml]
D --> E[Hardcoded Defaults]
style A fill:#e6f3ff,stroke:#333
style B fill:#e6f3ff,stroke:#333
style C fill:#e6f3ff,stroke:#333
style D fill:#e6f3ff,stroke:#333
style E fill:#e6f3ff,stroke:#333
F[Configuration Resolution] --> G[Final Provider Configuration]
A --> F
B --> F
C --> F
D --> F
E --> F
```

**Diagram sources**
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L76-L187)
- [provider_manager.py](file://src/core/provider_manager.py#L158-L219)
- [alias_config.py](file://src/core/alias_config.py#L32-L155)
- [defaults.toml](file://src/config/defaults.toml#L1-L89)

**Section sources**
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L76-L187)
- [provider_manager.py](file://src/core/provider_manager.py#L158-L219)
- [alias_config.py](file://src/core/alias_config.py#L32-L155)
- [defaults.toml](file://src/config/defaults.toml#L1-L89)

## Error Handling and Validation
Enhanced error handling uses an ErrorType enum and a centralized ErrorResponseBuilder to produce consistent error responses across endpoints. ProviderConfigLoader and ProviderManager validate configurations and raise descriptive errors for missing or conflicting settings. Tests cover error paths in orchestrator flows, including unknown providers, invalid models, authentication failures, and middleware exceptions.

```mermaid
flowchart TD
A[Configuration Input] --> B{Valid?}
B --> |Yes| C[Store Configuration]
B --> |No| D[Generate Error]
D --> E[Validate Required Fields]
E --> F{Missing Required Field?}
F --> |Yes| G[Return Specific Error]
F --> |No| H{Mixed Configuration?}
H --> |Yes| I[Return Mixed Config Error]
H --> |No| J{Invalid API Format?}
J --> |Yes| K[Return Format Error]
J --> |No| L[Store Configuration]
C --> M[Provider Ready]
L --> M
style A fill:#f9f,stroke:#333
style M fill:#f9f,stroke:#333
```

**Diagram sources**
- [error_types.py](file://src/core/error_types.py#L1-L48)
- [error_handling.py](file://src/api/services/error_handling.py#L19-L219)
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L103-L187)
- [test_request_orchestrator_error_paths.py](file://tests/api/orchestrator/test_request_orchestrator_error_paths.py#L1-L75)

**Section sources**
- [error_types.py](file://src/core/error_types.py#L1-L48)
- [error_handling.py](file://src/api/services/error_handling.py#L19-L219)
- [provider_config_loader.py](file://src/core/provider/provider_config_loader.py#L103-L187)
- [test_request_orchestrator_error_paths.py](file://tests/api/orchestrator/test_request_orchestrator_error_paths.py#L1-L75)

## Performance Considerations
Performance optimizations include:
- Connection pooling and client caching via ClientFactory
- Lazy loading of provider configurations and middleware
- Round-robin API key rotation with process-global locks
- Configurable timeouts and retry limits
- Streaming support with proper cancellation handling

```mermaid
graph TB
subgraph "Client Performance"
A[Connection Pooling]
B[Client Caching]
C[Streaming Support]
D[Cancellation Handling]
end
subgraph "Key Management"
E[Round-Robin Rotation]
F[Process-Global Locks]
G[Key Attempt Tracking]
end
subgraph "Configuration"
H[Lazy Loading]
I[Config Caching]
J[Hierarchical Resolution]
end
subgraph "Request Processing"
K[Timeout Configuration]
L[Retry Limits]
M[Error Recovery]
end
A --> Performance
B --> Performance
C --> Performance
D --> Performance
E --> Performance
F --> Performance
G --> Performance
H --> Performance
I --> Performance
J --> Performance
K --> Performance
L --> Performance
M --> Performance
```

**Diagram sources**
- [client_factory.py](file://src/core/provider/client_factory.py#L23-L81)
- [api_key_rotator.py](file://src/core/provider/api_key_rotator.py#L16-L54)
- [client.py](file://src/core/client.py#L53-L86)

**Section sources**
- [client_factory.py](file://src/core/provider/client_factory.py#L23-L81)
- [api_key_rotator.py](file://src/core/provider/api_key_rotator.py#L16-L54)
- [client.py](file://src/core/client.py#L53-L86)

## Integration with Alias System
The alias system integrates with the provider routing pipeline. The ModelManager resolves aliases and provider prefixes, then delegates to ProviderManager for configuration retrieval. This enables cross-provider aliasing and consistent model naming across providers.

```mermaid
sequenceDiagram
participant Client
participant ModelManager
participant AliasManager
participant ProviderManager
Client->>ModelManager : resolve_model("sonnet")
ModelManager->>AliasManager : resolve_alias("sonnet", provider=default)
AliasManager-->>ModelManager : "openai : gpt-4o"
ModelManager->>ProviderManager : parse_model_name("openai : gpt-4o")
ProviderManager-->>ModelManager : ("openai", "gpt-4o")
ModelManager-->>Client : ("openai", "gpt-4o")
Client->>ModelManager : resolve_model("poe : cheap")
ModelManager->>AliasManager : resolve_alias("poe : cheap")
AliasManager-->>ModelManager : "glm-4.6"
ModelManager->>ProviderManager : parse_model_name("poe : glm-4.6")
ProviderManager-->>ModelManager : ("poe", "glm-4.6")
ModelManager-->>Client : ("poe", "glm-4.6")
```

**Diagram sources**
- [model_manager.py](file://src/core/model_manager.py#L19-L91)
- [alias_config.py](file://src/core/alias_config.py#L157-L175)
- [provider_manager.py](file://src/core/provider_manager.py#L421-L431)

**Section sources**
- [model_manager.py](file://src/core/model_manager.py#L19-L91)
- [alias_config.py](file://src/core/alias_config.py#L157-L175)

## Practical Configuration Examples
The examples demonstrate multi-provider setups and provider-specific configurations:
- multi-provider.env: Configure multiple providers (OpenAI, Anthropic, AWS Bedrock, Azure)
- anthropic-direct.env: Direct Anthropic access with default provider set to Anthropic
- aws-bedrock.env: AWS Bedrock with Claude models and custom headers
- google-vertex.env: Google Vertex AI with Anthropic models and GCP project settings

Environment variables commonly used include {PROVIDER}_API_KEY, {PROVIDER}_BASE_URL, {PROVIDER}_API_VERSION, and {PROVIDER}_CUSTOM_HEADER_* for per-provider headers.

**Section sources**
- [multi-provider.env](file://examples/multi-provider.env#L1-L48)
- [anthropic-direct.env](file://examples/anthropic-direct.env#L1-L22)
- [aws-bedrock.env](file://examples/aws-bedrock.env#L1-L32)
- [google-vertex.env](file://examples/google-vertex.env#L1-L32)