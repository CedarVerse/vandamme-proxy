"""Unit tests for the ``vdm debug model-resolution`` CLI command.

These tests verify the CLI interface layer: argument parsing, output rendering,
error handling, and JSON serialisation.  The underlying ModelManager resolution
logic is tested separately in ``test_model_resolution_trace.py``.

Design notes
------------
- We mock ``src.core.dependencies`` (initialize_app, get_model_manager) because
  the CLI command imports them lazily inside the function body.  Patching the
  dependency module (not the CLI module) ensures the mock is visible regardless
  of when the lazy import executes.
- The mock ``resolve_model`` uses a ``side_effect`` callable that populates the
  trace in-place, mirroring what the real ModelManager does.  This lets us
  verify the full rendering pipeline (text and JSON) without instantiating the
  real dependency graph.
- Each test is isolated: no shared fixtures, no cross-test state.
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.core.model_resolution_trace import ResolutionPhase, ResolutionTrace

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_populated_trace(model: str = "haiku") -> ResolutionTrace:
    """Build a ResolutionTrace that mimics the real pipeline output.

    Contains two phases (profile prefix detection + provider prefix parsing)
    plus a final result, which is enough to exercise all rendering branches.
    """
    trace = ResolutionTrace(original_model=model)

    trace.phases.append(
        ResolutionPhase(
            name="Profile prefix detection",
            input=model,
            result="skipped",
            output=model,
            details={"reason": "no colon in model name"},
        )
    )
    trace.phases.append(
        ResolutionPhase(
            name="Provider prefix parsing",
            input=model,
            result="parsed",
            output=f"poe:{model}",
            details={"provider": "poe", "model": model},
        )
    )
    trace.final_provider = "poe"
    trace.final_model = model
    return trace


def _fake_resolve_model(model: str = "haiku", *, trace=None):
    """Side-effect for mock resolve_model that populates the trace in-place.

    The real ModelManager.resolve_model() mutates the trace as it walks the
    resolution pipeline.  Our mock must do the same so the CLI rendering code
    has data to display.
    """
    if trace is not None:
        for phase in _make_populated_trace(model).phases:
            trace.phases.append(phase)
        trace.final_provider = "poe"
        trace.final_model = model
    return ("poe", model)


def _mock_model_manager():
    """Create a mock ModelManager with resolve_model wired to our fake."""
    mm = Mock()
    mm.resolve_model.side_effect = _fake_resolve_model
    return mm


# ---------------------------------------------------------------------------
# Test 1: Plain text output
# ---------------------------------------------------------------------------


class TestDebugModelResolutionTextOutput:
    """Plain text output should contain phase names and the final result."""

    @pytest.mark.unit
    @patch("src.core.dependencies.get_model_manager")
    @patch("src.core.dependencies.initialize_app")
    def test_text_output_contains_phase_names_and_result(
        self, mock_init: Mock, mock_get_mm: Mock
    ) -> None:
        """Invoking with a model name should print phase headings and the final provider:model."""
        mock_get_mm.return_value = _mock_model_manager()

        result = runner.invoke(app, ["debug", "model-resolution", "haiku"])

        assert result.exit_code == 0, f"Unexpected failure:\n{result.output}"

        # Header line
        assert "Resolving model: haiku" in result.output

        # Phase names rendered by Rich (strip ANSI codes for plain assertion)
        plain = result.output
        assert "Profile prefix detection" in plain
        assert "Provider prefix parsing" in plain

        # Final result line
        assert "poe:haiku" in plain


# ---------------------------------------------------------------------------
# Test 2: JSON output
# ---------------------------------------------------------------------------


class TestDebugModelResolutionJsonOutput:
    """JSON output should be valid JSON with the expected top-level keys."""

    @pytest.mark.unit
    @patch("src.core.dependencies.get_model_manager")
    @patch("src.core.dependencies.initialize_app")
    def test_json_output_is_valid_with_expected_keys(
        self, mock_init: Mock, mock_get_mm: Mock
    ) -> None:
        """--json flag should emit parseable JSON with original_model, phases, and final result."""
        mock_get_mm.return_value = _mock_model_manager()

        result = runner.invoke(app, ["debug", "model-resolution", "haiku", "--json"])

        assert result.exit_code == 0, f"Unexpected failure:\n{result.output}"

        data = json.loads(result.output)

        # Top-level keys
        assert data["original_model"] == "haiku"
        assert data["final_provider"] == "poe"
        assert data["final_model"] == "haiku"

        # Phases list
        assert isinstance(data["phases"], list)
        assert len(data["phases"]) >= 1

        # Each phase should have the required fields
        for phase in data["phases"]:
            assert "name" in phase
            assert "input" in phase
            assert "result" in phase
            assert "output" in phase
            assert "details" in phase


# ---------------------------------------------------------------------------
# Test 3: Empty model name rejected
# ---------------------------------------------------------------------------


class TestDebugModelResolutionEmptyModel:
    """An empty (or whitespace-only) model name should be rejected with exit code 1."""

    @pytest.mark.unit
    @patch("src.core.dependencies.get_model_manager")
    @patch("src.core.dependencies.initialize_app")
    def test_empty_model_rejected(self, mock_init: Mock, mock_get_mm: Mock) -> None:
        """Empty string model should produce a non-zero exit and 'cannot be empty' message."""
        # NOTE: initialize_app and get_model_manager should NOT be called when
        # the model name fails validation first, but we mock them anyway so
        # that any import-time side effects in dependencies don't leak.
        mock_get_mm.return_value = _mock_model_manager()

        result = runner.invoke(app, ["debug", "model-resolution", ""])

        assert result.exit_code == 1
        assert "cannot be empty" in result.output

    @pytest.mark.unit
    @patch("src.core.dependencies.get_model_manager")
    @patch("src.core.dependencies.initialize_app")
    def test_whitespace_only_model_rejected(self, mock_init: Mock, mock_get_mm: Mock) -> None:
        """Whitespace-only model name should also be rejected."""
        mock_get_mm.return_value = _mock_model_manager()

        result = runner.invoke(app, ["debug", "model-resolution", "   "])

        assert result.exit_code == 1
        assert "cannot be empty" in result.output


# ---------------------------------------------------------------------------
# Test 4: Initialization failure shows actionable error
# ---------------------------------------------------------------------------


class TestDebugModelResolutionInitFailure:
    """When initialize_app() raises, the CLI should show an actionable error message."""

    @pytest.mark.unit
    @patch("src.core.dependencies.initialize_app")
    def test_init_failure_shows_actionable_message(self, mock_init: Mock) -> None:
        """RuntimeError from initialize_app should produce exit code 1 with guidance."""
        mock_init.side_effect = RuntimeError("No providers configured")

        result = runner.invoke(app, ["debug", "model-resolution", "haiku"])

        assert result.exit_code == 1
        assert "Initialization failed" in result.output
        # The command prints a suggestion to set PROVIDER_API_KEY
        assert "PROVIDER_API_KEY" in result.output
