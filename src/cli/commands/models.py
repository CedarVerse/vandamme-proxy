"""Model-related CLI commands."""

from __future__ import annotations

import json

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Model discovery and recommendations")
console = Console()


@app.command("top")
def top_models(
    base_url: str = typer.Option(
        "http://localhost:8082",
        "--base-url",
        help="Vandamme proxy base URL",
    ),
    limit: int = typer.Option(10, "--limit", min=1, max=50, help="Max models to show"),
    refresh: bool = typer.Option(False, "--refresh", help="Bypass cache"),
    provider: str | None = typer.Option(None, "--provider", help="Filter by provider"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON output"),
) -> None:
    """Show curated top models (fetched remotely, cached locally by the server)."""

    params: dict[str, str | int | float | bool | None] = {"limit": limit, "refresh": refresh}
    if provider:
        params["provider"] = provider

    url = base_url.rstrip("/") + "/top-models"
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()

    payload = resp.json()

    if json_output:
        console.print_json(json.dumps(payload))
        return

    table = Table(title="Top Models")
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="bold")
    table.add_column("Context", justify="right")
    table.add_column("Avg $/M", justify="right")
    table.add_column("Capabilities")
    table.add_column("Source", justify="right")

    source = "cache" if payload.get("cached") else "live"

    for m in payload.get("data", []):
        provider_name = m.get("provider") or ""
        model_id = m.get("id") or ""
        ctx = m.get("context_window")
        ctx_s = str(ctx) if isinstance(ctx, int) else ""

        pricing = m.get("pricing") or {}
        avg = pricing.get("average_per_million")
        avg_s = f"{avg:.3f}" if isinstance(avg, (int, float)) else ""

        caps = m.get("capabilities")
        caps_s = ", ".join(caps) if isinstance(caps, list) else ""

        table.add_row(provider_name, model_id, ctx_s, avg_s, caps_s, source)

    console.print(table)

    aliases = payload.get("aliases")
    if isinstance(aliases, dict) and aliases:
        console.print("\nSuggested aliases:")
        for k, v in sorted(aliases.items()):
            console.print(f"  {k} -> {v}")
