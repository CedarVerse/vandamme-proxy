"""Model name resolution with alias support and provider parsing.

This module provides the ModelManager class which resolves model names
through aliases and determines the appropriate provider for each request.

The ModelManager implements the ModelResolver protocol for clean
dependency inversion, eliminating circular imports.
"""

import logging
from typing import TYPE_CHECKING

from src.core.model_resolution_trace import ResolutionPhase, ResolutionTrace
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

    @staticmethod
    def _record_phase(
        trace: ResolutionTrace | None,
        name: str,
        input_model: str,
        result: str,
        output: str,
        **details: object,
    ) -> None:
        """Append a resolution phase to the trace, if tracing is active.

        This is a static method (no ``self`` dependency) so it can be called
        from anywhere in the resolution pipeline without coupling to instance state.

        Args:
            trace: The ResolutionTrace accumulator, or None to silently skip.
            name: Human-readable phase name (e.g., "Profile prefix detection").
            input_model: Model name entering this phase.
            result: "matched", "skipped", "parsed", or a descriptive label.
            output: Model name leaving this phase.
            **details: Phase-specific context for diagnostics (e.g., reason, profile_name).
        """
        if trace is not None:
            trace.phases.append(
                ResolutionPhase(
                    name=name,
                    input=input_model,
                    result=result,
                    output=output,
                    details=details,
                )
            )

    def resolve_model(self, model: str, *, trace: ResolutionTrace | None = None) -> tuple[str, str]:
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

        # Save the original model name for trace recording (it may be mutated below).
        original_model = model

        # ---- Phase 1: Profile prefix detection ----
        # Check for profile prefix FIRST (before provider).
        # "top:haiku" -> if "top" is a profile, strip it and continue with "haiku".
        profile: ProfileConfig | None = None
        if ":" in model:
            potential_profile, model_part = model.split(":", 1)
            profile_manager = getattr(self.provider_manager, "profile_manager", None)
            if profile_manager and profile_manager.is_profile(potential_profile):
                profile = profile_manager.get_profile(potential_profile)
                logger.debug(f"Using profile '{profile.name}' for model resolution")
                self._record_phase(
                    trace,
                    "Profile prefix detection",
                    model,
                    "matched",
                    model_part,
                    potential_profile=potential_profile,
                    profile_name=profile.name if profile else None,
                )
                # Continue with model_part for alias resolution
                model = model_part
            else:
                # Has colon but prefix is not a profile (e.g., "openai:gpt-5.1")
                reason = (
                    f"'{potential_profile}' is not a profile"
                    if profile_manager
                    else "no profile_manager"
                )
                self._record_phase(
                    trace,
                    "Profile prefix detection",
                    model,
                    "skipped",
                    model,
                    reason=reason,
                )
        else:
            self._record_phase(
                trace,
                "Profile prefix detection",
                model,
                "skipped",
                model,
                reason="no colon in model",
            )

        # ---- Phase 2: Default profile resolution ----
        # If no explicit profile prefix was found and a default profile is configured,
        # apply it to bare model names (no colon, no literal bypass).
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
        # Record phase 2 after the entire block, covering all outcomes.
        if profile is not None and ":" not in original_model and not original_model.startswith("!"):
            self._record_phase(
                trace,
                "Default profile resolution",
                model,
                "matched",
                model,
                default_target=self.provider_manager.default_profile,
                profile_name=profile.name,
            )
        else:
            # Determine the skip reason for diagnostic clarity.
            if ":" in original_model:
                reason = "model has explicit prefix"
            elif original_model.startswith("!"):
                reason = "literal bypass model"
            elif self.provider_manager.default_profile is None:
                reason = "no default profile configured"
            else:
                reason = "default profile not found"
            self._record_phase(
                trace,
                "Default profile resolution",
                model,
                "skipped",
                model,
                reason=reason,
            )

        # ---- Phase 3: Profile alias lookup ----
        # Check profile aliases first if a profile is active.
        resolved_model = model
        if profile and model.lower() in profile.aliases:
            resolved_model = profile.aliases[model.lower()]
            logger.debug(f"[ModelManager] Profile alias resolved: '{model}' -> '{resolved_model}'")
            self._record_phase(
                trace,
                "Profile alias lookup",
                model,
                "matched",
                resolved_model,
                alias_key=model.lower(),
                alias_target=resolved_model,
                match_type="exact",
            )
            # AliasManager is skipped when profile alias already matched
            self._record_phase(
                trace,
                "AliasManager resolution",
                model,
                "skipped",
                model,
                reason="profile alias already matched",
            )
        else:
            reason = (
                "no active profile" if not profile else f"'{model.lower()}' not in profile aliases"
            )
            self._record_phase(
                trace,
                "Profile alias lookup",
                model,
                "skipped",
                model,
                reason=reason,
            )
            # Fall through to AliasManager resolution
            # ---- Phase 3b: AliasManager resolution ----
            if self.alias_manager and self.alias_manager.has_aliases():
                # Literal model names (prefixed with '!') must bypass alias matching.
                # Still allow AliasManager to normalize into provider:model form when needed.
                if model.startswith("!"):
                    if ":" not in model:
                        default_target = self.provider_manager.default_target
                        resolved_model = (
                            self.alias_manager.resolve_alias(
                                model, provider=default_target, trace=trace
                            )
                            or model
                        )
                    else:
                        resolved_model = (
                            self.alias_manager.resolve_alias(model, trace=trace) or model
                        )
                    # AliasManager records its own "AliasManager resolution" phase when
                    # trace is provided, so we don't duplicate it here.
                else:
                    alias_count = self.alias_manager.get_alias_count()
                    logger.debug(f"Alias manager available with {alias_count} aliases")

                    # Check if model already has provider prefix
                    if ":" not in model:
                        # No provider prefix - resolve using default target only
                        default_target = self.provider_manager.default_target
                        logger.debug(
                            f"Resolving alias '{model}' with target scope '{default_target}'"
                        )
                        alias_target = self.alias_manager.resolve_alias(
                            model, provider=default_target, trace=trace
                        )
                    else:
                        # Has provider prefix - allow cross-provider resolution
                        logger.debug(f"Resolving alias '{model}' across all providers")
                        alias_target = self.alias_manager.resolve_alias(model, trace=trace)

                    if alias_target:
                        logger.debug(
                            f"[ModelManager] Alias resolved: '{model}' -> '{alias_target}'"
                        )
                        resolved_model = alias_target
                        # AliasManager records its own "AliasManager resolution" phase
                    else:
                        logger.debug(
                            f"No alias match found for '{model}', using original model name"
                        )
                        # AliasManager records its own "AliasManager resolution" phase
                        # (with "no match" result) when trace is provided.
            else:
                logger.debug("No aliases configured or alias manager unavailable")
                self._record_phase(
                    trace,
                    "AliasManager resolution",
                    model,
                    "skipped",
                    model,
                    reason="no aliases configured or alias manager unavailable",
                )

        # ---- Phase 4: Provider prefix parsing ----
        logger.debug(f"Parsing provider prefix from resolved model: '{resolved_model}'")
        provider_name, actual_model = self.provider_manager.parse_model_name(resolved_model)
        logger.debug(f"Parsed provider: '{provider_name}', actual model: '{actual_model}'")
        self._record_phase(
            trace,
            "Provider prefix parsing",
            resolved_model,
            "parsed",
            f"{provider_name}:{actual_model}",
            provider=provider_name,
            model=actual_model,
            default_target=self.provider_manager.default_target,
        )

        # ---- Final result ----
        if trace is not None:
            trace.final_provider = provider_name
            trace.final_model = actual_model

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
