# Top Models: Curated Recommendations

Vandamme Proxy provides a **proxy-metadata** feature that fetches curated model recommendations from remote sources (currently OpenRouter) and makes them available via both API and CLI. This helps operators and developers answer the practical question: *“which models should I use right now?”*

The recommendations are cached on disk, can be filtered by policy, and are surfaced as a **non-mutating alias overlay** so you can discover them without modifying your configuration.

---

## TL;DR Quick Start

```bash
# 1) View current top models (API)
curl "http://localhost:8082/top-models?limit=5"

# 2) View with your CLI (Rich table + suggested aliases)
vdm models top

# 3) See suggested aliases alongside your configured ones
curl http://localhost:8082/v1/aliases | jq '.suggested'

# 4) Force refresh bypassing cache
vdm models top --refresh
curl "http://localhost:8082/top-models?refresh=true"
```

---

## Concepts

### Proxy Metadata vs. /v1 API

- **`/top-models`**: Proxy metadata. This is not part of the `/v1/*` Anthropic-compatible surface; it’s an operational endpoint for discovering models.
- **`/v1/aliases`**: This endpoint now includes a `suggested` overlay field derived from `/top-models` **without** mutating your configured aliases.

### Suggested Aliases (non-mutating overlay)

The feature generates a minimal, deterministic set of suggested aliases:
- `top`: the #1 model in the list
- `top-cheap`: cheapest average price per million tokens
- `top-longctx`: longest context window

These are **only for discovery**. They appear in the `suggested` field of `/v1/aliases`:

```json
{
  "aliases": { /* your configured aliases */ },
  "suggested": {
    "default": {
      "top": "openai/gpt-4o",
      "top-cheap": "google/gemini-2.0-flash",
      "top-longctx": "openai/gpt-4o"
    }
  }
}
```

---

## API Endpoints

### `/top-models`

**GET /top-models**

Returns cached or live curated model list from a remote source (currently OpenRouter).

Query parameters:
- `limit` (int, 1–50, default 10): how many models to return
- `refresh` (bool, default false): bypass cache and fetch live
- `provider` (string, optional): filter results by provider prefix

**Response format**:
```json
{
  "object": "list",
  "source": "openrouter",
  "cached": true,
  "last_updated": "2025-12-20T13:45:00Z",
  "data": [
    {
      "id": "openai/gpt-4o",
      "name": "GPT-4o",
      "provider": "openai",
      "context_window": 128000,
      "capabilities": ["tools", "vision"],
      "pricing": {
        "input_per_million": 2.50,
        "output_per_million": 10.0,
        "average_per_million": 6.25
      }
    }
  ],
  "aliases": {
    "top": "openai/gpt-4o",
    "top-cheap": "google/gemini-2.0-flash",
    "top-longctx": "openai/gpt-4o"
  }
}
```

### `/v1/aliases` (with overlay)

The existing `/v1/aliases` endpoint now includes `suggested`:

```json
{
  "object": "list",
  "aliases": { /* configured aliases */ },
  "suggested": { "default": { "top": "...", ... } },
  "total": 42
}
```

- Errors in suggestion calculation never break `/v1/aliases`; they result in an empty `suggested` object and are logged at DEBUG level.

---

## CLI: `vdm models top`

```bash
vdm models top [OPTIONS]
```

- `--limit N` (default 10): max models to show
- `--provider X`: filter by provider prefix
- `--refresh`: bypass cache
- `--json`: print raw JSON response
- `--base-url URL`: Vandamme proxy base URL (default http://localhost:8082)

Examples:
```bash
# Human-friendly table with defaults
vdm models top

# JSON for scripts
vdm models top --json | jq '.data[0].id'

# Refresh and limit
vdm models top --refresh --limit 3

# Provider-filtered
vdm models top --provider openai
```

---

## Configuration

### Environment Variables

- `TOP_MODELS_CACHE_DIR` (default `~/.cache/vandamme-proxy`): where disk cache is stored
- `TOP_MODELS_CACHE_TTL_DAYS` (default `2`): how long cached results stay fresh
- `TOP_MODELS_TIMEOUT_SECONDS` (default `30`): HTTP timeout when fetching recommendations
- `TOP_MODELS_EXCLUDE` (CSV): models to exclude (substring match on `model.id`)

### Exclusions

Use `TOP_MODELS_EXCLUDE` to hide models you don’t want recommended:

```bash
# Exclude all OpenAI models
export TOP_MODELS_EXCLUDE="openai/"

# Exclude multiple providers/prefixes
export TOP_MODELS_EXCLUDE="openai/,anthropic/,custom-provider/beta"

# Exclude specific model names
export TOP_MODELS_EXCLUDE="gpt-4o,claude-3-opus-20240229"
```

The exclusion is a **substring match** against the full model identifier (e.g., `openai/gpt-4o`).

### Cache Path and TTL

- Default cache file: `~/.cache/vandamme-proxy/top-models.json`
- Cache includes versioned schema for future compatibility
- Requests are served from cache while within TTL; set `refresh=true` to bypass

---

## Internals (for advanced users)

### Data Flow

1. **Fetch**:
   - By default: reads from disk cache
   - If `refresh=true` or cache miss/invalid: calls `OpenRouterTopModelsSource`

2. **Filter**:
   - Applies global exclusions (`TOP_MODELS_EXCLUDE`)
   - Applies `provider` filter if requested

3. **Slice**:
   - Applies `limit` after filtering

4. **Suggest aliases**:
   - Derives deterministic aliases (`top`, `top-cheap`, `top-longctx`)

### Error Resilience

- `/v1/aliases` never fails due to suggestion errors
- `/top-models` returns 200 with `cached=true` if live fetch fails but cache is usable
- Upstream network failures return 502 with clear error messages

### Extensibility

- Source abstraction (`TopModelsSource`) makes adding new aggregators (other than OpenRouter) straightforward without changing API/CLI.
- Cache schema is versioned for safe migrations.

---

## Use Cases

### Operators: “What should our default model be?”

```bash
vdm models top --limit 1
```

Take the first `id` as your `VDM_DEFAULT_PROVIDER` or document it as the team default.

### Operators: “Excluding expensive/providers we don’t trust”

Set `TOP_MODELS_EXCLUDE` in your service configuration; the system instantly stops recommending those models without a restart.

### Developers: “I want a cheap but capable model”

```bash
# Discover current cheapest model
curl "http://localhost:8082/top-models?limit=100" | jq '.aliases.top_cheap'
```

Then use that model ID in your request.

### CI/CD: “Pick a model that exists now”

Use `/top-models?refresh=true` to get the latest recommendations and choose the first one that matches your criteria (e.g., cheapest, longest context).

---

## Monitoring

### Cache Hits/Misses

Enable DEBUG logging to see cache behavior:

```bash
LOG_LEVEL=DEBUG vdm models top --refresh
# You’ll see logs like:
# DEBUG - TopModelsCache - cache miss; fetching from source
# DEBUG - TopModelsCache - cache hit; serving fresh
```

### Health

Standard `/health` indicates whether the top-models source is reachable when there is no valid cache.

---

## Tips and Gotchas

- **Suggestions are not aliases**: you cannot use `top` directly in API requests unless you implement your own resolution layer. They are purely informative.
- **Cache TTL**: if you’re setting up a fleet, ensure all servers’ clocks are reasonably in sync so cache TTL is coherent.
- **Network Access**: the server making `/top-models` requests must reach `https://openrouter.ai/api/v1/models`. If your deployment has network restrictions, you may need to allowlist this.
- **Rate Limits**: OpenRouter’s public model list is small and generally not rate-limited, but don’t set TTL to seconds for frequent `refresh=true` in production.

---

## Troubleshooting

### No models returned

- Check `TOP_MODELS_EXCLUDE` isn’t accidentally matching everything.
- Verify `LOG_LEVEL=DEBUG` to see fetch vs. cache path and any parse errors.
- Ensure outbound connectivity to `https://openrouter.ai/api/v1/models`.

### Stale suggestions despite `refresh=true`

- Verify the server you’re querying is the one serving the request (multi-node deployments).

### Suggested aliases disappear

- `/v1/aliases` will omit `suggested` if the underlying `/top-models` fails entirely; check `/top-models` directly to debug.

---

## Related Documentation

- [Model Aliases](model-aliases.md) – for configuring your own aliases
- [Provider Routing Guide](provider-routing-guide.md) – for per-provider configuration
- [Multi-API Keys](multi-api-keys.md) – for high availability across providers