# Request Tracking Mechanism

<cite>
**Referenced Files in This Document**
- [tracker.py](file://src/core/metrics/tracker/tracker.py)
- [request.py](file://src/core/metrics/models/request.py)
- [summary.py](file://src/core/metrics/models/summary.py)
- [hierarchical.py](file://src/core/metrics/calculations/hierarchical.py)
- [factory.py](file://src/core/metrics/tracker/factory.py)
- [runtime.py](file://src/core/metrics/runtime.py)
- [types.py](file://src/core/metrics/types.py)
- [provider.py](file://src/core/metrics/models/provider.py)
- [endpoints.py](file://src/api/endpoints.py)
- [streaming.py](file://src/api/services/streaming.py)
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
This document provides comprehensive data model documentation for the RequestTracker class, focusing on how it manages both active and completed request metrics within a single process. The RequestTracker implements a two-state model: active requests stored in-memory during execution and completed requests aggregated into summary metrics. It exposes thread-safe operations using asyncio primitives and provides hierarchical aggregation for provider/model filtering with optional inclusion of active requests.

## Project Structure
The request tracking mechanism spans several modules within the metrics subsystem:
- Tracker implementation: manages state, lifecycle events, and synchronization
- Data models: define the structure for request-level and summary metrics
- Calculations: provide hierarchical aggregation helpers and rolling computations
- Factory and runtime: instantiate and expose the tracker to API layers
- Types: define typed outputs for hierarchical metrics

```mermaid
graph TB
subgraph "Metrics Core"
RT["RequestTracker<br/>src/core/metrics/tracker/tracker.py"]
RM["RequestMetrics<br/>src/core/metrics/models/request.py"]
SM["SummaryMetrics<br/>src/core/metrics/models/summary.py"]
PT["ProviderModelMetrics<br/>src/core/metrics/models/provider.py"]
HT["Hierarchical Helpers<br/>src/core/metrics/calculations/hierarchical.py"]
TY["Types<br/>src/core/metrics/types.py"]
end
subgraph "Factory/Runtime"
FX["Factory<br/>src/core/metrics/tracker/factory.py"]
RTM["Runtime Helper<br/>src/core/metrics/runtime.py"]
end
subgraph "API Integration"
EP["Endpoints<br/>src/api/endpoints.py"]
ST["Streaming Services<br/>src/api/services/streaming.py"]
end
RT --> RM
RT --> SM
RT --> HT
RT --> TY
SM --> PT
FX --> RT
RTM --> RT
EP --> RTM
ST --> RTM
```

**Diagram sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L42-L84)
- [request.py](file://src/core/metrics/models/request.py#L9-L56)
- [summary.py](file://src/core/metrics/models/summary.py#L16-L119)
- [provider.py](file://src/core/metrics/models/provider.py#L11-L47)
- [hierarchical.py](file://src/core/metrics/calculations/hierarchical.py#L1-L125)
- [types.py](file://src/core/metrics/types.py#L14-L32)
- [factory.py](file://src/core/metrics/tracker/factory.py#L15-L30)
- [runtime.py](file://src/core/metrics/runtime.py#L20-L28)
- [endpoints.py](file://src/api/endpoints.py#L180-L244)
- [streaming.py](file://src/api/services/streaming.py#L196-L242)

**Section sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L1-L84)
- [factory.py](file://src/core/metrics/tracker/factory.py#L1-L31)
- [runtime.py](file://src/core/metrics/runtime.py#L1-L29)

## Core Components
The RequestTracker orchestrates request lifecycle events and maintains two complementary data stores:
- active_requests: dict[str, RequestMetrics] storing in-flight requests
- summary_metrics: SummaryMetrics aggregating completed requests

It uses asyncio.Lock for mutual exclusion and asyncio.Condition for reliable notification of active request changes. The tracker also maintains dashboard-facing buffers for recent traces and errors, along with last_accessed timestamps for provider/model attribution.

Key responsibilities:
- start_request(): registers new active requests and initializes metrics
- end_request(): finalizes active requests and aggregates into summary metrics
- get_running_totals_hierarchical(): computes hierarchical provider/model metrics with optional active request inclusion
- Synchronization: thread-safe operations with versioned notifications for concurrent listeners

**Section sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L42-L84)
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L85-L180)
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L315-L452)

## Architecture Overview
The RequestTracker integrates with API endpoints and streaming services to capture request lifecycle events. The factory creates trackers with configurable summary intervals, and the runtime helper provides access to the process-local instance.

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "API Endpoint"
participant Tracker as "RequestTracker"
participant Upstream as "Provider Client"
participant Stream as "Streaming Wrapper"
Client->>API : "POST /v1/chat/completions"
API->>Tracker : "start_request(request_id, model, is_streaming)"
Tracker-->>API : "RequestMetrics"
API->>Upstream : "Forward request"
Upstream-->>API : "Response or stream"
alt "Non-streaming"
API->>Tracker : "end_request(request_id)"
Tracker-->>API : "Aggregated metrics"
else "Streaming"
API->>Stream : "wrap with error handling + metrics finalizer"
Stream->>Upstream : "Stream chunks"
Stream->>Tracker : "end_request(request_id) in finally"
Tracker-->>Stream : "Aggregated metrics"
end
API-->>Client : "Response or SSE stream"
```

**Diagram sources**
- [endpoints.py](file://src/api/endpoints.py#L180-L244)
- [endpoints.py](file://src/api/endpoints.py#L326-L353)
- [streaming.py](file://src/api/services/streaming.py#L196-L242)
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L85-L180)

## Detailed Component Analysis

### RequestTracker Class
The RequestTracker class encapsulates the two-state metric management model with robust synchronization and hierarchical aggregation capabilities.

```mermaid
classDiagram
class RequestTracker {
-asyncio.Lock _lock
-asyncio.Condition _active_requests_changed
-int _active_requests_version
-dict~Task,int~ _active_requests_version_seen
-deque recent_errors
-deque recent_traces
-int _trace_seq
-int _error_seq
-dict last_accessed_timestamps
+dict active_requests
+SummaryMetrics summary_metrics
+int summary_interval
+int request_count
+int total_completed_requests
+start_request(request_id, claude_model, is_streaming, provider, resolved_model) RequestMetrics
+end_request(request_id, **kwargs) void
+get_request(request_id) RequestMetrics?
+get_active_requests_snapshot() list[dict]
+get_recent_errors(limit) list[dict]
+get_recent_traces(limit) list[dict]
+wait_for_active_requests_change(timeout) void
+update_last_accessed(provider, model, timestamp) void
+get_running_totals_hierarchical(provider_filter, model_filter, include_active) HierarchicalData
-_notify_active_requests_changed() void
-_emit_summary_locked() void
}
class RequestMetrics {
+string request_id
+float start_time
+float? end_time
+string? claude_model
+string? openai_model
+string? provider
+int input_tokens
+int output_tokens
+int cache_read_tokens
+int cache_creation_tokens
+int message_count
+int request_size
+int response_size
+bool is_streaming
+string? error
+string? error_type
+int tool_use_count
+int tool_result_count
+int tool_call_count
+duration_ms() float
+start_time_iso() string
}
class SummaryMetrics {
+int total_requests
+int total_errors
+int total_input_tokens
+int total_output_tokens
+int total_cache_read_tokens
+int total_cache_creation_tokens
+float total_duration_ms
+int total_tool_uses
+int total_tool_results
+int total_tool_calls
+dict model_counts
+dict error_counts
+dict provider_model_metrics
+add_request(RequestMetrics) void
+get_running_totals(provider_filter, model_filter) dict
}
class HierarchicalData {
+dict? last_accessed
+int total_requests
+int total_errors
+int total_input_tokens
+int total_output_tokens
+int total_cache_read_tokens
+int total_cache_creation_tokens
+int total_tool_uses
+int total_tool_results
+int total_tool_calls
+int active_requests
+float average_duration_ms
+int total_duration_ms
+dict providers
}
RequestTracker --> RequestMetrics : "manages"
RequestTracker --> SummaryMetrics : "aggregates"
RequestTracker --> HierarchicalData : "returns"
```

**Diagram sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L42-L84)
- [request.py](file://src/core/metrics/models/request.py#L9-L56)
- [summary.py](file://src/core/metrics/models/summary.py#L16-L119)
- [types.py](file://src/core/metrics/types.py#L14-L32)

#### Lifecycle Management
The request lifecycle is managed through coordinated operations:
- start_request(): Creates RequestMetrics with timestamps and model metadata, stores in active_requests, and notifies listeners
- end_request(): Finalizes metrics, aggregates into summary_metrics, records dashboard traces/errors, and resets state

```mermaid
flowchart TD
Start([Request Start]) --> CreateMetrics["Create RequestMetrics<br/>with timestamps"]
CreateMetrics --> StoreActive["Store in active_requests"]
StoreActive --> NotifyListeners["Notify active_requests_changed"]
NotifyListeners --> ProcessRequest["Process upstream request"]
ProcessRequest --> Success{"Success?"}
Success --> |Yes| Finalize["Call end_request(request_id)"]
Success --> |No| FinalizeError["Set error fields<br/>Call end_request(request_id)"]
Finalize --> Aggregate["Add to SummaryMetrics"]
FinalizeError --> Aggregate
Aggregate --> TraceLog["Record trace/error entries"]
TraceLog --> ResetCounter["Reset active_requests entry"]
ResetCounter --> EmitSummary{"Request count % summary_interval == 0?"}
EmitSummary --> |Yes| EmitLog["_emit_summary_locked()"]
EmitSummary --> |No| Done([Complete])
EmitLog --> Done
```

**Diagram sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L85-L180)
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L456-L490)

#### Hierarchical Aggregation Logic
The get_running_totals_hierarchical method builds provider->model hierarchies with streaming/non-streaming splits and optional active request inclusion.

```mermaid
flowchart TD
Entry([get_running_totals_hierarchical]) --> LockAcquire["Acquire asyncio.Lock"]
LockAcquire --> InitRT["Initialize RunningTotals<br/>with active_requests count"]
InitRT --> IterateCompleted["Iterate SummaryMetrics.provider_model_metrics"]
IterateCompleted --> FilterPM{"Apply provider/model filters"}
FilterPM --> |Skip| NextPM["Next PM entry"]
FilterPM --> |Include| AccumulatePM["Accumulate into provider/model splits"]
AccumulatePM --> NextPM
NextPM --> IncludeActive{"include_active?"}
IncludeActive --> |No| FinalizeRT["finalize_running_totals()"]
IncludeActive --> |Yes| IterateActive["Iterate active_requests"]
IterateActive --> FilterActive{"Apply provider/model filters"}
FilterActive --> |Skip| NextActive["Next active request"]
FilterActive --> |Include| AddActive["Add active metrics to splits"]
AddActive --> NextActive
NextActive --> FinalizeRT
FinalizeRT --> UnlockRelease["Release lock"]
UnlockRelease --> Return([Return HierarchicalData])
```

**Diagram sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L315-L452)
- [hierarchical.py](file://src/core/metrics/calculations/hierarchical.py#L85-L125)

**Section sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L42-L490)
- [request.py](file://src/core/metrics/models/request.py#L9-L56)
- [summary.py](file://src/core/metrics/models/summary.py#L16-L119)
- [hierarchical.py](file://src/core/metrics/calculations/hierarchical.py#L1-L125)
- [types.py](file://src/core/metrics/types.py#L14-L32)

### Data Models and Aggregation
The data models define the structures used throughout the tracking pipeline:

- RequestMetrics: per-request attributes including timestamps, token counts, streaming flags, error information, and tool usage metrics
- SummaryMetrics: accumulated totals across completed requests with provider/model granularity and streaming/non-streaming splits
- ProviderModelMetrics: granular metrics for specific provider/model combinations
- RunningTotals: hierarchical aggregation container for API responses

```mermaid
erDiagram
REQUESTMETRICS {
string request_id PK
float start_time
float end_time
string claude_model
string openai_model
string provider
int input_tokens
int output_tokens
int cache_read_tokens
int cache_creation_tokens
int message_count
int request_size
int response_size
bool is_streaming
string error
string error_type
int tool_use_count
int tool_result_count
int tool_call_count
}
PROVIDERMODEL {
int total_requests
int total_errors
int total_input_tokens
int total_output_tokens
int total_cache_read_tokens
int total_cache_creation_tokens
float total_duration_ms
int total_tool_uses
int total_tool_results
int total_tool_calls
int streaming_requests
int streaming_errors
int streaming_input_tokens
int streaming_output_tokens
int streaming_cache_read_tokens
int streaming_cache_creation_tokens
float streaming_duration_ms
int streaming_tool_uses
int streaming_tool_results
int streaming_tool_calls
int non_streaming_requests
int non_streaming_errors
int non_streaming_input_tokens
int non_streaming_output_tokens
int non_streaming_cache_read_tokens
int non_streaming_cache_creation_tokens
float non_streaming_duration_ms
int non_streaming_tool_uses
int non_streaming_tool_results
int non_streaming_tool_calls
}
SUMMARY {
int total_requests
int total_errors
int total_input_tokens
int total_output_tokens
int total_cache_read_tokens
int total_cache_creation_tokens
float total_duration_ms
int total_tool_uses
int total_tool_results
int total_tool_calls
dict model_counts
dict error_counts
dict provider_model_metrics
}
REQUESTMETRICS ||--|| PROVIDERMODEL : "aggregated into"
SUMMARY ||--|| PROVIDERMODEL : "contains"
```

**Diagram sources**
- [request.py](file://src/core/metrics/models/request.py#L9-L56)
- [provider.py](file://src/core/metrics/models/provider.py#L11-L47)
- [summary.py](file://src/core/metrics/models/summary.py#L16-L119)

**Section sources**
- [request.py](file://src/core/metrics/models/request.py#L9-L56)
- [provider.py](file://src/core/metrics/models/provider.py#L11-L47)
- [summary.py](file://src/core/metrics/models/summary.py#L16-L119)

### Integration Points
The RequestTracker integrates with API endpoints and streaming services:

- API endpoints: start_request() at request initiation, end_request() on completion or error
- Streaming services: wrap streams with error handling and metrics finalization to ensure end_request() is always called
- Runtime helper: provides access to the process-local RequestTracker instance

```mermaid
sequenceDiagram
participant Endpoint as "API Endpoint"
participant Tracker as "RequestTracker"
participant Streaming as "Streaming Wrapper"
participant Upstream as "Provider Client"
Endpoint->>Tracker : "start_request()"
Endpoint->>Upstream : "forward request"
alt "streaming"
Endpoint->>Streaming : "wrap with error handling"
Streaming->>Upstream : "stream chunks"
Streaming->>Tracker : "end_request() in finally"
else "non-streaming"
Upstream-->>Endpoint : "response"
Endpoint->>Tracker : "end_request()"
end
```

**Diagram sources**
- [endpoints.py](file://src/api/endpoints.py#L180-L244)
- [endpoints.py](file://src/api/endpoints.py#L326-L353)
- [streaming.py](file://src/api/services/streaming.py#L196-L242)
- [runtime.py](file://src/core/metrics/runtime.py#L20-L28)

**Section sources**
- [endpoints.py](file://src/api/endpoints.py#L180-L244)
- [endpoints.py](file://src/api/endpoints.py#L326-L353)
- [streaming.py](file://src/api/services/streaming.py#L196-L242)
- [runtime.py](file://src/core/metrics/runtime.py#L20-L28)

## Dependency Analysis
The RequestTracker depends on several supporting modules for data modeling, calculation, and type safety.

```mermaid
graph TB
RT["RequestTracker"]
RM["RequestMetrics"]
SM["SummaryMetrics"]
PM["ProviderModelMetrics"]
HT["Hierarchical Helpers"]
TY["Types"]
FX["Factory"]
RTM["Runtime Helper"]
RT --> RM
RT --> SM
RT --> HT
RT --> TY
SM --> PM
FX --> RT
RTM --> RT
```

**Diagram sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L29-L39)
- [factory.py](file://src/core/metrics/tracker/factory.py#L15-L30)
- [runtime.py](file://src/core/metrics/runtime.py#L20-L28)
- [types.py](file://src/core/metrics/types.py#L14-L32)

**Section sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L29-L39)
- [factory.py](file://src/core/metrics/tracker/factory.py#L15-L30)
- [runtime.py](file://src/core/metrics/runtime.py#L20-L28)
- [types.py](file://src/core/metrics/types.py#L14-L32)

## Performance Considerations
The RequestTracker is designed for high-throughput request processing with careful attention to synchronization overhead and memory usage:

- Lock contention: All public methods acquire asyncio.Lock for exclusive access to internal state. While this ensures thread safety, it can become a bottleneck under extreme concurrency. Consider batching operations or reducing lock scope where possible.
- Memory usage: active_requests grows with concurrent in-flight requests. The dictionary stores RequestMetrics objects with integer and float counters, plus string fields for identifiers. Monitor active_requests size in production to prevent memory pressure.
- Summary interval: The summary_interval parameter controls how frequently completed request summaries are logged and reset. Larger intervals reduce logging overhead but increase memory retention of completed metrics.
- Deque buffers: recent_errors and recent_traces use deques with fixed maximum lengths to cap memory usage for dashboard telemetry.
- Hierarchical computation: get_running_totals_hierarchical iterates over completed metrics and optionally active requests. Filtering reduces computational cost but still scales with the number of tracked items.

Race condition prevention:
- Versioned notifications: The tracker uses asyncio.Condition with a monotonic version counter to reliably notify multiple concurrent listeners without missing updates. Each task tracks the last seen version to avoid missed changes.
- Atomic operations: Critical sections protect state transitions (start/end) and ensure that active_requests and summary_metrics remain consistent across concurrent access.

**Section sources**
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L46-L84)
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L249-L291)
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L456-L490)

## Troubleshooting Guide
Common issues and their resolutions:

- Missing RequestTracker instance: Ensure the tracker is created during application startup and attached to app.state. Access via get_request_tracker() will raise errors if not configured.
- Inconsistent model attribution: Verify that resolved_model is set before end_request() to avoid alias tokens in active request displays.
- Streaming finalization failures: Confirm that with_streaming_error_handling wraps all streaming generators to guarantee end_request() execution in finally blocks.
- Excessive lock contention: Monitor active_requests size and adjust summary_interval. Consider reducing concurrent request volume or optimizing downstream provider latency.
- Dashboard data gaps: Check versioned notification logic if SSE clients miss updates; the tracker uses version counters to prevent missed notifications.

**Section sources**
- [runtime.py](file://src/core/metrics/runtime.py#L20-L28)
- [streaming.py](file://src/api/services/streaming.py#L196-L242)
- [tracker.py](file://src/core/metrics/tracker/tracker.py#L256-L291)

## Conclusion
The RequestTracker provides a robust, thread-safe mechanism for managing request metrics within a single process. Its two-state model separates active and completed metrics, while hierarchical aggregation enables flexible provider/model filtering. The use of asyncio primitives ensures safe concurrent access, and the summary_interval-based reset mechanism balances observability with resource usage. Proper integration with API endpoints and streaming services guarantees comprehensive coverage of request lifecycle events, enabling accurate monitoring and diagnostics.