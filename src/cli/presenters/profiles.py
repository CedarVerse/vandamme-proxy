"""Presenters for profile display in CLI."""

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table


@dataclass(frozen=True)
class ProfileInfo:
    """Information about a single profile."""

    name: str
    timeout: int | None
    max_retries: int | None
    alias_count: int
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

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def present_summary(
        self,
        summary: ProfileSummary,
        active_profile_name: str | None = None,
    ) -> None:
        """Display profile summary with color formatting.

        Args:
            summary: ProfileSummary data with all profiles to display
            active_profile_name: Name of the active/default profile, if any
        """
        if summary.total_profiles == 0:
            return

        self.console.print(f"\n🔧 Profiles ({summary.total_profiles} configured):")

        table = Table(show_header=True, box=None, pad_edge=False)
        table.add_column("Name", style="bold", width=15)
        table.add_column("Timeout", width=12)
        table.add_column("Max Retries", width=12)
        table.add_column("Aliases", width=8)
        table.add_column("Source", width=10)

        for profile in summary.profiles:
            # Determine if this is the active profile
            is_active = (
                active_profile_name is not None
                and profile.name.lower() == active_profile_name.lower()
            )
            active_indicator = "* " if is_active else "  "

            # Format name with active indicator
            name_display = f"{active_indicator}{profile.name}"

            timeout_display = f"{profile.timeout}s" if profile.timeout else "[dim]inherited[/dim]"
            retries_display = (
                str(profile.max_retries) if profile.max_retries else "[dim]inherited[/dim]"
            )
            source_color = self.SOURCE_COLORS.get(profile.source, "")
            source_reset = "[/]" if source_color else ""
            source_display = f"{source_color}{profile.source}{source_reset}"

            table.add_row(
                name_display,
                timeout_display,
                retries_display,
                str(profile.alias_count),
                source_display,
            )

        self.console.print(table)

        # Add legend if there's an active profile
        if active_profile_name is not None:
            self.console.print("  * = active/default profile")
