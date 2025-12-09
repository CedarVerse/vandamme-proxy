"""Test commands for the vdm CLI."""

import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.config import config

app = typer.Typer(help="Test commands")


@app.command()
def connection() -> None:
    """Test API connectivity."""
    console = Console()

    console.print("[bold cyan]Testing API Connectivity[/bold cyan]")
    console.print()

    # Test configuration
    try:
        if not config.openai_api_key:
            console.print("[red]❌ OPENAI_API_KEY not configured[/red]")
            sys.exit(1)

        console.print(f"✅ API Key configured: {config.openai_api_key_hash}")
        console.print(f"✅ Default Provider: {config.default_provider}")
        console.print(f"✅ Base URL: {config.openai_base_url}")
        console.print(f"✅ Big Model: {config.big_model}")
        console.print(f"✅ Middle Model: {config.middle_model}")
        console.print(f"✅ Small Model: {config.small_model}")

        console.print()
        console.print(
            Panel(
                "To run a full connectivity test, use: [cyan]vdm health upstream[/cyan]",
                title="Next Steps",
                expand=False,
            )
        )

    except Exception as e:
        console.print(f"[red]❌ Configuration test failed: {str(e)}[/red]")
        sys.exit(1)


@app.command()
def models() -> None:
    """Test model mappings."""
    console = Console()

    console.print("[bold cyan]Testing Model Mappings[/bold cyan]")
    console.print()

    # Define test mappings
    test_models = [
        ("claude-3-haiku", config.small_model),
        ("claude-3-5-haiku", config.small_model),
        ("claude-3-sonnet", config.middle_model),
        ("claude-3-5-sonnet", config.middle_model),
        ("claude-3-opus", config.big_model),
    ]

    table = Table(title="Model Mappings")
    table.add_column("Claude Model", style="cyan")
    table.add_column("Maps To", style="green")
    table.add_column("Type", style="yellow")

    for claude_model, openai_model in test_models:
        model_type = (
            "Small"
            if "haiku" in claude_model.lower()
            else "Middle" if "sonnet" in claude_model.lower() else "Big"
        )
        table.add_row(claude_model, openai_model, model_type)

    console.print(table)

    console.print()
    console.print(
        Panel(
            "These mappings are applied automatically when requests are processed.",
            title="Model Mapping Information",
            expand=False,
        )
    )


@app.command()
def providers() -> None:
    """List all configured providers."""
    console = Console()

    console.print("[bold cyan]Configured Providers[/bold cyan]")
    console.print()

    # Load providers
    try:
        config.provider_manager.load_provider_configs()
        providers = config.provider_manager.list_providers()

        if not providers:
            console.print("[yellow]No providers configured[/yellow]")
            console.print()
            console.print(
                Panel(
                    "Configure providers by setting {PROVIDER}_API_KEY and {PROVIDER}_BASE_URL environment variables.",
                    title="Provider Configuration",
                    expand=False,
                )
            )
            return

        table = Table(title="Provider Configuration")
        table.add_column("Provider", style="cyan")
        table.add_column("Base URL", style="green")
        table.add_column("API Version", style="yellow")
        table.add_column("Default", style="magenta")

        for provider_name, provider_config in providers.items():
            is_default = "✓" if provider_name == config.provider_manager.default_provider else ""
            api_version = provider_config.api_version or "N/A"
            table.add_row(
                provider_name,
                provider_config.base_url,
                api_version,
                is_default
            )

        console.print(table)
        console.print()

        # Show default provider
        console.print(f"Default Provider: [bold]{config.provider_manager.default_provider}[/bold]")
        console.print()

        # Show examples
        console.print(
            Panel(
                f"Use providers with model prefixes:\n"
                f"• [cyan]openrouter:gpt-4o[/cyan] → Uses OpenRouter\n"
                f"• [cyan]poe:gemini-3-pro[/cyan] → Uses Poe\n"
                f"• [cyan]claude-3-5-sonnet[/cyan] → Uses default provider ({config.provider_manager.default_provider})",
                title="Usage Examples",
                expand=False,
            )
        )

    except Exception as e:
        console.print(f"[red]❌ Error loading providers: {str(e)}[/red]")
        sys.exit(1)
