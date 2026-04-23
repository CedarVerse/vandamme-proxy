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
        """Resolve model name to (provider, actual_model).

        The resolution pipeline runs these phases in order (first match wins):

        1. Profile prefix: "profile:model" -> detect profile, strip prefix
        2. Default profile: bare name + VDM_DEFAULT_TARGET is a profile -> set profile
        3. Profile aliases: exact-match (case-insensitive) in profile.aliases
        4. Literal bypass: "!model" -> skip substring matching
        5. AliasManager: substring match, chained resolution, ranked by priority
        6. Provider prefix: "provider:model" or default target fallback
        7. Return (provider_name, actual_model_name)

        See docs/model-resolution.md for the full guide with examples.

        Returns:
            Tuple[str, str]: (provider_name, actual_model_name)

        Note:
            If you add or remove a phase, update docs/model-resolution.md.
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

        # If no explicit profile prefix was found and the default target is a profile,
        # set the profile variable so the existing profile alias check handles it.
        if profile is None and ":" not in model and not model.startswith("!"):
            default_profile_name = self.provider_manager.default_profile
            if default_profile_name:
                _pm = self.provider_manager.profile_manager
                if _pm:
                    # get_profile may return None if profile was removed after select()
                    profile = _pm.get_profile(default_profile_name)
                    if profile:
                        logger.debug(
                            f"Using default profile '{default_profile_name}' "
                            f"for bare model resolution"
                        )

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
                    default_target = self.provider_manager.default_target
                    resolved_model = (
                        self.alias_manager.resolve_alias(model, provider=default_target) or model
                    )
                else:
                    resolved_model = self.alias_manager.resolve_alias(model) or model
            else:
                logger.debug(
                    f"Alias manager available with {self.alias_manager.get_alias_count()} aliases"
                )

                # Check if model already has provider prefix
                if ":" not in model:
                    # No provider prefix - resolve using default target only
                    default_target = self.provider_manager.default_target
                    logger.debug(f"Resolving alias '{model}' with target scope '{default_target}'")
                    alias_target = self.alias_manager.resolve_alias(model, provider=default_target)
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
            via = "profile alias" if profile else "alias"
            logger.debug(
                f"[ModelManager] Resolved: '{model}' -> "
                f"'{provider_name}:{actual_model}' (via {via})"
            )
        else:
            logger.debug(
                f"Model resolution complete: '{model}' -> "
                f"'{provider_name}:{actual_model}' (no alias)"
            )

        return provider_name, actual_model
