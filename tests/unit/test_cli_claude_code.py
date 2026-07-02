"""Unit tests for the ``vdm claude-code setup`` CLI command."""

from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from src.cli.commands.claude_code import DEFAULT_MODEL, DEFAULT_SMALL_FAST_MODEL
from src.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_setup_merges_env_and_preserves_existing_settings(tmp_path) -> None:
    """Existing settings and env keys should be preserved while Vandamme keys are added."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(make test-unit)"]},
                "env": {"EXISTING": "keep-me"},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["claude-code", "setup", "--settings-path", str(settings_path)])

    assert result.exit_code == 0, result.output
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Bash(make test-unit)"]}
    assert data["env"]["EXISTING"] == "keep-me"
    assert data["env"]["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "1"
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://localhost:8082"
    assert data["env"]["ANTHROPIC_API_BASE_URL"] == "http://localhost:8082"
    assert data["env"]["CLAUDE_AGENT_API_BASE_URL"] == "http://localhost:8082"
    assert data["env"]["ANTHROPIC_MODEL"] == "sonnet"
    assert data["env"]["ANTHROPIC_SMALL_FAST_MODEL"] == "haiku"


@pytest.mark.unit
def test_setup_dry_run_does_not_write_file(tmp_path) -> None:
    """Dry-run should show the merged JSON but not create or mutate settings.json."""
    settings_path = tmp_path / "missing" / "settings.json"

    result = runner.invoke(
        app,
        ["claude-code", "setup", "--settings-path", str(settings_path), "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert not settings_path.exists()
    plain_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    rendered = json.loads(plain_output.split("\nConfigured env keys:")[0])
    assert rendered["settings_path"] == str(settings_path)
    assert rendered["skipped_env_keys"] == []
    assert rendered["env"]["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "1"
    assert rendered["env"]["ANTHROPIC_API_BASE_URL"] == "http://localhost:8082"
    assert rendered["env"]["CLAUDE_AGENT_API_BASE_URL"] == "http://localhost:8082"
    assert rendered["env"]["ANTHROPIC_MODEL"] == DEFAULT_MODEL
    assert rendered["env"]["ANTHROPIC_SMALL_FAST_MODEL"] == DEFAULT_SMALL_FAST_MODEL


@pytest.mark.unit
def test_setup_dry_run_redacts_secret_values(tmp_path) -> None:
    """Dry-run should not print sensitive proxy credentials."""
    settings_path = tmp_path / "settings.json"
    secret_key = "secret-proxy-key"
    secret_token = "secret-proxy-token"

    result = runner.invoke(
        app,
        [
            "claude-code",
            "setup",
            "--settings-path",
            str(settings_path),
            "--api-key",
            secret_key,
            "--auth-token",
            secret_token,
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not settings_path.exists()
    assert secret_key not in result.output
    assert secret_token not in result.output
    plain_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    rendered = json.loads(plain_output.split("\nConfigured env keys:")[0])
    assert rendered["settings_path"] == str(settings_path)
    assert rendered["skipped_env_keys"] == []
    assert rendered["env"]["ANTHROPIC_API_KEY"] == "***"
    assert rendered["env"]["ANTHROPIC_AUTH_TOKEN"] == "***"


@pytest.mark.unit
def test_setup_uses_generic_defaults_not_provider_specific(tmp_path) -> None:
    """Defaults should enable generic Vandamme gateway discovery aliases."""
    settings_path = tmp_path / "settings.json"

    result = runner.invoke(app, ["claude-code", "setup", "--settings-path", str(settings_path)])

    assert result.exit_code == 0, result.output
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["env"]["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "1"
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://localhost:8082"
    assert data["env"]["ANTHROPIC_API_BASE_URL"] == "http://localhost:8082"
    assert data["env"]["CLAUDE_AGENT_API_BASE_URL"] == "http://localhost:8082"
    assert data["env"]["ANTHROPIC_MODEL"] == "sonnet"
    assert data["env"]["ANTHROPIC_SMALL_FAST_MODEL"] == "haiku"
    assert "chatgpt" not in json.dumps(data).lower()


@pytest.mark.unit
def test_setup_honors_custom_base_url_for_all_gateway_keys(tmp_path) -> None:
    """Custom base URL should be applied to each known Claude Code gateway URL key."""
    settings_path = tmp_path / "settings.json"

    result = runner.invoke(
        app,
        [
            "claude-code",
            "setup",
            "--settings-path",
            str(settings_path),
            "--base-url",
            "http://127.0.0.1:9090",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:9090"
    assert data["env"]["ANTHROPIC_API_BASE_URL"] == "http://127.0.0.1:9090"
    assert data["env"]["CLAUDE_AGENT_API_BASE_URL"] == "http://127.0.0.1:9090"


@pytest.mark.unit
def test_setup_preserves_existing_vandamme_keys_without_force(tmp_path) -> None:
    """Existing Claude Code gateway env values should not be overwritten unless forced."""
    settings_path = tmp_path / "settings.json"
    secret_existing_key = "existing-secret-key"
    settings_path.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_MODEL": "custom-existing-model",
                    "ANTHROPIC_API_KEY": secret_existing_key,
                    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "0",
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "claude-code",
            "setup",
            "--settings-path",
            str(settings_path),
            "--api-key",
            "new-secret-key",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_MODEL"] == "custom-existing-model"
    assert data["env"]["ANTHROPIC_API_KEY"] == secret_existing_key
    assert data["env"]["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "0"
    assert "Preserved existing values" in result.output
    assert secret_existing_key not in result.output
    assert "new-secret-key" not in result.output


@pytest.mark.unit
def test_setup_dry_run_only_shows_vandamme_delta_not_existing_env(tmp_path) -> None:
    """Dry-run should not dump unrelated existing environment values."""
    settings_path = tmp_path / "settings.json"
    unrelated_secret = "unrelated-existing-secret"
    settings_path.write_text(
        json.dumps({"env": {"UNRELATED_SECRET": unrelated_secret, "EXISTING": "keep-me"}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["claude-code", "setup", "--settings-path", str(settings_path), "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert unrelated_secret not in result.output
    plain_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    rendered = json.loads(plain_output.split("\nConfigured env keys:")[0])
    assert "UNRELATED_SECRET" not in rendered["env"]
    assert "EXISTING" not in rendered["env"]
    assert rendered["env"]["ANTHROPIC_MODEL"] == DEFAULT_MODEL


@pytest.mark.unit
def test_setup_force_overwrites_existing_vandamme_keys(tmp_path) -> None:
    """--force should replace existing Claude Code gateway env values with requested values."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_MODEL": "custom-existing-model",
                    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "0",
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "claude-code",
            "setup",
            "--settings-path",
            str(settings_path),
            "--model",
            "opus",
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["env"]["ANTHROPIC_MODEL"] == "opus"
    assert data["env"]["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] == "1"


@pytest.mark.unit
def test_claude_code_command_is_registered() -> None:
    """The main CLI should expose the claude-code setup command."""
    result = runner.invoke(app, ["claude-code", "--help"])

    assert result.exit_code == 0, result.output
    assert "setup" in result.output
