# API Reference

<cite>
**Referenced Files in This Document**   
- [endpoints.py](file://src/api/endpoints.py)
- [v1.py](file://src/api/routers/v1.py)
- [api-key-passthrough.md](file://docs/api-key-passthrough.md)
- [streaming.py](file://src/api/services/streaming.py)
- [anthropic_sse_to_openai.py](file://src/conversion/anthropic_sse_to_openai.py)
- [openai.py](file://src/models/openai.py)
- [claude.py](file://src/models/claude.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Authentication](#authentication)
3. [OpenAI-Compatible Endpoints](#openai-compatible-endpoints)
   - [/v1/chat/completions](#v1chatcompletions)
   - [/v1/completions](#v1completions)
   - [/v1/embeddings](#v1embeddings)
4. [Anthropic Passthrough Endpoints](#anthropic-passthrough-endpoints)
   - [/v1/messages](#v1messages)
   - [/v1/messages/count_tokens](#v1messagescount_tokens)
5. [Provider-Specific Endpoints](#provider-specific-endpoints)
   - [/v1/models](#v1models)
   - [/v1/aliases](#v1aliases)
6. [Health and Utility Endpoints](#health-and-utility-endpoints)
   - [/health](#health)
   - [/test-connection](#test-connection)
   - [/top-models](#top-models)
   - [/](#)
7. [Streaming Implementation](#streaming-implementation)
8. [Error Responses](#error-responses)
9. [Security Considerations](#security-considerations)

## Introduction
The Vandamme Proxy provides a unified API interface that supports both OpenAI-compatible and Anthropic-native endpoints. This API reference documents all exposed endpoints, their request/response schemas, authentication methods, and implementation details. The proxy acts as a translation layer between different LLM provider APIs, allowing clients to use familiar interfaces while routing requests to various backend providers.

The API supports OpenAI-style chat completions, Anthropic Messages API passthrough, model listing, alias management, and health monitoring. Key features include API key passthrough, streaming support via Server-Sent Events (SSE), and comprehensive error handling.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1-L1418)
- [v1.py](file://src/api/routers/v1.py#L1-L34)

## Authentication
The API supports two methods for providing authentication credentials:

1. **x-api-key header**: Direct API key transmission
2. **Authorization header**: Bearer token format

The proxy validates client API keys when `PROXY_API_KEY` is configured in the environment. For providers configured with API key passthrough (`!PASSTHRU`), the client's API key is forwarded directly to the upstream provider.

When API key passthrough is enabled for a provider, clients must provide a valid API key in their request, which will be used to authenticate with the target provider. This allows clients to use their own provider credentials through the proxy.

```bash
# Example with x-api-key header
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{...}'

# Example with Authorization header
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{...}'
```

For passthrough providers, the configuration uses the `!PASSTHRU` sentinel value to indicate that client keys should be forwarded:

```bash
# In .env file
OPENAI_API_KEY=!PASSTHRU
```

This approach provides security advantages by requiring explicit configuration for passthrough behavior and preventing accidental exposure of provider credentials.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L112-L138)
- [api-key-passthrough.md](file://docs/api-key-passthrough.md#L1-L211)

## OpenAI-Compatible Endpoints

### /v1/chat/completions
The `/v1/chat/completions` endpoint provides OpenAI-compatible chat completion functionality. It supports both streaming and non-streaming responses and can route requests to various provider backends.

**HTTP Method**: POST  
**URL Pattern**: `/v1/chat/completions`

#### Request Parameters
| Parameter | Type | Required | Description |
|---------|------|----------|-------------|
| model | string | Yes | Model identifier, which may include provider prefix (e.g., "openai:gpt-4o-mini") |
| messages | array | Yes | Array of message objects with role and content |
| stream | boolean | No | Whether to stream the response (default: false) |
| temperature | number | No | Sampling temperature |
| max_tokens | integer | No | Maximum number of tokens to generate |

#### Request Body Structure
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": false
}
```

#### Example curl Request
```bash
curl -X POST http://localhost:8082/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

#### Response Format
For non-streaming requests, returns a standard OpenAI chat completion response:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}
```

For streaming requests, returns Server-Sent Events (SSE) with `text/event-stream` content type.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L171-L388)
- [openai.py](file://src/models/openai.py#L8-L15)

### /v1/completions
The `/v1/completions` endpoint is not explicitly implemented in the current codebase. The primary text generation endpoint is `/v1/chat/completions` which follows the chat-based interface pattern. Legacy completion endpoints may be available through the router registration, but the main supported interface is the chat completions endpoint.

### /v1/embeddings
The `/v1/embeddings` endpoint is not explicitly implemented in the current codebase. The proxy focuses on chat completion and message-based interfaces rather than embedding generation. Clients requiring embedding functionality should use the native provider APIs directly or request this feature for future implementation.

## Anthropic Passthrough Endpoints

### /v1/messages
The `/v1/messages` endpoint provides native Anthropic Messages API compatibility with passthrough support for Anthropic-format providers.

**HTTP Method**: POST  
**URL Pattern**: `/v1/messages`

#### Request Parameters
| Parameter | Type | Required | Description |
|---------|------|----------|-------------|
| model | string | Yes | Model identifier with optional provider prefix |
| max_tokens | integer | Yes | Maximum tokens to generate |
| messages | array | Yes | Array of message objects |
| stream | boolean | No | Whether to stream the response |
| system | string | No | System message content |
| tools | array | No | Array of tool definitions for function calling |
| temperature | number | No | Sampling temperature |

#### Request Body Structure
```json
{
  "model": "claude-3-haiku-20240307",
  "max_tokens": 100,
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": false
}
```

#### Example curl Request
```bash
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "model": "claude-3-haiku-20240307",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

#### Response Format
Returns a native Anthropic Messages API response:
```json
{
  "id": "msg_123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I help you?"
    }
  ],
  "model": "claude-3-haiku-20240307",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 9,
    "output_tokens": 12
  }
}
```

For streaming requests, returns Server-Sent Events (SSE) with `text/event-stream` content type, maintaining compatibility with Anthropic's streaming format.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L391-L903)
- [claude.py](file://src/models/claude.py#L57-L71)

### /v1/messages/count_tokens
The `/v1/messages/count_tokens` endpoint estimates or calculates the token count for a given message request.

**HTTP Method**: POST  
**URL Pattern**: `/v1/messages/count_tokens`

#### Request Parameters
| Parameter | Type | Required | Description |
|---------|------|----------|-------------|
| model | string | Yes | Model identifier |
| messages | array | Yes | Array of message objects to count |
| system | string | No | System message content |

#### Request Body Structure
```json
{
  "model": "claude-3-haiku-20240307",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ]
}
```

#### Example curl Request
```bash
curl -X POST http://localhost:8082/v1/messages/count_tokens \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "model": "claude-3-haiku-20240307",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

#### Response Format
Returns token count estimation:
```json
{
  "input_tokens": 9
}
```

The endpoint first attempts to use the provider's native token counting capability when available. If not supported, it falls back to character-based estimation (approximately 4 characters per token).

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L905-L995)
- [claude.py](file://src/models/claude.py#L73-L80)

## Provider-Specific Endpoints

### /v1/models
The `/v1/models` endpoint lists available models from the configured providers.

**HTTP Method**: GET  
**URL Pattern**: `/v1/models`

#### Query Parameters
| Parameter | Type | Required | Description |
|---------|------|----------|-------------|
| provider | string | No | Specific provider to fetch models from |
| format | string | No | Response format: "anthropic", "openai", or "raw" |
| refresh | boolean | No | Force refresh from upstream (bypass cache) |

#### Headers
| Header | Description |
|--------|-------------|
| provider | Provider override (takes precedence over query parameter) |
| anthropic-version | When present, infers response format as Anthropic |

#### Example curl Request
```bash
curl -X GET "http://localhost:8082/v1/models?format=openai&provider=openai" \
  -H "x-api-key: your-api-key"
```

#### Response Format
Returns models in the requested format:
```json
{
  "data": [
    {
      "id": "gpt-4o-mini",
      "object": "model",
      "created": 1677610600,
      "owned_by": "openai"
    }
  ],
  "object": "list"
}
```

The endpoint supports multiple response formats and maintains a disk cache of model listings to reduce upstream API calls.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1155-L1292)

### /v1/aliases
The `/v1/aliases` endpoint lists all configured model aliases grouped by provider.

**HTTP Method**: GET  
**URL Pattern**: `/v1/aliases`

#### Example curl Request
```bash
curl -X GET http://localhost:8082/v1/aliases \
  -H "x-api-key: your-api-key"
```

#### Response Format
```json
{
  "object": "list",
  "aliases": {
    "poe": {
      "haiku": "gpt-4o-mini",
      "sonnet": "gpt-4o"
    },
    "openai": {
      "fast": "gpt-4o-mini"
    }
  },
  "suggested": {
    "default": {
      "coding": "claude-3-5-sonnet-20241022"
    }
  },
  "total": 3
}
```

The response includes both configured aliases and suggested aliases derived from top models data.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1295-L1343)

## Health and Utility Endpoints

### /health
The `/health` endpoint provides comprehensive health check information.

**HTTP Method**: GET  
**URL Pattern**: `/health`

#### Example curl Request
```bash
curl -X GET http://localhost:8082/health
```

#### Response Format
Returns YAML-formatted health information:
```yaml
status: healthy
timestamp: '2024-01-15T10:00:00'
api_key_valid: true
client_api_key_validation: true
default_provider: openai
providers:
  openai:
    api_format: openai
    base_url: https://api.openai.com
    api_key_hash: sha256:abc123
```

The health check verifies API key validity, provider configurations, and connectivity.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L998-L1070)

### /test-connection
The `/test-connection` endpoint tests connectivity to the default provider.

**HTTP Method**: GET  
**URL Pattern**: `/test-connection`

#### Example curl Request
```bash
curl -X GET http://localhost:8082/test-connection
```

#### Response Format
```json
{
  "status": "success",
  "message": "Successfully connected to openai API",
  "provider": "openai",
  "model_used": "gpt-4o-mini",
  "timestamp": "2024-01-15T10:00:00",
  "response_id": "cmpl-123"
}
```

This endpoint performs a simple test request to verify API connectivity and authentication.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1072-L1134)

### /top-models
The `/top-models` endpoint provides curated top model recommendations.

**HTTP Method**: GET  
**URL Pattern**: `/top-models`

#### Query Parameters
| Parameter | Type | Required | Description |
|---------|------|----------|-------------|
| limit | integer | No | Number of models to return (default: 10) |
| refresh | boolean | No | Force refresh from source |
| provider | string | No | Filter by specific provider |
| include_cache_info | boolean | No | Include cache metadata |

#### Example curl Request
```bash
curl -X GET "http://localhost:8082/top-models?limit=5" \
  -H "x-api-key: your-api-key"
```

#### Response Format
```json
{
  "object": "top_models",
  "source": "manual",
  "last_updated": "2024-01-15T10:00:00",
  "providers": ["openai", "anthropic"],
  "models": [
    {
      "name": "claude-3-5-sonnet-20241022",
      "provider": "anthropic",
      "sub_provider": "native",
      "ranking": 1,
      "category": "coding"
    }
  ],
  "suggested_aliases": {
    "coding": "claude-3-5-sonnet-20241022"
  }
}
```

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1346-L1392)

### /
The root endpoint provides basic server information.

**HTTP Method**: GET  
**URL Pattern**: `/`

#### Example curl Request
```bash
curl -X GET http://localhost:8082/
```

#### Response Format
```json
{
  "message": "VanDamme Proxy v1.0.0",
  "status": "running",
  "config": {
    "base_url": "http://localhost:8082",
    "max_tokens_limit": 4096,
    "api_key_configured": true,
    "client_api_key_validation": true
  },
  "endpoints": {
    "messages": "/v1/messages",
    "count_tokens": "/v1/messages/count_tokens",
    "running_totals": "/metrics/running-totals",
    "models": "/v1/models",
    "aliases": "/v1/aliases",
    "top_models": "/top-models",
    "health": "/health",
    "test_connection": "/test-connection"
  }
}
```

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1395-L1418)

## Streaming Implementation
The API implements streaming responses using Server-Sent Events (SSE) for both OpenAI-compatible and Anthropic-native endpoints.

### SSE Headers
All streaming responses include the following headers:
```http
Cache-Control: no-cache
Connection: keep-alive
Content-Type: text/event-stream
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: *
```

### Streaming Behavior
- Streaming responses use `text/event-stream` content type
- Each chunk is sent as an SSE event with `data:` prefix
- Final message is `[DONE]` followed by double newline
- Client should handle partial responses incrementally

### Error Handling in Streams
When errors occur during streaming, the API sends an error event followed by `[DONE]`:
```text
data: {"error": {"message": "Upstream read timeout", "type": "upstream_timeout", "code": "read_timeout", "suggestion": "Consider increasing REQUEST_TIMEOUT"}}
data: [DONE]
```

The streaming implementation includes error handling wrappers that catch exceptions mid-stream and send appropriate error events without crashing the connection.

```mermaid
flowchart TD
A[Client Request with stream=true] --> B{Provider Type}
B --> |Anthropic-format| C[Direct SSE Passthrough]
B --> |OpenAI-format| D[Convert to OpenAI SSE]
C --> E[Apply Error Handling Wrapper]
D --> F[Apply Conversion & Error Handling]
E --> G[Stream Events with sse_headers]
F --> G
G --> H[Client Receives data: chunks]
H --> I{Complete?}
I --> |Yes| J[Send data: [DONE]]
I --> |Error| K[Send Error Event + [DONE]]
```

**Diagram sources**
- [streaming.py](file://src/api/services/streaming.py#L18-L242)
- [anthropic_sse_to_openai.py](file://src/conversion/anthropic_sse_to_openai.py#L150-L156)

**Section sources**
- [streaming.py](file://src/api/services/streaming.py#L1-L242)
- [endpoints.py](file://src/api/endpoints.py#L273-L290)

## Error Responses
The API returns standardized error responses for various failure scenarios.

### HTTP Status Codes
| Status Code | Meaning | Description |
|------------|--------|-------------|
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Invalid or missing API key |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 503 | Service Unavailable | Upstream service unavailable |
| 504 | Gateway Timeout | Upstream request timed out |

### Error Response Format
Standard JSON error response:
```json
{
  "type": "error",
  "error": {
    "type": "api_error",
    "message": "Invalid API key. Please provide a valid Anthropic API key."
  }
}
```

### Streaming Error Format
SSE error event:
```text
data: {"error": {"message": "Upstream read timeout", "type": "upstream_timeout", "code": "read_timeout"}}
data: [DONE]
```

### Common Errors
**Invalid API Key**:
```json
{
  "type": "error",
  "error": {
    "type": "api_error",
    "message": "Invalid API key. Please provide a valid Anthropic API key."
  }
}
```

**Provider Requires Passthrough**:
```json
{
  "type": "error",
  "error": {
    "type": "api_error",
    "message": "Provider 'openai' requires API key passthrough, but no client API key was provided"
  }
}
```

**Timeout Error**:
```json
{
  "type": "error",
  "error": {
    "type": "upstream_timeout",
    "message": "Upstream request timed out. Consider increasing REQUEST_TIMEOUT."
  }
}
```

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L131-L136)
- [api-key-passthrough.md](file://docs/api-key-passthrough.md#L189-L209)

## Security Considerations
The API includes several security features to protect against common vulnerabilities.

### API Key Passthrough Security
The passthrough feature uses explicit sentinel values (`!PASSTHRU`) to prevent accidental exposure of provider credentials. Key security principles include:

- **Explicit Configuration**: Providers must be explicitly marked for passthrough
- **No Mixed Modes**: Cannot mix static keys with passthrough for the same provider
- **Auditability**: Configuration clearly shows which providers use client keys
- **Hashed Logging**: API keys are hashed in logs (first 8 characters of SHA256)

### Authentication Bypass Risks
When `PROXY_API_KEY` is not set, client API key validation is disabled, potentially allowing unauthorized access. To mitigate this risk:

1. Always set `PROXY_API_KEY` in production environments
2. Use network-level controls (firewalls, VPCs) to restrict access
3. Monitor API usage and set up alerts for unusual patterns
4. Implement rate limiting to prevent abuse

### Rate Limiting
While not explicitly implemented in the provided code, rate limiting should be considered for production deployments. Options include:

- Client IP-based rate limiting
- API key-based rate limiting
- Token-based rate limiting
- Request volume-based rate limiting

The proxy should be deployed behind a reverse proxy or API gateway that can handle rate limiting, or implement rate limiting middleware.

### Input Validation
The API performs basic input validation through Pydantic models, ensuring that requests conform to expected schemas. However, additional validation may be needed for specific use cases, such as:

- Content filtering
- Prompt injection protection
- Size limits on inputs
- Allowed model restrictions

**Section sources**
- [api-key-passthrough.md](file://docs/api-key-passthrough.md#L1-L211)
- [endpoints.py](file://src/api/endpoints.py#L112-L138)