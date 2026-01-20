"""Profile configuration for reusable settings and aliases."""

from dataclasses import dataclass


@dataclass
class ProfileConfig:
    """Configuration for a profile (reusable settings + aliases bundle).

    A profile is a decorator that modifies timeout, retries, and aliases
    without replacing the underlying provider infrastructure.

    Profile names are stored WITHOUT the # prefix (the # is only for
    visual distinction in TOML files).

    Attributes:
        name: Profile name (without # prefix)
        timeout: Request timeout in seconds, or None to inherit from [defaults]
        max_retries: Maximum retry attempts, or None to inherit from [defaults]
        aliases: Mapping of alias -> provider:model (MUST have provider prefix)
        source: Where defined: "local", "user", "package"
    """

    name: str
    timeout: int | None
    max_retries: int | None
    aliases: dict[str, str]
    source: str

    def validate(self, available_providers: set[str]) -> list[str]:
        """Validate profile configuration.

        Args:
            available_providers: Set of known provider names

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for alias, target in self.aliases.items():
            if ":" not in target:
                errors.append(
                    f"Profile '{self.name}' alias '{alias}' must include provider prefix.\n"
                    f'  Invalid: {alias} = "{target}"\n'
                    f'  Valid: {alias} = "provider:model"'
                )
            else:
                provider = target.split(":", 1)[0].lower()
                if provider not in available_providers:
                    errors.append(
                        f"Profile '{self.name}' alias '{alias}' "
                        f"references unknown provider '{provider}'.\n"
                        f"  Available providers: "
                        f"{', '.join(sorted(available_providers))}"
                    )
        return errors
