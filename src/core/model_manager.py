"""Model name resolution with alias support and provider parsing.

This module provides the ModelManager class which resolves model names
through aliases and determines the appropriate provider for each request.

The ModelManager implements the ModelResolver protocol for clean
dependency inversion, eliminating circular imports.
"""

import logging
from typing import TYPE_CHECKING

from src.core.protocols import ConfigProvider, ModelResolver

if TYPE_CHECKING:
    from src.core.alias_manager import AliasManager
    from src.core.profile_config import ProfileConfig

logger = logging.getLogger(__name__)


class ModelManager(ModelResolver):
    """Manages model name resolution with alias support and provider parsing.

    This class implements the ModelResolver protocol, providing clean
    dependency inversion. It uses the ConfigProvider protocol for
    configuration access instead of depending on the concrete Config class.

    The ModelManager orchestrates:
    1. Provider prefix parsing (e.g., "openai:gpt-4" -> ("openai", "gpt-4"))
    2. Alias resolution through AliasManager
    3. Default provider fallback

    Attributes:
        config: Configuration implementing ConfigProvider protocol
        provider_manager: Provider manager instance from dependencies
        alias_manager: Alias manager instance from dependencies
    """

    def __init__(self, config: ConfigProvider) -> None:
        """Initialize ModelManager with configuration.

        Args:
            config: Configuration object implementing ConfigProvider protocol.
                   This allows dependency injection and cleaner separation of concerns.
        """
        self.config = config
        # Access managers through config (which delegates to dependencies module)
        self.provider_manager = config.provider_manager  # type: ignore[attr-defined]
        self.alias_manager: AliasManager | None = getattr(config, "alias_manager", None)  # type: ignore[attr-defined]

    def resolve_model(self, model: str) -> tuple[str, str]:
        """Resolve model name to (provider, actual_model)

        Resolution process:
        1. Check for profile prefix (profiles take precedence over providers)
        2. If profile prefix, use profile's aliases for resolution
        3. Otherwise, use existing alias resolution logic
        4. Parse provider prefix from resolved value
        5. Return provider and actual model name

        Returns:
            Tuple[str, str]: (provider_name, actual_model_name)
        """
        logger.debug(f"Starting model resolution for: '{model}'")

        # NEW: Check for profile prefix FIRST (before provider)
        profile: ProfileConfig | None = None
        if ":" in model:
            potential_profile, model_part = model.split(":", 1)
            profile_manager = getattr(self.provider_manager, "profile_manager", None)
            if profile_manager and profile_manager.is_profile(potential_profile):
                profile = profile_manager.get_profile(potential_profile)
                logger.debug(f"Using profile '{profile.name}' for model resolution")
                # Continue with model_part for alias resolution
                model = model_part

        # Apply alias resolution if available
        resolved_model = model

        # NEW: Check profile aliases first if a profile is active
        if profile and model.lower() in profile.aliases:
            resolved_model = profile.aliases[model.lower()]
            logger.debug(f"[ModelManager] Profile alias resolved: '{model}' -> '{resolved_model}'")
        elif self.alias_manager and self.alias_manager.has_aliases():
            # Literal model names (prefixed with '!') must bypass alias matching.
            # Still allow AliasManager to normalize into provider:model form when needed.
            if model.startswith("!"):
                if ":" not in model:
                    default_provider = self.provider_manager.default_provider
                    resolved_model = (
                        self.alias_manager.resolve_alias(model, provider=default_provider) or model
                    )
                else:
                    resolved_model = self.alias_manager.resolve_alias(model) or model
            else:
                logger.debug(
                    f"Alias manager available with {self.alias_manager.get_alias_count()} aliases"
                )

                # Check if model already has provider prefix
                if ":" not in model:
                    # No provider prefix - resolve using default provider only
                    default_provider = self.provider_manager.default_provider
                    logger.debug(
                        f"Resolving alias '{model}' with provider scope '{default_provider}'"
                    )
                    alias_target = self.alias_manager.resolve_alias(
                        model, provider=default_provider
                    )
                else:
                    # Has provider prefix - allow cross-provider resolution
                    logger.debug(f"Resolving alias '{model}' across all providers")
                    alias_target = self.alias_manager.resolve_alias(model)

                if alias_target:
                    logger.debug(f"[ModelManager] Alias resolved: '{model}' -> '{alias_target}'")
                    resolved_model = alias_target
                else:
                    logger.debug(f"No alias match found for '{model}', using original model name")
        else:
            logger.debug("No aliases configured or alias manager unavailable")

        # Parse provider prefix
        logger.debug(f"Parsing provider prefix from resolved model: '{resolved_model}'")
        provider_name, actual_model = self.provider_manager.parse_model_name(resolved_model)
        logger.debug(f"Parsed provider: '{provider_name}', actual model: '{actual_model}'")

        # Log the final resolution result
        if resolved_model != model:
            logger.debug(
                f"[ModelManager] Resolved: '{model}' -> "
                f"'{provider_name}:{actual_model}' (via alias)"
            )
        else:
            logger.debug(
                f"Model resolution complete: '{model}' -> "
                f"'{provider_name}:{actual_model}' (no alias)"
            )

        return provider_name, actual_model
