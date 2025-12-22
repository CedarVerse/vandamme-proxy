"""Elegant YAML formatting utilities for running totals responses."""

from datetime import datetime
from typing import Any

import yaml  # type: ignore


def format_running_totals_yaml(data: dict[str, Any], filters: dict[str, str] | None = None) -> str:
    """Format running totals data as pretty YAML with comments and metadata.

    Args:
        data: Hierarchical running totals data
        filters: Applied filters for documentation

    Returns:
        Formatted YAML string
    """
    # Create the YAML structure with metadata
    yaml_data = {
        "# Running Totals Report": None,
        f"# Generated: {datetime.now().isoformat()}Z": None,
    }

    # Add filter information if provided
    if filters:
        filter_parts = []
        if filters.get("provider"):
            filter_parts.append(f"provider={filters['provider']}")
        if filters.get("model"):
            filter_parts.append(f"model={filters['model']}")

        if filter_parts:
            yaml_data["# Filter: " + " & ".join(filter_parts)] = None

    # Add empty line for separation
    yaml_data["#"] = None

    # Add the actual data
    yaml_data.update(data)

    # Configure YAML for pretty output
    class PrettyYamlDumper(yaml.SafeDumper):
        """Custom YAML dumper for pretty formatting."""

        def write_line_break(self, data: Any = None) -> None:
            # Ensure blank lines between top-level sections
            super().write_line_break(data)
            if len(self.indents) == 1:
                super().write_line_break()

    # Format with 2-space indentation and pretty flow
    yaml_str = yaml.dump(
        yaml_data,
        Dumper=PrettyYamlDumper,
        default_flow_style=False,
        indent=2,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )

    # Clean up the output - remove null values for comments
    lines = []
    for line in yaml_str.split("\n"):
        # Skip lines that are just "null:" (from our comment structure)
        if line.strip() == "null:":
            continue
        # Clean up comment lines
        if line.strip().startswith("'#"):
            line = line.replace("'#", "#")
            if line.endswith(": null"):
                line = line[:-6]
            # Remove trailing single quote if present
            if line.endswith("'"):
                line = line[:-1]
        lines.append(line)

    return "\n".join(lines)


def create_hierarchical_structure(
    summary_data: dict[str, Any], provider_data: dict[str, Any]
) -> dict[str, Any]:
    """Create hierarchical YAML structure from summary and provider data.

    Args:
        summary_data: Overall summary statistics
        provider_data: Provider-specific data with models

    Returns:
        Hierarchical dictionary suitable for YAML formatting
    """
    structure = {
        "# Summary Statistics": None,
        "summary": {
            "last_accessed": summary_data.get("last_accessed"),
            "total_requests": summary_data.get("total_requests", 0),
            "total_errors": summary_data.get("total_errors", 0),
            "total_input_tokens": summary_data.get("total_input_tokens", 0),
            "total_output_tokens": summary_data.get("total_output_tokens", 0),
            "total_cache_read_tokens": summary_data.get("total_cache_read_tokens", 0),
            "total_cache_creation_tokens": summary_data.get("total_cache_creation_tokens", 0),
            "total_tool_uses": summary_data.get("total_tool_uses", 0),
            "total_tool_results": summary_data.get("total_tool_results", 0),
            "total_tool_calls": summary_data.get("total_tool_calls", 0),
            "active_requests": summary_data.get("active_requests", 0),
            "average_duration_ms": summary_data.get("average_duration_ms", 0),
            "total_duration_ms": summary_data.get("total_duration_ms", 0),
        },
        "#": None,  # Empty line separator
    }

    # Add provider breakdown
    if provider_data:
        structure["# Provider Breakdown"] = None
        providers_dict: dict[str, Any] = {}

        def format_totals(totals: dict[str, Any]) -> dict[str, Any]:
            # Keep stable key order; drop empty sections later.
            return {
                "requests": totals.get("requests", 0),
                "errors": totals.get("errors", 0),
                "input_tokens": totals.get("input_tokens", 0),
                "output_tokens": totals.get("output_tokens", 0),
                "cache_read_tokens": totals.get("cache_read_tokens", 0),
                "cache_creation_tokens": totals.get("cache_creation_tokens", 0),
                "tool_uses": totals.get("tool_uses", 0),
                "tool_results": totals.get("tool_results", 0),
                "tool_calls": totals.get("tool_calls", 0),
                "average_duration_ms": totals.get("average_duration_ms", 0),
                "total_duration_ms": totals.get("total_duration_ms", 0),
            }

        def format_split(split: dict[str, Any]) -> dict[str, Any]:
            out: dict[str, Any] = {"total": format_totals(split.get("total", {}))}
            streaming = split.get("streaming", {})
            non_streaming = split.get("non_streaming", {})
            if streaming.get("requests", 0) > 0:
                out["streaming"] = format_totals(streaming)
            if non_streaming.get("requests", 0) > 0:
                out["non_streaming"] = format_totals(non_streaming)
            return out

        for provider_name, provider_info in sorted(provider_data.items()):
            providers_dict[f"# {provider_name.title()} Provider"] = None

            provider_stats: dict[str, Any] = {
                "last_accessed": provider_info.get("last_accessed"),
                "rollup": format_split(provider_info.get("rollup", {})),
            }

            models = provider_info.get("models") or {}
            if models:
                models_dict: dict[str, Any] = {}
                for model_name, model_info in sorted(models.items()):
                    models_dict[model_name] = {
                        "last_accessed": model_info.get("last_accessed"),
                        **format_split(model_info),
                    }
                provider_stats["models"] = models_dict

            providers_dict[provider_name] = provider_stats

        structure["providers"] = providers_dict

    return structure


def format_health_yaml(data: dict[str, Any]) -> str:
    """Format health check data as pretty YAML with comments.

    Args:
        data: Health check response data

    Returns:
        Formatted YAML string
    """
    # Create the YAML structure with metadata
    yaml_data = {
        "# Health Check Report": None,
        f"# Generated: {datetime.now().isoformat()}Z": None,
    }

    # Add status-specific comment
    status = data.get("status", "unknown")
    if status == "healthy":
        yaml_data["# Status: All systems operational"] = None
    elif status == "degraded":
        yaml_data["# Status: System running with configuration issues"] = None

    # Add empty line for separation
    yaml_data["#"] = None

    # Add the actual data
    yaml_data.update(data)

    # Configure YAML for pretty output
    class PrettyYamlDumper(yaml.SafeDumper):
        """Custom YAML dumper for pretty formatting."""

        def write_line_break(self, data: Any = None) -> None:
            # Ensure blank lines between top-level sections
            super().write_line_break(data)
            if len(self.indents) == 1:
                super().write_line_break()

    # Format with 2-space indentation and pretty flow
    yaml_str = yaml.dump(
        yaml_data,
        Dumper=PrettyYamlDumper,
        default_flow_style=False,
        indent=2,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )

    # Clean up the output - remove null values for comments
    lines = []
    for line in yaml_str.split("\n"):
        # Skip lines that are just "null:" (from our comment structure)
        if line.strip() == "null:":
            continue
        # Clean up comment lines
        if line.strip().startswith("'#"):
            line = line.replace("'#", "#")
            if line.endswith(": null"):
                line = line[:-6]
            # Remove trailing single quote if present
            if line.endswith("'"):
                line = line[:-1]
        lines.append(line)

    return "\n".join(lines)
