# Streaming Implementation

<cite>
**Referenced Files in This Document**   
- [endpoints.py](file://src/api/endpoints.py)
- [streaming.py](file://src/api/services/streaming.py)
- [response_converter.py](file://src/conversion/response_converter.py)
- [openai_stream_to_claude_state_machine.py](file://src/conversion/openai_stream_to_claude_state_machine.py)
- [anthropic_sse_to_openai.py](file://src/conversion/anthropic_sse_to_openai.py)
- [error_handling.py](file://src/api/services/error_handling.py)
- [26-vdm-active-requests-sse.js](file://assets/ag_grid/26-vdm-active-requests-sse.js)
- [25-vdm-metrics-active-requests.js](file://assets/ag_grid/25-vdm-metrics-active-requests.js)
- [metrics.py](file://src/api/metrics.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Server-Sent Events (SSE) Protocol](#server-sent-events-sse-protocol)
3. [Streaming Response Generation](#streaming-response-generation)
4. [Error Handling in Streaming](#error-handling-in-streaming)
5. [Streaming Format Conversion](#streaming-format-conversion)
6. [Active Requests Monitoring](#active-requests-monitoring)
7. [Client-Side Handling](#client-side-handling)
8. [Conclusion](#conclusion)

## Introduction
This document provides comprehensive documentation for the streaming implementation in the API, focusing on the Server-Sent Events (SSE) protocol used for streaming responses. The system supports both OpenAI and Anthropic streaming formats, with conversion utilities to bridge between them. The implementation includes robust error handling, metrics tracking, and real-time monitoring capabilities through the dashboard. The core components are located in `src/api/endpoints.py` for endpoint definitions, `src/api/services/streaming.py` for streaming utilities, and `src/conversion/` for format conversion logic.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1-L1418)
- [streaming.py](file://src/api/services/streaming.py#L1-L242)

## Server-Sent Events (SSE) Protocol
The API uses Server-Sent Events (SSE) for streaming responses, providing a standardized way to push real-time data from the server to clients. The SSE implementation follows the W3C specification with specific headers and event formatting.

### SSE Headers
The `sse_headers()` function in `src/api/services/streaming.py` defines the standard headers used for all SSE responses:

```python
def sse_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
    }
```

These headers ensure:
- No caching of streaming responses
- Persistent connection for event streaming
- Cross-origin resource sharing (CORS) support
- Compatibility with various client implementations

### Streaming Response Utility
The `streaming_response()` function creates FastAPI StreamingResponse objects with the appropriate media type and headers:

```python
def streaming_response(
    *,
    stream: AnySseStream,
    headers: dict[str, str] | None = None,
) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=headers or sse_headers(),
    )
```

This utility:
- Sets the media type to `text/event-stream`
- Applies SSE headers (defaulting to `sse_headers()` if none provided)
- Wraps the async generator stream for proper SSE formatting

**Section sources**
- [streaming.py](file://src/api/services/streaming.py#L18-L37)

## Streaming Response Generation
The API generates streaming responses for both `chat_completions` and `create_message` endpoints, handling both OpenAI and Anthropic formats.

### Async Generator Patterns
Streaming responses use async generators to yield SSE-formatted chunks incrementally. The pattern follows:

1. Create an async generator function that yields SSE-formatted strings
2. Wrap the generator with error handling and metrics finalization
3. Return a StreamingResponse with the wrapped stream

For OpenAI-format providers, the streaming pattern is straightforward:

```python
async def openai_stream_as_sse_lines() -> AsyncGenerator[str, None]:
    async for chunk in openai_stream:
        yield f"{chunk}\n"

return streaming_response(
    stream=with_streaming_error_handling(
        original_stream=openai_stream_as_sse_lines(),
        http_request=http_request,
        request_id=request_id,
        provider_name=provider_name,
        metrics_enabled=LOG_REQUEST_METRICS,
    ),
    headers=sse_headers(),
)
```

For Anthropic-format providers, additional conversion is required:

```python
async def anthropic_stream_as_openai() -> AsyncGenerator[str, None]:
    async for chunk in anthropic_sse_to_openai_chat_completions_sse(
        anthropic_sse_lines=anthropic_stream,
        model=resolved_model,
        completion_id=f"chatcmpl-{request_id}",
    ):
        yield chunk

return streaming_response(
    stream=with_streaming_error_handling(
        original_stream=anthropic_stream_as_openai(),
        http_request=http_request,
        request_id=request_id,
        provider_name=provider_name,
        metrics_enabled=LOG_REQUEST_METRICS,
    ),
    headers=sse_headers(),
)
```

### Endpoint Implementation
The `chat_completions` and `create_message` endpoints in `src/api/endpoints.py` implement streaming based on the `stream` parameter in the request. When `stream=True`, they return a `StreamingResponse`; otherwise, they return a `JSONResponse` with the complete response.

The endpoints handle:
- Request validation and API key authentication
- Provider context resolution
- Model alias resolution
- Metrics tracking
- Error handling
- Format conversion between OpenAI and Anthropic

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L171-L388)
- [endpoints.py](file://src/api/endpoints.py#L391-L851)

## Error Handling in Streaming
The streaming implementation includes comprehensive error handling to ensure robustness and proper client communication.

### with_streaming_error_handling Decorator
The `with_streaming_error_handling` decorator in `src/api/services/streaming.py` wraps streaming generators to handle errors gracefully:

```python
def with_streaming_error_handling(
    *,
    original_stream: AsyncGenerator[str, None],
    http_request: Request,
    request_id: str,
    provider_name: str | None = None,
    metrics_enabled: bool,
) -> AsyncGenerator[str, None]:
    async def _wrapped() -> AsyncGenerator[str, None]:
        # Apply error handling first (inner layer)
        error_handled_stream = with_sse_error_handler(
            original_stream=original_stream,
            request_id=request_id,
            provider_name=provider_name,
        )
        # Then apply metrics finalization (outer layer, in finally)
        metrics_finalized_stream = with_streaming_metrics_finalizer(
            original_stream=error_handled_stream,
            http_request=http_request,
            request_id=request_id,
            enabled=metrics_enabled,
        )
        async for chunk in metrics_finalized_stream:
            yield chunk
    return _wrapped()
```

This decorator composes two layers:
1. **SSE error handling**: Catches exceptions and emits error events
2. **Metrics finalization**: Ensures metrics are finalized regardless of success or failure

### Error Event Formatting
When streaming errors occur, the system emits properly formatted SSE error events:

```python
def _format_sse_error_event(
    *,
    message: str,
    error_type: str = "upstream_timeout",
    code: str = "read_timeout",
    suggestion: str | None = None,
) -> str:
    error_payload: dict[str, Any] = {
        "error": {
            "message": message,
            "type": error_type,
            "code": code,
        }
    }
    if suggestion:
        error_payload["error"]["suggestion"] = suggestion
    return f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
```

The error event includes:
- Human-readable error message
- Error type/category
- Error code
- Optional actionable suggestion

Common error types include:
- `upstream_timeout`: Upstream read or connection timeout
- `upstream_http_error`: HTTP error from upstream provider
- `streaming_error`: General streaming error

### Error Recovery Mechanisms
The system handles various error scenarios:

1. **Timeout errors**: Converted to HTTP 504 Gateway Timeout
2. **Client disconnection**: Detected via `http_request.is_disconnected()`
3. **Upstream HTTP errors**: Emitted as SSE error events
4. **JSON parsing errors**: Handled with `SSEParseError`

The error handling ensures that:
- Metrics are properly finalized
- Clients receive meaningful error information
- The connection is properly closed with `[DONE]`
- No "response already started" errors occur

**Section sources**
- [streaming.py](file://src/api/services/streaming.py#L40-L241)
- [error_handling.py](file://src/api/services/error_handling.py#L16-L93)

## Streaming Format Conversion
The system supports conversion between OpenAI and Anthropic streaming formats, enabling interoperability between different provider APIs.

### OpenAI to Anthropic Conversion
The `convert_openai_streaming_to_claude_with_cancellation` function in `src/conversion/response_converter.py` converts OpenAI streaming responses to Anthropic format:

```python
async def convert_openai_streaming_to_claude_with_cancellation(
    openai_stream: Any,
    original_request: ClaudeMessagesRequest,
    logger: Any,
    http_request: Request,
    openai_client: Any,
    request_id: str,
    tool_name_map_inverse: dict[str, str] | None = None,
) -> AsyncGenerator[str, None]:
```

This function:
- Handles client cancellation via `http_request.is_disconnected()`
- Updates metrics during streaming
- Converts OpenAI SSE events to Anthropic SSE events
- Supports tool call conversion
- Emits proper final events

The conversion uses a state machine (`OpenAIToClaudeStreamState`) to maintain context across chunks.

### Anthropic to OpenAI Conversion
The `anthropic_sse_to_openai_chat_completions_sse` function in `src/conversion/anthropic_sse_to_openai.py` converts Anthropic SSE events to OpenAI format:

```python
async def anthropic_sse_to_openai_chat_completions_sse(
    *,
    anthropic_sse_lines: AsyncGenerator[str, None],
    model: str,
    completion_id: str,
) -> AsyncGenerator[str, None]:
```

This function:
- Parses Anthropic SSE events
- Translates text deltas to OpenAI format
- Maps finish reasons
- Handles tool calls
- Emits OpenAI-style SSE lines

### State Machine Implementation
The conversion process uses a state machine approach to ensure proper event ordering and completeness:

```python
@dataclass
class OpenAIToClaudeStreamState:
    message_id: str
    tool_name_map_inverse: dict[str, str]
    text_block_index: int = 0
    tool_block_counter: int = 0
    tool_id_allocator: ToolCallIdAllocator = field(init=False)
    args_assembler: ToolCallArgsAssembler = field(default_factory=ToolCallArgsAssembler)
    current_tool_calls: dict[int, ToolCallIndexState] = field(default_factory=dict)
    final_stop_reason: str = Constants.STOP_END_TURN
```

The state machine ensures:
- Proper ordering of content block events
- Correct tool call ID allocation
- Complete JSON argument assembly
- Accurate stop reason mapping

**Section sources**
- [response_converter.py](file://src/conversion/response_converter.py#L113-L333)
- [openai_stream_to_claude_state_machine.py](file://src/conversion/openai_stream_to_claude_state_machine.py#L1-L245)
- [anthropic_sse_to_openai.py](file://src/conversion/anthropic_sse_to_openai.py#L1-L264)

## Active Requests Monitoring
The system uses SSE to push real-time updates about active requests to the dashboard, providing visibility into ongoing operations.

### SSE Endpoint
The `/metrics/active-requests/stream` endpoint in `src/api/metrics.py` provides a real-time stream of active requests:

```python
@metrics_router.get("/active-requests/stream", response_model=None)
async def stream_active_requests(
    http_request: Request,
    _: None = Depends(validate_api_key),
) -> StreamingResponse | JSONResponse:
```

This endpoint:
- Emits updates when the active requests snapshot changes
- Sends a heartbeat comment every 30 seconds
- Handles client disconnection
- Respects the `LOG_REQUEST_METRICS` configuration

### JavaScript Implementation
The client-side implementation in `assets/ag_grid/26-vdm-active-requests-sse.js` handles the SSE stream:

```javascript
function connectSSE() {
    const url = getSSEUrl();
    eventSource = new EventSource(url);
    
    eventSource.addEventListener('update', onMessage);
    eventSource.addEventListener('disabled', onMessage);
    
    eventSource.onopen = () => {
        console.log('[vdm][sse] Connected');
        updateConnectionIndicator(true);
    };
    
    eventSource.onerror = (e) => {
        updateConnectionIndicator(false);
        // Auto-reconnect with backoff
    };
}
```

Key features:
- Automatic reconnection with exponential backoff
- Connection status indicator
- SPA navigation support
- Page visibility awareness
- Duplicate request ID handling

### Data Transformation
The JavaScript code transforms the API response to AG Grid format:

```javascript
function formatActiveRequestsRowData(apiRow) {
    return {
        request_id: apiRow.request_id || '',
        provider: apiRow.provider || 'unknown',
        provider_color: getProviderBadgeColor(provider),
        model: model,
        resolved_model: apiRow.resolved_model || '',
        is_streaming: Boolean(apiRow.is_streaming),
        input_tokens: apiRow.input_tokens || 0,
        output_tokens: apiRow.output_tokens || 0,
        // ... other fields
    };
}
```

The transformation includes:
- Provider badge color mapping
- Timestamp conversion
- Field renaming for grid compatibility
- Age calculation for recency display

### Update Frequency
The system updates the active requests display based on:
- Immediate updates when requests start or complete
- Periodic snapshots at the configured interval (default 2 seconds)
- Heartbeat messages every 30 seconds to keep the connection alive

The update frequency is configurable via `active_requests_sse_interval` and `active_requests_sse_heartbeat` settings.

**Section sources**
- [metrics.py](file://src/api/metrics.py#L81-L173)
- [26-vdm-active-requests-sse.js](file://assets/ag_grid/26-vdm-active-requests-sse.js#L1-L316)
- [25-vdm-metrics-active-requests.js](file://assets/ag_grid/25-vdm-metrics-active-requests.js#L1-L95)

## Client-Side Handling
This section provides examples of how clients can handle the streaming responses and SSE events.

### SSE Event Formatting
The API emits SSE events in the following format:

```
event: message_start
data: {"type":"message_start","message":{"id":"msg_123","type":"message","role":"assistant","model":"claude-3-opus-20240229","content":[],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":0,"output_tokens":0}}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

data: {"object":"chat.completion.chunk","created":1707584392,"model":"gpt-4-turbo","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}
```

Key characteristics:
- Events use the `event:` prefix for named events
- Data uses the `data:` prefix for JSON payloads
- Each event ends with `\n\n`
- The stream terminates with `data: [DONE]\n\n`

### Client Implementation Examples
Clients can handle the streaming responses using various approaches:

**JavaScript (Fetch API):**
```javascript
const response = await fetch('/v1/messages', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'x-api-key': 'your-api-key'
    },
    body: JSON.stringify({
        model: 'claude-3-opus-20240229',
        messages: [{role: 'user', content: 'Hello'}],
        stream: true
    })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    // Process SSE events
    console.log(chunk);
}
```

**Python (httpx):**
```python
import httpx

async with httpx.AsyncClient() as client:
    async with client.stream(
        'POST',
        'http://localhost:8000/v1/messages',
        json={
            'model': 'claude-3-opus-20240229',
            'messages': [{'role': 'user', 'content': 'Hello'}],
            'stream': True
        },
        headers={'x-api-key': 'your-api-key'}
    ) as response:
        async for line in response.aiter_lines():
            if line.strip():
                print(line)
```

### Error Handling on Client Side
Clients should handle the following error scenarios:

1. **Network errors**: Reconnection logic with exponential backoff
2. **Timeout errors**: User feedback and retry options
3. **Parsing errors**: Graceful degradation and error reporting
4. **Cancellation**: Proper cleanup of resources

Example error handling:
```javascript
eventSource.onerror = (e) => {
    console.error('SSE connection error:', e);
    // Show user feedback
    showConnectionError();
    // Auto-reconnect will be handled by EventSource
};
```

### Best Practices
When implementing client-side streaming:

1. **Handle reconnection**: Implement robust reconnection logic
2. **Parse incrementally**: Process events as they arrive
3. **Display progress**: Show streaming indicators to users
4. **Handle errors gracefully**: Provide meaningful error messages
5. **Respect cancellation**: Allow users to cancel long-running requests
6. **Manage memory**: Avoid memory leaks with large responses

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L171-L851)
- [streaming.py](file://src/api/services/streaming.py#L18-L241)

## Conclusion
The streaming implementation in the API provides a robust and flexible system for handling real-time responses from AI providers. Key features include:

- **Standardized SSE protocol** with proper headers and event formatting
- **Dual-format support** for both OpenAI and Anthropic streaming
- **Comprehensive error handling** with graceful degradation
- **Real-time monitoring** through the dashboard's active requests view
- **Efficient conversion** between different streaming formats
- **Client-friendly design** with clear error messages and proper termination

The system is designed to be reliable, performant, and easy to use, providing a seamless experience for both API consumers and dashboard users. The modular architecture allows for easy extension and maintenance, with clear separation of concerns between streaming utilities, format conversion, and error handling.

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L1-L1418)
- [streaming.py](file://src/api/services/streaming.py#L1-L242)
- [response_converter.py](file://src/conversion/response_converter.py#L1-L333)