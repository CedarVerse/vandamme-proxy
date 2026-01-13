# Multi-Provider Support

<cite>
**Referenced Files in This Document**   
- [provider_manager.py](file://src/core/provider_manager.py)
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
</cite>

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

The vandamme-proxy system implements a sophisticated multi-provider support architecture that enables seamless integration with various LLM providers including OpenAI, Anthropic, Poe, Azure, Gemini, and AWS Bedrock. At the core of this system is the ProviderManager class, which orchestrates provider configuration, routing, and client management through a flexible and extensible design. The system supports both static API key configurations and client key passthrough modes, allowing for diverse deployment scenarios from simple single-provider setups to complex multi-tenant environments. This documentation details the architecture and implementation of the multi-provider system, focusing on the ProviderManager class and its interactions with configuration management, routing mechanisms, and client creation patterns.

## ProviderManager Architecture

The ProviderManager class serves as the central orchestrator for managing multiple LLM providers within the vandamme-proxy system. It implements a singleton-like pattern through lazy initialization, ensuring that provider configurations are loaded only when needed during request processing. The architecture follows a clear separation of concerns, with distinct responsibilities for configuration loading, client management, and middleware integration. The ProviderManager maintains internal dictionaries for storing provider configurations (`_configs`) and instantiated clients (`_clients`), enabling efficient lookup and reuse of resources. It also manages process-global state for API key rotation through `_api_key_locks` and `_api_key_indices`, ensuring thread-safe operation when multiple requests access the same provider. The class implements a comprehensive error handling system that provides meaningful feedback when provider configurations are invalid or incomplete.

```mermaid
classDiagram
class ProviderManager {
+default_provider : str
+default_provider_source : str
-_clients : dict[str, Client]
-_configs : dict[str, ProviderConfig]
-_loaded : bool
-_load_results : list[ProviderLoadResult]
-_api_key_locks : dict[str, asyncio.Lock]
-_api_key_indices : dict[str, int]
-middleware_chain : MiddlewareChain
-_middleware_initialized : bool
+load_provider_configs()
+get_client(provider_name, client_api_key)
+get_next_provider_api_key(provider_name)
+get_provider_config(provider_name)
+list_providers()
+print_provider_summary()
}
class ProviderConfig {
+name : str
+api_key : str
+base_url : str
+api_keys : list[str]
+api_version : str
+timeout : int
+max_retries : int
+custom_headers : dict[str, str]
+api_format : str
+tool_name_sanitization : bool
+is_azure : bool
+is_anthropic_format : bool
+uses_passthrough : bool
+get_api_keys()
+get_effective_api_key(client_api_key)
}
class ProviderLoadResult {
+name : str
+status : str
+message : str | None
+api_key_hash : str | None
+base_url : str | None
}
ProviderManager --> ProviderConfig : "manages"
ProviderManager --> ProviderLoadResult : "tracks"
ProviderManager --> OpenAIClient : "creates"
ProviderManager --> AnthropicClient : "creates"
```

**Diagram sources**
- [provider_manager.py](file://src/core/provider_manager.py#L29-L586)
- [provider_config.py](file://src/core/provider_config.py#L7-L102)

**Section sources**
- [provider_manager.py](file://src/core/provider_manager.py#L29-L586)
- [provider_config.py](file://src/core/provider_config.py#L7-L102)

## Provider Routing Mechanism

The provider routing mechanism in vandamme-proxy uses a simple yet powerful 'provider:model' syntax to direct requests to specific LLM providers. This syntax allows clients to explicitly specify which provider should handle a request by prefixing the model name with the provider identifier followed by a colon. For example, 'openai:gpt-4o' routes the request to the OpenAI provider, while 'anthropic:claude-3-5-sonnet' directs it to Anthropic. When no provider prefix is specified, the system uses the default provider configured through environment variables or TOML files. The routing process is implemented in the `parse_model_name` method of the ProviderManager class, which parses the model string and returns a tuple containing the provider name and the actual model name. This mechanism enables fine-grained control over provider selection while maintaining backward compatibility with existing client applications.

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
- [provider_manager.py](file://src/core/provider_manager.py#L408-L417)
- [model_manager.py](file://src/core/model_manager.py#L19-L91)
- [provider_context.py](file://src/api/services/provider_context.py#L21-L58)

**Section sources**
- [provider_manager.py](file://src/core/provider_manager.py#L408-L417)
- [model_manager.py](file://src/core/model_manager.py#L19-L91)
- [provider_context.py](file://src/api/services/provider_context.py#L21-L58)

## Configuration Management

The multi-provider system implements a comprehensive configuration management approach that supports multiple sources and formats. Provider configurations are primarily defined through environment variables, with each provider requiring specific environment variables such as `{PROVIDER}_API_KEY`, `{PROVIDER}_BASE_URL`, and `{PROVIDER}_API_VERSION`. The system automatically discovers providers by scanning for environment variables ending with `_API_KEY`, allowing for dynamic provider registration without code changes. In addition to environment variables, the system supports TOML-based configuration files that provide default values and additional settings. The configuration loading process follows a hierarchical approach, with environment variables taking precedence over TOML configurations, which in turn override hardcoded defaults. This layered approach enables flexible deployment scenarios, from simple environment-based configurations to complex setups with multiple configuration sources.

```mermaid
flowchart TD
Start([Configuration Loading]) --> EnvScan["Scan Environment Variables"]
EnvScan --> DefaultProvider["Load Default Provider"]
DefaultProvider --> AdditionalProviders["Load Additional Providers"]
AdditionalProviders --> TOMLCheck["Check TOML Configuration"]
TOMLCheck --> EnvOverride["Override with Environment Variables"]
EnvOverride --> Validation["Validate Configuration"]
Validation --> Result["Store Provider Config"]
Result --> End([Configuration Complete])
style Start fill:#f9f,stroke:#333
style End fill:#f9f,stroke:#333
```

**Diagram sources**
- [provider_manager.py](file://src/core/provider_manager.py#L91-L108)
- [provider_config.py](file://src/core/provider_config.py#L7-L102)
- [alias_config.py](file://src/core/alias_config.py#L27-L224)

**Section sources**
- [provider_manager.py](file://src/core/provider_manager.py#L91-L108)
- [provider_config.py](file://src/core/provider_config.py#L7-L102)
- [alias_config.py](file://src/core/alias_config.py#L27-L224)

## Factory Pattern and Client Creation

The vandamme-proxy system implements a factory pattern for dynamic provider client creation, enabling lazy loading and efficient resource management. The ProviderManager class acts as a factory that creates and manages client instances for different providers based on their API format. When a client is requested through the `get_client` method, the ProviderManager checks if a client for the specified provider already exists in its cache. If not, it creates a new client instance based on the provider's configuration, particularly the `api_format` setting which determines whether to instantiate an OpenAIClient or AnthropicClient. This factory approach enables several key benefits: clients are created only when needed (lazy loading), multiple requests to the same provider can share the same client instance, and the system can support different client types (OpenAI vs Anthropic) through a consistent interface. The factory also handles special cases such as passthrough providers, where the client is configured to use the client's API key rather than a static provider key.

```mermaid
classDiagram
class ProviderManager {
+get_client(provider_name, client_api_key)
}
class OpenAIClient {
+create_chat_completion(request)
+create_chat_completion_stream(request)
}
class AnthropicClient {
+create_chat_completion(request)
+create_chat_completion_stream(request)
}
class ClientFactory {
<<interface>>
+create_client(config, api_key)
}
ProviderManager --> ClientFactory : "implements"
ProviderManager --> OpenAIClient : "creates"
ProviderManager --> AnthropicClient : "creates"
OpenAIClient ..|> ClientFactory : "implements"
AnthropicClient ..|> ClientFactory : "implements"
```

**Diagram sources**
- [provider_manager.py](file://src/core/provider_manager.py#L419-L473)
- [client.py](file://src/core/client.py#L32-L352)
- [anthropic_client.py](file://src/core/anthropic_client.py#L25-L271)

**Section sources**
- [provider_manager.py](file://src/core/provider_manager.py#L419-L473)
- [client.py](file://src/core/client.py#L32-L352)
- [anthropic_client.py](file://src/core/anthropic_client.py#L25-L271)

## Hierarchical Configuration Loading

The vandamme-proxy system implements a hierarchical configuration loading process that combines environment variables, user configuration files, and package defaults to provide flexible and robust configuration management. The loading process begins with environment variables, which have the highest precedence and allow for runtime configuration and deployment-specific settings. When environment variables are not present, the system looks for configuration in TOML files, starting with local overrides (`vandamme-config.toml` in the current directory), then user-specific configurations (`~/.config/vandamme-proxy/vandamme-config.toml`), and finally package defaults (`src/config/defaults.toml`). This hierarchy enables a powerful configuration cascade where local settings can override user preferences, which in turn override system defaults. The system also supports provider-specific configuration options such as custom headers, timeouts, and retry limits, allowing for fine-tuned control over each provider's behavior.

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
- [provider_manager.py](file://src/core/provider_manager.py#L145-L321)
- [alias_config.py](file://src/core/alias_config.py#L32-L155)
- [defaults.toml](file://src/config/defaults.toml#L1-L89)

**Section sources**
- [provider_manager.py](file://src/core/provider_manager.py#L145-L321)
- [alias_config.py](file://src/core/alias_config.py#L32-L155)
- [defaults.toml](file://src/config/defaults.toml#L1-L89)

## Error Handling and Validation

The multi-provider system implements comprehensive error handling and validation to ensure robust operation in various deployment scenarios. The ProviderConfig class includes a `__post_init__` method that validates configuration parameters such as provider name, API key, base URL, and API format, raising descriptive errors when requirements are not met. The system specifically prevents mixed configurations where passthrough mode (`!PASSTHRU`) is combined with static API keys, ensuring clear and predictable behavior. During provider loading, the system tracks load results through the ProviderLoadResult class, capturing success, partial, and failure states with detailed messages. This information is used to generate informative summaries through the `print_provider_summary` method, which displays provider status, API key hashes, and base URLs. The client classes also implement sophisticated error handling for API interactions, including automatic key rotation on authentication failures and proper mapping of provider-specific error messages to standardized HTTP responses.

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
- [provider_config.py](file://src/core/provider_config.py#L69-L97)
- [provider_manager.py](file://src/core/provider_manager.py#L244-L321)
- [client.py](file://src/core/client.py#L23-L219)

**Section sources**
- [provider_config.py](file://src/core/provider_config.py#L69-L97)
- [provider_manager.py](file://src/core/provider_manager.py#L244-L321)
- [client.py](file://src/core/client.py#L23-L219)

## Performance Considerations

The multi-provider system incorporates several performance optimizations to handle multiple upstream services efficiently. The client classes implement connection pooling through cached HTTP clients, reducing the overhead of establishing new connections for each request. The ProviderManager maintains a cache of client instances, allowing multiple requests to reuse the same client and avoiding the cost of repeated client initialization. For providers with multiple API keys, the system implements round-robin key rotation with process-global locks to ensure thread-safe operation while distributing load across available keys. The system also supports streaming responses with proper cancellation handling, allowing long-running requests to be terminated gracefully without resource leaks. Configuration loading is designed to be lazy, with providers loaded only when first accessed, reducing startup time and memory usage. The system also includes configurable timeouts and retry limits, allowing administrators to tune performance characteristics based on their specific deployment requirements and provider capabilities.

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
- [client.py](file://src/core/client.py#L53-L86)
- [provider_manager.py](file://src/core/provider_manager.py#L44-L46)
- [anthropic_client.py](file://src/core/anthropic_client.py#L50-L54)
- [client.py](file://src/core/client.py#L109-L137)

**Section sources**
- [client.py](file://src/core/client.py#L53-L86)
- [provider_manager.py](file://src/core/provider_manager.py#L44-L46)
- [anthropic_client.py](file://src/core/anthropic_client.py#L50-L54)

## Integration with Alias System

The multi-provider system integrates closely with the alias system to provide flexible model name resolution and provider abstraction. The ModelManager class coordinates between the ProviderManager and AliasManager to resolve model names through a multi-step process: first applying alias resolution if available, then parsing the provider prefix, and finally returning the resolved provider and model name. This integration allows users to define aliases in TOML configuration files that can reference specific providers or use provider-specific aliases. For example, an alias 'haiku' might resolve to different models depending on the context provider, enabling consistent naming across different providers. The system also supports cross-provider aliases, where an alias can reference a model on a different provider, facilitating migration between providers or cost-based routing. The alias resolution process is designed to be efficient, with caching mechanisms to avoid repeated parsing and resolution operations.

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
- [provider_manager.py](file://src/core/provider_manager.py#L408-L417)

**Section sources**
- [model_manager.py](file://src/core/model_manager.py#L19-L91)
- [alias_config.py](file://src/core/alias_config.py#L157-L175)

## Practical Configuration Examples

The vandamme-proxy system provides several practical configuration examples that demonstrate different deployment scenarios for the multi-provider system. The `multi-provider.env` example shows how to configure multiple providers including OpenAI, Anthropic, AWS Bedrock, and Azure, with each provider having its own API key and base URL. This configuration enables clients to route requests to different providers using the 'provider:model' syntax. The `anthropic-direct.env` example demonstrates a simple setup with direct Anthropic API access, setting the default provider to Anthropic. The `aws-bedrock.env` example shows configuration for AWS Bedrock with Claude models, including AWS-specific settings like region and custom headers. The `google-vertex.env` example illustrates configuration for Google Vertex AI with Anthropic models, including Google Cloud project settings. These examples provide templates for common use cases and can be customized based on specific requirements, such as adding custom headers, adjusting timeouts, or configuring multiple API keys for load balancing and failover.

```mermaid
graph TD
A[Configuration Examples] --> B[multi-provider.env]
A --> C[anthropic-direct.env]
A --> D[aws-bedrock.env]
A --> E[google-vertex.env]
B --> F[Multiple Providers]
B --> G[OpenAI, Anthropic, AWS, Azure]
B --> H[Provider-Specific Settings]
C --> I[Direct Anthropic Access]
C --> J[Default Provider: Anthropic]
C --> K[Simplified Configuration]
D --> L[AWS Bedrock]
D --> M[Claude Models]
D --> N[AWS Region Settings]
D --> O[Custom Headers]
E --> P[Google Vertex AI]
E --> Q[Anthropic Models]
E --> R[GCP Project Settings]
E --> S[Custom Headers]
style A fill:#f9f,stroke:#333
```

**Diagram sources**
- [multi-provider.env](file://examples/multi-provider.env#L1-L48)
- [anthropic-direct.env](file://examples/anthropic-direct.env#L1-L22)
- [aws-bedrock.env](file://examples/aws-bedrock.env#L1-L32)
- [google-vertex.env](file://examples/google-vertex.env#L1-L32)

**Section sources**
- [multi-provider.env](file://examples/multi-provider.env#L1-L48)
- [anthropic-direct.env](file://examples/anthropic-direct.env#L1-L22)
- [aws-bedrock.env](file://examples/aws-bedrock.env#L1-L32)
- [google-vertex.env](file://examples/google-vertex.env#L1-L32)