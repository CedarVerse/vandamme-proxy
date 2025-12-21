"""Cache for /v1/models endpoint responses.

Caches provider-specific model lists to avoid repeated API calls.
"""

# type: ignore

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from src.core.cache.disk import DiskJsonCache, make_cache_key


class ModelsDiskCache(DiskJsonCache):
    """Cache for provider model lists from upstream `/models`.

    Notes:
    - The cache stores the *raw upstream JSON response* (no transformations).
    - Transformations (Anthropic/OpenAI response shapes) happen at the API layer.
    """

    def __init__(self, cache_dir: Path, ttl_hours: int) -> None:
        super().__init__(
            cache_dir=cache_dir,
            ttl=timedelta(hours=ttl_hours),
            schema_version=1,
            namespace="models",
        )

    def make_file_path(self, provider: str, base_url: str, custom_headers: dict[str, str]) -> Path:
        """Generate cache file path for specific provider configuration."""
        # Create deterministic cache key from provider config
        headers_str = ",".join(f"{k}:{v}" for k, v in sorted(custom_headers.items()))
        cache_key = make_cache_key(provider, base_url, headers_str)
        return self.cache_dir / self.namespace / provider / f"models-{cache_key}.json"

    def _file_path(self) -> Path:
        """This is overridden by make_file_path - should not be called directly."""
        raise NotImplementedError("Use make_file_path(provider, base_url, headers) instead")

    def read_response_if_fresh(
        self,
        provider: str,
        base_url: str,
        custom_headers: dict[str, str],
    ) -> dict[str, Any] | None:
        """Read raw upstream `/models` response from cache if fresh."""
        if self._should_skip_cache():
            return None

        path = self.make_file_path(provider, base_url, custom_headers)
        cache_data = self._read_cache_file(path)
        if not cache_data:
            return None

        if not self._is_cache_fresh(cache_data):
            return None

        response = cache_data.get("response")
        if not isinstance(response, dict):
            return None

        return response

    def read_response_if_any(
        self,
        provider: str,
        base_url: str,
        custom_headers: dict[str, str],
    ) -> dict[str, Any] | None:
        """Read raw upstream `/models` response from cache (ignores TTL)."""
        if self._should_skip_cache():
            return None

        path = self.make_file_path(provider, base_url, custom_headers)
        cache_data = self._read_cache_file(path)
        if not cache_data:
            return None

        response = cache_data.get("response")
        if not isinstance(response, dict):
            return None

        return response

    def read_models_if_fresh(
        self,
        provider: str,
        base_url: str,
        custom_headers: dict[str, str],
    ) -> list[dict[str, Any]] | None:
        """Backward-compatible API: read OpenAI-style `data` list if cache is fresh."""
        response = self.read_response_if_fresh(provider, base_url, custom_headers)
        if response is None:
            return None

        models = response.get("data")
        if not isinstance(models, list):
            return None

        return models

    def write_response(
        self,
        provider: str,
        base_url: str,
        custom_headers: dict[str, str],
        response: dict[str, Any],
    ) -> None:
        """Write raw upstream `/models` response to cache."""
        if self._should_skip_cache():
            return

        path = self.make_file_path(provider, base_url, custom_headers)
        full_data = {
            "schema_version": self.schema_version,
            "last_updated": self._get_timestamp(),
            "provider": provider,
            "base_url": base_url,
            "response": response,
        }
        self._atomic_write(path, full_data)

    def write_models(
        self,
        provider: str,
        base_url: str,
        custom_headers: dict[str, str],
        models: list[dict[str, Any]],
    ) -> None:
        """Backward-compatible API: write OpenAI-style `data` list to cache."""
        self.write_response(
            provider=provider,
            base_url=base_url,
            custom_headers=custom_headers,
            response={"object": "list", "data": models},
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _serialize(self, payload: Any) -> dict[str, Any]:  # noqa: ANN401
        """Not used - we implement custom read/write methods."""
        return payload  # pragma: no cover

    def _deserialize(self, cache_data: dict[str, Any]) -> Any:  # noqa: ANN401
        """Not used - we implement custom read/write methods."""
        return cache_data  # pragma: no cover

    def _read_cache_file(self, path: Path) -> dict[str, Any] | None:
        """Read a cache file, upgrading legacy schema when needed.

        Legacy schema (v1) stored a list under `models`.
        Current schema stores the exact upstream JSON under `response`.
        """
        cache_data = super()._read_cache_file(path)
        if not cache_data:
            return cache_data

        if "response" not in cache_data and isinstance(cache_data.get("models"), list):
            cache_data = {
                **cache_data,
                "response": {"object": "list", "data": cache_data.get("models")},
            }

        return cache_data

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _serialize(self, payload: Any) -> dict[str, Any]:  # noqa: ANN401
        """Not used - we implement custom read/write methods."""
        return payload  # pragma: no cover

    def _deserialize(self, cache_data: dict[str, Any]) -> Any:  # noqa: ANN401
        """Not used - we implement custom read/write methods."""
        return cache_data  # pragma: no cover
