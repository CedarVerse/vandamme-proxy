"""Test ProfileSummaryPresenter with active profile indicator and aliases display."""

import re

import pytest

from src.cli.presenters.profiles import ProfileInfo, ProfileSummary, ProfileSummaryPresenter


@pytest.mark.unit
def test_profile_summary_with_active_profile_indicator(capsys):
    """Test that active profile is shown with * indicator."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(
        total_profiles=3,
        profiles=(
            ProfileInfo(
                name="top",
                timeout=120,
                max_retries=3,
                alias_count=5,
                aliases={
                    "fast": "openai:gpt-4o-mini",
                    "smart": "anthropic:claude-3-5-sonnet-20241022",
                },
                source="local",
            ),
            ProfileInfo(
                name="chatgpt",
                timeout=None,
                max_retries=None,
                alias_count=2,
                aliases={"haiku": "gpt-5-mini-2025-08-07"},
                source="package",
            ),
            ProfileInfo(
                name="openai",
                timeout=90,
                max_retries=2,
                alias_count=3,
                aliases={"fast": "gpt-4o-mini"},
                source="user",
            ),
        ),
    )

    # Call with active_profile_name="top"
    presenter.present_summary(summary, active_profile_name="top")

    captured = capsys.readouterr()
    output = captured.out
    # Look for the pattern with * before top (may have ANSI codes between)
    assert re.search(r"\*\s*top", output, re.IGNORECASE), "Active profile should have * indicator"
    assert "chatgpt" in output
    assert "openai" in output
    # Legend should be present
    assert "* = active" in output or "* = default" in output, "Legend should explain * indicator"


@pytest.mark.unit
def test_profile_summary_without_active_profile(capsys):
    """Test profile summary with no active profile."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(
        total_profiles=2,
        profiles=(
            ProfileInfo(
                name="chatgpt",
                timeout=None,
                max_retries=None,
                alias_count=2,
                aliases={"haiku": "gpt-5-mini-2025-08-07"},
                source="package",
            ),
            ProfileInfo(
                name="openai",
                timeout=90,
                max_retries=2,
                alias_count=3,
                aliases={"fast": "gpt-4o-mini"},
                source="user",
            ),
        ),
    )

    # Call with no active profile
    presenter.present_summary(summary, active_profile_name=None)

    captured = capsys.readouterr()
    output = captured.out
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
def test_profile_summary_case_insensitive(capsys):
    """Test that active profile matching is case-insensitive."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(
        total_profiles=2,
        profiles=(
            ProfileInfo(
                name="TOP",
                timeout=120,
                max_retries=3,
                alias_count=5,
                aliases={"fast": "openai:gpt-4o-mini"},
                source="local",
            ),
            ProfileInfo(
                name="openai",
                timeout=90,
                max_retries=2,
                alias_count=3,
                aliases={"fast": "gpt-4o-mini"},
                source="user",
            ),
        ),
    )

    # Call with lowercase "top" but profile name is "TOP"
    presenter.present_summary(summary, active_profile_name="top")

    captured = capsys.readouterr()
    output = captured.out
    # The profile name in output should have the indicator
    assert re.search(r"\*\s*TOP", output, re.IGNORECASE), (
        "Active profile should match case-insensitively and show indicator"
    )


@pytest.mark.unit
def test_profile_summary_empty(capsys):
    """Test that empty summary produces no output."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(total_profiles=0, profiles=())

    presenter.present_summary(summary, active_profile_name="top")

    captured = capsys.readouterr()
    output = captured.out
    assert "Profiles" not in output


@pytest.mark.unit
def test_present_active_profile_aliases_shows_aliases(capsys):
    """Test that present_active_profile_aliases displays profile aliases."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(
        total_profiles=2,
        profiles=(
            ProfileInfo(
                name="myprofile",
                timeout=120,
                max_retries=3,
                alias_count=2,
                aliases={
                    "fast": "openai:gpt-4o-mini",
                    "smart": "anthropic:claude-3-5-sonnet-20241022",
                },
                source="local",
            ),
            ProfileInfo(
                name="other",
                timeout=90,
                max_retries=2,
                alias_count=1,
                aliases={"haiku": "zai:haiku"},
                source="package",
            ),
        ),
    )

    presenter.present_active_profile_aliases(summary, active_profile_name="myprofile")

    captured = capsys.readouterr()
    output = captured.out
    assert "Active Profile Aliases (myprofile)" in output
    assert "fast" in output
    assert "openai:gpt-4o-mini" in output
    assert "smart" in output
    assert "anthropic:claude-3-5-sonnet-20241022" in output


@pytest.mark.unit
def test_present_active_profile_aliases_case_insensitive(capsys):
    """Test that active profile name matching is case-insensitive."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(
        total_profiles=1,
        profiles=(
            ProfileInfo(
                name="MYPROFILE",
                timeout=120,
                max_retries=3,
                alias_count=1,
                aliases={"fast": "openai:gpt-4o-mini"},
                source="local",
            ),
        ),
    )

    presenter.present_active_profile_aliases(summary, active_profile_name="myprofile")

    captured = capsys.readouterr()
    output = captured.out
    assert "Active Profile Aliases (MYPROFILE)" in output
    assert "fast" in output
    assert "openai:gpt-4o-mini" in output


@pytest.mark.unit
def test_present_active_profile_aliases_no_output_when_no_aliases(capsys):
    """Test that nothing is displayed when active profile has no aliases."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(
        total_profiles=1,
        profiles=(
            ProfileInfo(
                name="empty",
                timeout=120,
                max_retries=3,
                alias_count=0,
                aliases={},
                source="local",
            ),
        ),
    )

    presenter.present_active_profile_aliases(summary, active_profile_name="empty")

    captured = capsys.readouterr()
    output = captured.out
    assert "Active Profile Aliases" not in output


@pytest.mark.unit
def test_present_active_profile_aliases_no_output_when_profile_not_found(capsys):
    """Test that nothing is displayed when active profile name is not found."""
    presenter = ProfileSummaryPresenter()

    summary = ProfileSummary(
        total_profiles=1,
        profiles=(
            ProfileInfo(
                name="existing",
                timeout=120,
                max_retries=3,
                alias_count=1,
                aliases={"fast": "openai:gpt-4o-mini"},
                source="local",
            ),
        ),
    )

    presenter.present_active_profile_aliases(summary, active_profile_name="nonexistent")

    captured = capsys.readouterr()
    output = captured.out
    assert "Active Profile Aliases" not in output
