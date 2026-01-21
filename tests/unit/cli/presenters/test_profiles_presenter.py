"""Test ProfileSummaryPresenter with active profile indicator."""

import re
from io import StringIO

import pytest
from rich.console import Console

from src.cli.presenters.profiles import ProfileInfo, ProfileSummary, ProfileSummaryPresenter


@pytest.mark.unit
def test_profile_summary_with_active_profile_indicator():
    """Test that active profile is shown with * indicator."""
    console = Console(file=StringIO(), force_terminal=True)
    presenter = ProfileSummaryPresenter(console=console)

    summary = ProfileSummary(
        total_profiles=3,
        profiles=(
            ProfileInfo(name="top", timeout=120, max_retries=3, alias_count=5, source="local"),
            ProfileInfo(
                name="chatgpt", timeout=None, max_retries=None, alias_count=2, source="package"
            ),
            ProfileInfo(name="openai", timeout=90, max_retries=2, alias_count=3, source="user"),
        ),
    )

    # Call with active_profile_name="top"
    presenter.present_summary(summary, active_profile_name="top")

    output = console.file.getvalue()
    # Look for the pattern with * before top (may have ANSI codes between)
    assert re.search(r"\*\s*top", output, re.IGNORECASE), "Active profile should have * indicator"
    assert "chatgpt" in output
    assert "openai" in output
    # Legend should be present
    assert "* = active" in output or "* = default" in output, "Legend should explain * indicator"


@pytest.mark.unit
def test_profile_summary_without_active_profile():
    """Test profile summary with no active profile."""
    console = Console(file=StringIO(), force_terminal=True)
    presenter = ProfileSummaryPresenter(console=console)

    summary = ProfileSummary(
        total_profiles=2,
        profiles=(
            ProfileInfo(
                name="chatgpt", timeout=None, max_retries=None, alias_count=2, source="package"
            ),
            ProfileInfo(name="openai", timeout=90, max_retries=2, alias_count=3, source="user"),
        ),
    )

    # Call with no active profile
    presenter.present_summary(summary, active_profile_name=None)

    output = console.file.getvalue()
    assert "chatgpt" in output
    assert "openai" in output
    # No * indicator should be present in profile names
    assert "*chatgpt" not in output
    assert "*openai" not in output
    # No legend should be present when there's no active profile
    assert "* = active" not in output and "* = default" not in output, (
        "Legend should not appear when no active profile"
    )


@pytest.mark.unit
def test_profile_summary_case_insensitive():
    """Test that active profile matching is case-insensitive."""
    console = Console(file=StringIO(), force_terminal=True)
    presenter = ProfileSummaryPresenter(console=console)

    summary = ProfileSummary(
        total_profiles=2,
        profiles=(
            ProfileInfo(name="TOP", timeout=120, max_retries=3, alias_count=5, source="local"),
            ProfileInfo(name="openai", timeout=90, max_retries=2, alias_count=3, source="user"),
        ),
    )

    # Call with lowercase "top" but profile name is "TOP"
    presenter.present_summary(summary, active_profile_name="top")

    output = console.file.getvalue()
    # The profile name in output should have the indicator
    assert re.search(r"\*\s*TOP", output, re.IGNORECASE), (
        "Active profile should match case-insensitively and show indicator"
    )


@pytest.mark.unit
def test_profile_summary_empty():
    """Test that empty summary produces no output."""
    console = Console(file=StringIO(), force_terminal=True)
    presenter = ProfileSummaryPresenter(console=console)

    summary = ProfileSummary(total_profiles=0, profiles=())

    presenter.present_summary(summary, active_profile_name="top")

    output = console.file.getvalue()
    assert "Profiles" not in output
