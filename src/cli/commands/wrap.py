"""Placeholder wrap command for future implementations.

Always uses syslog logging, no console output.
"""

import typer

from src.core.logging import configure_logging

app = typer.Typer(help="Wrap command (placeholder)")


@app.command()
def run() -> None:
    """Run placeholder wrap logic with systemd logging enabled."""
    # Configure syslog logging immediately
    configure_logging(use_systemd=True)
    # No output - all goes to syslog when --systemd is used


if __name__ == "__main__":
    app()
