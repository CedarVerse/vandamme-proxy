"""Main CLI entry point for vandamme-proxy."""

import logging

import typer

# Import command modules
from src.cli.commands import config, health, server, test, wrap

app = typer.Typer(
    name="vdm",
    help="Vandamme Proxy CLI - Elegant management for your proxy server",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Add subcommands
app.add_typer(server.app, name="server", help="Server management")
app.add_typer(config.app, name="config", help="Configuration management")
app.add_typer(health.app, name="health", help="Health checks")
app.add_typer(test.app, name="test", help="Test commands")
app.add_typer(wrap.app, name="wrap", help="Wrap command (systemd logging)")

# Note: wrap command always uses systemd logging; no global --systemd flag

# Get the application logger
logger = logging.getLogger(__name__)


@app.command()
def version() -> None:
    """Show version information."""
    from src import __version__

    # Use the logger instead of print
    logger.info(f"vdm version {__version__}")


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config_file: str = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Vandamme Proxy CLI."""
    # Note: Verbose flag sets DEBUG level globally.
    # Individual commands (like server start) may override this with their own logging config.
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if config_file:
        # Load custom config file
        logger.warning(f"Config file loading not yet implemented: {config_file}")
        # TODO: Implement config file loading


if __name__ == "__main__":
    app()
