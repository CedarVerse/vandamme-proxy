"""
Model alias management for VDM_ALIAS_* environment variables.

This module provides flexible model name resolution with case-insensitive
substring matching, supporting provider prefixes in alias values.
"""

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AliasManager:
    """
    Manages model aliases with case-insensitive substring matching.

    Supports VDM_ALIAS_* environment variables where:
    - VDM_ALIAS_FAST=openai:gpt-4o-mini
    - VDM_ALIAS_HAIKU=poe:gpt-4o-mini
    - VDM_ALIAS_CHAT=anthropic:claude-3-5-sonnet-20241022
    """

    def __init__(self) -> None:
        """Initialize AliasManager and load aliases from environment."""
        self.aliases: Dict[str, str] = {}
        self._load_aliases()

    def _load_aliases(self) -> None:
        """
        Load VDM_ALIAS_* environment variables.

        Expected format: VDM_ALIAS_<NAME>=<target_model>
        Example: VDM_ALIAS_FAST=openai:gpt-4o-mini
        """
        alias_pattern = re.compile(r"^VDM_ALIAS_(.+)$")

        for env_key, env_value in os.environ.items():
            match = alias_pattern.match(env_key)
            if match:
                alias_name = match.group(1).lower()  # Store aliases in lowercase

                if not env_value or not env_value.strip():
                    logger.warning(f"Empty alias value for {env_key}, skipping")
                    continue

                if self._validate_alias(alias_name, env_value):
                    self.aliases[alias_name] = env_value.strip()
                    logger.info(f"Loaded model alias: {alias_name} -> {env_value}")
                else:
                    logger.warning(
                        f"Invalid alias configuration for {env_key}={env_value}, skipping"
                    )

        if self.aliases:
            logger.info(f"Loaded {len(self.aliases)} model aliases")

    def _validate_alias(self, alias: str, value: str) -> bool:
        """
        Validate alias configuration.

        Args:
            alias: The alias name (lowercase)
            value: The alias target value

        Returns:
            True if valid, False otherwise
        """
        # Check for circular reference
        if alias == value.lower():
            logger.error(f"Circular alias reference detected: {alias} -> {value}")
            return False

        # Basic format validation - allow most characters in model names
        # Allow provider:model format or plain model names
        # Be permissive since model names can have various formats
        if not value or not value.strip():
            return False

        # Disallow characters that are clearly invalid for model names
        # Allow letters, numbers, hyphens, underscores, dots, slashes, colons
        # @ is not allowed as it's typically used for usernames or emails
        if "@" in value:
            logger.warning(f"Invalid alias target format (contains @): {value}")
            return False

        return True

    def resolve_alias(self, model: str) -> Optional[str]:
        """
        Resolve model name to alias value with case-insensitive substring matching.

        Resolution algorithm:
        1. Convert model name to lowercase
        2. Create variations of model name (with underscores and hyphens)
        3. Find all aliases where alias name matches any variation
        4. If exact match exists, return it immediately
        5. Otherwise, select longest matching substring
        6. If tie, select alphabetically first

        Args:
            model: The requested model name

        Returns:
            The resolved alias target or None if no match found
        """
        if not model or not self.aliases:
            return None

        model_lower = model.lower()

        # Create variations of the model name for matching
        # This allows "my_model" to match both "my-model" and "my_model" in the model name
        model_variations = {
            model_lower,  # Original
            model_lower.replace("_", "-"),  # Underscores to hyphens
            model_lower.replace("-", "_"),  # Hyphens to underscores
        }

        # Find all matching aliases
        matches: List[Tuple[str, str, int]] = []  # (alias, target, match_length)

        for alias, target in self.aliases.items():
            alias_lower = alias.lower()

            # Check if alias matches any variation of the model name
            for variation in model_variations:
                if alias_lower in variation:
                    # Use the actual matched length from the variation
                    match_length = len(alias_lower)
                    matches.append((alias, target, match_length))
                    break  # Found a match, no need to check other variations

        if not matches:
            return None

        # Sort matches: exact match first, then by length, then alphabetically
        # For exact match, check against all variations
        matches.sort(
            key=lambda x: (
                (
                    0 if any(x[0].lower() == variation for variation in model_variations) else 1
                ),  # Exact match first
                -x[2],  # Longer match first
                x[0],  # Alphabetical order
            )
        )

        best_match = matches[0]
        logger.debug(
            f"Resolved model alias '{model}' -> '{best_match[1]}' "
            f"(matched alias '{best_match[0]}')"
        )

        return best_match[1]

    def get_all_aliases(self) -> Dict[str, str]:
        """
        Get all configured aliases.

        Returns:
            Dictionary of alias_name -> target_model
        """
        return self.aliases.copy()

    def has_aliases(self) -> bool:
        """
        Check if any aliases are configured.

        Returns:
            True if aliases exist, False otherwise
        """
        return bool(self.aliases)

    def get_alias_count(self) -> int:
        """
        Get the number of configured aliases.

        Returns:
            Number of aliases
        """
        return len(self.aliases)
