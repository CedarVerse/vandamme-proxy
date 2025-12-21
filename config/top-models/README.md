# Top Models rankings (manual)

This folder contains a **human-maintained** ranked list of the best models for *programming* tasks.

OpenRouter’s public API (`/api/v1/models`) provides the **full catalog** of models, but does **not** provide the “Rankings → Categories → Programming” ordering in a stable machine-readable way.

So we keep the ordering here (as TOML), and Vandamme Proxy enriches that ordering using OpenRouter’s catalog (name, context, pricing, capabilities) via the proxy’s existing `/v1/models` endpoint.

## Files

- `programming.toml` — the ordered programming ranking.

## How it works

1. Vandamme reads `programming.toml` and extracts the ordered list of model IDs.
2. It calls the proxy’s own catalog endpoint:

   - `/v1/models?provider=openrouter&format=openai`
   - (and when `refresh=true` is requested on `/top-models`, it forces a refresh of `/v1/models` too)

3. It matches the TOML IDs against the catalog and emits `/top-models` in the **same order**.

If an ID in TOML is missing from the OpenRouter catalog response, it will be skipped (and logged).

## Editing the ranking

Open `programming.toml` and update the `[[models]]` list in the exact order you want.

Guidelines:
- Use OpenRouter model IDs of the form `provider/model` (example: `x-ai/grok-code-fast-1`).
- Keep the list ordered (rank #1 first).
- Prefer stable IDs (avoid temporary preview suffixes unless intentionally chosen).

## TOML schema

Only `[[models]].id` is required.

```toml
version = 1
category = "programming"
source = "https://openrouter.ai/rankings#categories"
last_verified = "YYYY-MM-DD"

[[models]]
id = "x-ai/grok-code-fast-1"
# note = "Optional note"
```
