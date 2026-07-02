"""Claude Code integration commands."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Claude Code integration")

DEFAULT_BASE_URL = "http://localhost:8082"
DEFAULT_MODEL = "sonnet"
DEFAULT_SMALL_FAST_MODEL = "haiku"


def default_settings_path() -> Path:
    """Return the default Claude Code settings path."""
    return Path.home() / ".claude" / "settings.json"


def load_settings(path: Path) -> dict[str, Any]:
    """Load Claude Code settings, returning an empty settings object when absent."""
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_claude_code_env(
    *,
    base_url: str,
    model: str,
    small_fast_model: str,
    auth_token: str | None = None,
    api_key: str | None = None,
) -> dict[str, str]:
    """Build the environment entries Claude Code needs for Vandamme."""
    env = {
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_API_BASE_URL": base_url,
        "CLAUDE_AGENT_API_BASE_URL": base_url,
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_SMALL_FAST_MODEL": small_fast_model,
    }
    if auth_token:
        env["ANTHROPIC_AUTH_TOKEN"] = auth_token
    if api_key:
        env["ANTHROPIC_API_KEY"] = api_key
    return env


def merge_settings(
    existing: dict[str, Any],
    new_env: dict[str, str],
    *,
    force: bool = False,
) -> tuple[dict[str, Any], set[str]]:
    """Merge Vandamme env settings into an existing Claude Code settings object.

    Returns the merged settings and the names of skipped keys. Keys are skipped
    when they already exist with a different value and ``force`` is false.
    """
    merged = copy.deepcopy(existing)
    existing_env = merged.get("env", {})
    if existing_env is None:
        existing_env = {}
    if not isinstance(existing_env, dict):
        raise ValueError("settings.json field 'env' must be a JSON object when present")

    env = dict(existing_env)
    skipped: set[str] = set()
    for key, value in new_env.items():
        current = env.get(key)
        if current is not None and current != value and not force:
            skipped.add(key)
            continue
        env[key] = value

    merged["env"] = env
    return merged, skipped


SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def is_secret_env_key(key: str) -> bool:
    """Return true when an environment key name conventionally carries a secret."""
    upper_key = key.upper()
    return any(marker in upper_key for marker in SECRET_ENV_MARKERS)


def redact_env_for_display(env: dict[str, str]) -> dict[str, str]:
    """Return env entries safe for terminal display by redacting secret-like keys."""
    return {key: "***" if is_secret_env_key(key) else value for key, value in env.items()}


def write_settings(path: Path, settings: dict[str, Any]) -> None:
    """Write Claude Code settings atomically enough for local CLI use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@app.command()
def setup(
    base_url: str = typer.Option(
        DEFAULT_BASE_URL,
        "--base-url",
        help="Vandamme proxy base URL for Claude Code requests and gateway model discovery.",
    ),
    model: str = typer.Option(
        DEFAULT_MODEL,
        "--model",
        help="Default Claude Code model. Defaults to Vandamme's generic alias.",
    ),
    small_fast_model: str = typer.Option(
        DEFAULT_SMALL_FAST_MODEL,
        "--small-fast-model",
        help="Claude Code small/fast model. Defaults to Vandamme's generic alias.",
    ),
    auth_token: str | None = typer.Option(
        None,
        "--auth-token",
        help="Optional proxy auth token to write as ANTHROPIC_AUTH_TOKEN.",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Optional proxy API key to write as ANTHROPIC_API_KEY.",
    ),
    settings_path: Path | None = typer.Option(
        None,
        "--settings-path",
        help="Claude Code settings.json path. Primarily useful for tests.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the merged settings without writing files.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing Claude Code Vandamme-related env values.",
    ),
) -> None:
    """Configure Claude Code to use Vandamme for model discovery and requests.

    The command updates ``~/.claude/settings.json`` by merging the ``env`` object;
    existing unrelated Claude Code settings are preserved. It enables Claude Code's
    gateway model discovery and points all known Claude Code gateway base URL env
    keys at Vandamme. Existing Claude Code/Vandamme env values are left unchanged
    unless ``--force`` is passed.
    """
    console = Console()
    path = settings_path or Path(os.environ.get("CLAUDE_SETTINGS_PATH", default_settings_path()))

    try:
        existing = load_settings(path)
        new_env = build_claude_code_env(
            base_url=base_url,
            model=model,
            small_fast_model=small_fast_model,
            auth_token=auth_token,
            api_key=api_key,
        )
        merged, skipped = merge_settings(existing, new_env, force=force)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None

    if dry_run:
        typer.echo(
            json.dumps(
                {
                    "settings_path": str(path),
                    "env": redact_env_for_display(
                        {key: value for key, value in new_env.items() if key not in skipped}
                    ),
                    "skipped_env_keys": sorted(skipped),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        write_settings(path, merged)
        console.print(f"[green]✅ Claude Code settings updated:[/green] {path}")

    if skipped:
        skipped_list = ", ".join(sorted(skipped))
        console.print(
            Panel(
                f"Preserved existing values for keys: {skipped_list}\n"
                "Run again with --force to overwrite these keys.",
                title="Existing Claude Code env preserved",
                style="yellow",
            )
        )

    console.print(
        "[dim]Configured env keys: "
        + ", ".join(key for key in sorted(new_env) if key not in skipped)
        + "[/dim]"
    )
