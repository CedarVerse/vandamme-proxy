"""Duration helpers for metrics rollups."""

from __future__ import annotations


def finalize_average_duration(totals: dict[str, float | int]) -> None:
    """Compute `average_duration_ms` from `total_duration_ms`.

    We intentionally retain `total_duration_ms` so the dashboard can show both
    average and total duration.
    """

    requests = int(totals.get("requests", 0) or 0)
    total = float(totals.get("total_duration_ms", 0) or 0)
    if requests > 0:
        totals["average_duration_ms"] = int(round(total / requests))
    else:
        totals["average_duration_ms"] = 0
    totals["total_duration_ms"] = total


def finalize_split(split: dict[str, dict[str, float | int]]) -> None:
    for section in ("total", "streaming", "non_streaming"):
        finalize_average_duration(split[section])
