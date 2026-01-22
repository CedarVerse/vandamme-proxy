"""Presenters for profile display in CLI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileInfo:
    """Information about a single profile."""

    name: str
    timeout: int | None
    max_retries: int | None
    alias_count: int
    aliases: dict[str, str]
    source: str


@dataclass(frozen=True)
class ProfileSummary:
    """Complete profile summary for presentation."""

    total_profiles: int
    profiles: tuple[ProfileInfo, ...]


class ProfileSummaryPresenter:
    """Presenter for profile summary display."""

    SOURCE_COLORS = {
        "local": "[cyan]",
        "user": "[green]",
        "package": "[dim]",
    }

    def __init__(self) -> None:
        """Initialize presenter without console (uses print for Active Providers style)."""
        pass

    def present_summary(
        self,
        summary: ProfileSummary,
        active_profile_name: str | None = None,
    ) -> None:
        """Display profile summary (Active Providers style).

        Args:
            summary: ProfileSummary data with all profiles to display
            active_profile_name: Name of the active/default profile, if any
        """
        if summary.total_profiles == 0:
            return

        print(f"\n🔧 Profiles ({summary.total_profiles} configured):")
        print(f"   {'Name':<12} {'Timeout':<12} {'Max Retries':<12} {'Aliases':<8} {'Source':<10}")
        print(f"   {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 8} {'-' * 10}")

        for profile in summary.profiles:
            # Determine if this is the active profile
            is_active = (
                active_profile_name is not None
                and profile.name.lower() == active_profile_name.lower()
            )
            active_indicator = "* " if is_active else "  "

            # Format name with active indicator
            name_display = f"{active_indicator}{profile.name}"

            timeout_display = f"{profile.timeout}s" if profile.timeout else "inherited"
            retries_display = str(profile.max_retries) if profile.max_retries else "inherited"

            # Color the active profile name
            if is_active:
                print(
                    f"   \033[92m{name_display:<12}\033[0m {timeout_display:<12} "
                    f"{retries_display:<12} {profile.alias_count:<8} {profile.source:<10}"
                )
            else:
                print(
                    f"   {name_display:<12} {timeout_display:<12} "
                    f"{retries_display:<12} {profile.alias_count:<8} {profile.source:<10}"
                )

        # Add legend if there's an active profile
        if active_profile_name is not None:
            print("  * = active/default profile")

    def present_active_profile_aliases(
        self,
        summary: ProfileSummary,
        active_profile_name: str,
    ) -> None:
        """Display aliases for the active/default profile (Active Providers style).

        Args:
            summary: ProfileSummary with all profiles
            active_profile_name: Name of the active profile to show aliases for
        """
        # Find the active profile
        active_profile = next(
            (p for p in summary.profiles if p.name.lower() == active_profile_name.lower()),
            None,
        )
        if not active_profile or not active_profile.aliases:
            return

        print(f"\n✨ Active Profile Aliases ({active_profile.name}):")
        print(f"   {'Alias':<20} {'Target Model'}")
        print(f"   {'-' * 20} {'-' * 50}")

        for alias, target in sorted(active_profile.aliases.items()):
            print(f"   {alias:<20} {target}")
