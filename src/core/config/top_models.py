"""Top models feature configuration module.

This module handles top models feature settings including:
- Source configuration (manual_rankings or openrouter)
- Rankings file path
- Timeout settings
- Model exclusion list

Now uses schema-based loading for automatic type coercion and validation.
"""

from dataclasses import dataclass

from src.core.config.schema import ConfigSchema
from src.core.config.validation import load_env_var


@dataclass(frozen=True)
class TopModelsConfig:
    """Configuration for top models feature.

    Attributes:
        source: Source for top models ("manual_rankings" or "openrouter")
        rankings_file: Path to TOML file with manual rankings
        timeout_seconds: Timeout in seconds for fetching from remote source
        exclude: Tuple of model IDs to exclude from recommendations
    """

    source: str
    rankings_file: str
    timeout_seconds: float
    exclude: tuple[str, ...]


class TopModelsSettings:
    """Manages top models configuration from environment variables.

    This class uses the schema-based loading approach which provides:
    - Automatic type coercion (str -> float/tuple)
    - Validation with clear error messages
    - Single source of truth for default values
    - Tuple parsing from comma-separated strings
    """

    @staticmethod
    def load() -> TopModelsConfig:
        """Load top models configuration using schema-based validation.

        Returns:
            TopModelsConfig with values from environment or defaults

        Raises:
            ConfigError: If any environment variable fails validation
        """
        # Parse exclude string to tuple - the schema returns a string
        exclude_str = load_env_var(ConfigSchema.TOP_MODELS_EXCLUDE)
        exclude = tuple(s.strip() for s in exclude_str.split(",") if s.strip())

        return TopModelsConfig(
            source=load_env_var(ConfigSchema.TOP_MODELS_SOURCE),
            rankings_file=load_env_var(ConfigSchema.TOP_MODELS_RANKINGS_FILE) or "",
            timeout_seconds=load_env_var(ConfigSchema.TOP_MODELS_TIMEOUT_SECONDS),
            exclude=exclude,
        )
