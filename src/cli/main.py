"""Main CLI entry point for vandamme-proxy."""

import logging
import sys

import typer

# Import command modules
from src.cli.commands import config, health, models, server, test
from src.cli.commands.wrap import wrap

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
app.add_typer(models.app, name="models", help="Model discovery")
app.add_typer(test.app, name="test", help="Test commands")

# Add wrap as a command directly with support for extra arguments
app.command(context_settings={"allow_extra_args": True})(wrap)

# Note: wrap command handles its own logging configuration

# Get the application logger
logger = logging.getLogger(__name__)


def claude_alias() -> None:
    """Alias that runs 'vdm wrap claude' with all arguments."""
    # Get all arguments after 'claude.vdm'
    args = sys.argv[1:]  # Skip 'claude.vdm'

    # Build the vdm wrap claude command
    cmd = ["vdm", "wrap", "claude"] + args

    # Execute the command
    import subprocess

    try:
        process = subprocess.run(cmd)
        sys.exit(process.returncode)
    except KeyboardInterrupt:
        sys.exit(130)  # Standard SIGINT exit code
    except FileNotFoundError:
        logger.error("vdm command not found. Make sure vandamme-proxy is installed.")
        sys.exit(1)


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
