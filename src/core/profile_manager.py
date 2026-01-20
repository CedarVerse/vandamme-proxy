"""Profile management for reusable configuration presets."""

import logging
from typing import Any

from src.core.profile_config import ProfileConfig

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages profile configurations and validation.

    Profiles are loaded from TOML files by AliasConfigLoader and
    validated against available providers.

    Profile names are stored WITHOUT the # prefix (the # is only for
    visual distinction in TOML files).
    """

    def __init__(self) -> None:
        """Initialize ProfileManager with empty profile registry."""
        self._profiles: dict[str, ProfileConfig] = {}

    def load_profiles(self, profiles_dict: dict[str, dict[str, Any]]) -> None:
        """Load profiles from parsed TOML configuration.

        Args:
            profiles_dict: {profile_name: {timeout, max-retries, aliases, source}}
                          Profile names should NOT include # prefix
        """
        self._profiles.clear()
        for name, config in profiles_dict.items():
            self._profiles[name.lower()] = ProfileConfig(
                name=name,
                timeout=config.get("timeout"),
                max_retries=config.get("max-retries"),
                aliases=config.get("aliases", {}),
                source=config.get("source", "unknown"),
            )
        logger.info(f"Loaded {len(self._profiles)} profiles")

    def reload_profiles(self, profiles_dict: dict[str, dict[str, Any]]) -> None:
        """Reload profiles from parsed TOML configuration.

        This is a convenience wrapper around load_profiles() that
        provides semantic clarity for hot-reload scenarios.

        Args:
            profiles_dict: {profile_name: {timeout, max-retries, aliases, source}}
        """
        self.load_profiles(profiles_dict)
        logger.info("Profiles reloaded")

    def get_profile(self, name: str) -> ProfileConfig | None:
        """Get profile by name.

        Args:
            name: Profile name (case-insensitive, no # prefix)

        Returns:
            ProfileConfig or None if not found
        """
        return self._profiles.get(name.lower())

    def list_profiles(self) -> list[str]:
        """List all available profile names.

        Returns:
            Sorted list of profile names (without # prefix)
        """
        return sorted(self._profiles.keys())

    def is_profile(self, name: str) -> bool:
        """Check if a name is a profile (not a provider).

        Args:
            name: Name to check (no # prefix)

        Returns:
            True if name is a profile
        """
        return name.lower() in self._profiles

    def validate_all(self, available_providers: set[str]) -> dict[str, list[str]]:
        """Validate all profiles against available providers.

        Args:
            available_providers: Set of known provider names

        Returns:
            Dict mapping profile names to lists of errors (empty if valid)
        """
        return {
            profile.name: profile.validate(available_providers)
            for profile in self._profiles.values()
        }

    def detect_collisions(self, provider_names: set[str]) -> list[str]:
        """Detect profile names that collide with provider names.

        When a profile name matches a provider name (case-insensitive),
        the profile takes precedence for requests using the 'profile:model'
        prefix. This method logs informative warnings about such collisions.

        Args:
            provider_names: Set of known provider names (case-insensitive comparison)

        Returns:
            List of collision messages (empty if no collisions)
        """
        collisions = []
        provider_lower = {p.lower() for p in provider_names}

        for profile_name in self._profiles:
            if profile_name in provider_lower:
                msg = (
                    f"Profile '{profile_name}' has the same name as provider '{profile_name}'. "
                    f"The profile takes precedence for requests using "
                    f"'{profile_name}:model' prefix."
                )
                collisions.append(msg)

        return collisions
