"""Metrics and monitoring configuration module.

This module handles metrics-related settings including:
- Request metrics logging flag
- Token limits (min/max)
- Active requests SSE configuration

Now uses schema-based loading for automatic type coercion and validation.
"""

from dataclasses import dataclass

from src.core.config.schema import ConfigSchema
from src.core.config.validation import load_env_var


@dataclass(frozen=True)
class MetricsConfig:
    """Configuration for metrics and monitoring settings.

    Attributes:
        log_request_metrics: Whether to log request metrics
        max_tokens_limit: Maximum token limit for requests
        min_tokens_limit: Minimum token limit for requests
        active_requests_sse_enabled: Whether active requests SSE is enabled
        active_requests_sse_interval: Interval in seconds for SSE updates
        active_requests_sse_heartbeat: Heartbeat interval in seconds for SSE
    """

    log_request_metrics: bool
    max_tokens_limit: int
    min_tokens_limit: int
    active_requests_sse_enabled: bool
    active_requests_sse_interval: float
    active_requests_sse_heartbeat: float


class MetricsSettings:
    """Manages metrics configuration from environment variables.

    This class uses the schema-based loading approach which provides:
    - Automatic type coercion (str -> int/float/bool)
    - Validation with clear error messages
    - Single source of truth for default values
    - Sophisticated boolean parsing (accepts "true", "1", "yes", "on")
    """

    @staticmethod
    def load() -> MetricsConfig:
        """Load metrics configuration using schema-based validation.

        Returns:
            MetricsConfig with values from environment or defaults

        Raises:
            ConfigError: If any environment variable fails validation
        """
        return MetricsConfig(
            log_request_metrics=load_env_var(ConfigSchema.LOG_REQUEST_METRICS),
            max_tokens_limit=load_env_var(ConfigSchema.MAX_TOKENS_LIMIT),
            min_tokens_limit=load_env_var(ConfigSchema.MIN_TOKENS_LIMIT),
            active_requests_sse_enabled=load_env_var(ConfigSchema.VDM_ACTIVE_REQUESTS_SSE_ENABLED),
            active_requests_sse_interval=load_env_var(
                ConfigSchema.VDM_ACTIVE_REQUESTS_SSE_INTERVAL
            ),
            active_requests_sse_heartbeat=load_env_var(
                ConfigSchema.VDM_ACTIVE_REQUESTS_SSE_HEARTBEAT
            ),
        )
