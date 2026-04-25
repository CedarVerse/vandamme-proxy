"""Debug and diagnostic commands for the vdm CLI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import typer
from rich.console import Console

if TYPE_CHECKING:
    from src.core.model_resolution_trace import ResolutionTrace

app = typer.Typer(help="Debug and diagnostic commands")


@app.command("model-resolution")
def model_resolution(
    model: str = typer.Argument(..., help="Model name to resolve (as sent by client)"),
    json_output: bool = typer.Option(False, "--json", help="Output trace as JSON"),
) -> None:
    """Trace the full model resolution pipeline for a model name.

    Shows each resolution phase (profile prefix, alias lookup, etc.),
    the resolvers tried within each phase, and the final provider:model result.

    Examples:

        vdm debug model-resolution sonnet

        vdm debug model-resolution openai:haiku --json
    """
    from src.core.dependencies import get_model_manager, initialize_app
    from src.core.model_resolution_trace import ResolutionTrace

    console = Console()

    if not model.strip():
        console.print("[red]Error: Model name cannot be empty.[/red]")
        raise typer.Exit(code=1)

    try:
        initialize_app()
    except RuntimeError as e:
        console.print(f"[red]Initialization failed:[/red] {e}")
        console.print("[dim]Set at least one PROVIDER_API_KEY environment variable.[/dim]")
        raise typer.Exit(code=1) from None

    try:
        model_manager = get_model_manager()
    except RuntimeError as e:
        console.print(f"[red]Model manager not available:[/red] {e}")
        raise typer.Exit(code=1) from None

    trace = ResolutionTrace(original_model=model)
    model_manager.resolve_model(model, trace=trace)

    if json_output:
        _print_json(trace)
    else:
        _print_text(trace, console)


def _print_text(trace: ResolutionTrace, console: Console) -> None:
    """Print trace as formatted text with Rich."""
    console.print(f"[bold]Resolving model:[/bold] {trace.original_model}")
    console.print()

    for phase in trace.phases:
        console.print(f"  [bold cyan]{phase.name}[/bold cyan]")
        console.print(f"    Input: {phase.input}")

        if phase.result == "matched":
            console.print(f"    [green]Matched[/green]: {phase.output}")
            for key, value in phase.details.items():
                if key not in ("resolver_steps",):
                    console.print(f"    {key}: {value}")
            steps = cast(list[dict[str, Any]] | None, phase.details.get("resolver_steps"))
            if steps:
                console.print("    Resolver chain:")
                for step in steps:
                    status = "[green]resolved[/green]" if step["was_resolved"] else "tried"
                    console.print(f"      {step['name']}: {status} -> {step['output_model']}")
        elif phase.result == "skipped":
            reason = phase.details.get("reason", "")
            console.print(f"    [dim]Skipped: {reason}[/dim]")
        elif phase.result == "no match":
            console.print(f"    [yellow]No match[/yellow]: {phase.output}")
            steps = cast(list[dict[str, Any]] | None, phase.details.get("resolver_steps"))
            if steps:
                console.print("    Resolver chain:")
                for step in steps:
                    console.print(f"      {step['name']}: tried -> {step['output_model']}")
        elif phase.result == "literal bypass":
            console.print(f"    [yellow]Literal bypass[/yellow]: {phase.output}")
        elif phase.result == "parsed":
            for key, value in phase.details.items():
                console.print(f"    {key}: {value}")
        else:
            console.print(f"    {phase.result}: {phase.output}")
            for key, value in phase.details.items():
                console.print(f"    {key}: {value}")

        console.print()

    if trace.final_provider or trace.final_model:
        console.print(f"  [bold]Result:[/bold] {trace.final_provider}:{trace.final_model}")


def _print_json(trace: ResolutionTrace) -> None:
    """Print trace as JSON.

    Serialises the full ResolutionTrace (phases, resolver steps, and final
    result) so it can be consumed programmatically or piped into jq.
    """
    data = {
        "original_model": trace.original_model,
        "phases": [
            {
                "name": phase.name,
                "input": phase.input,
                "result": phase.result,
                "output": phase.output,
                "details": phase.details,
            }
            for phase in trace.phases
        ],
        "final_provider": trace.final_provider,
        "final_model": trace.final_model,
    }
    print(json.dumps(data, indent=2))
