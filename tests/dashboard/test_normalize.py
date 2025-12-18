from __future__ import annotations

from src.dashboard.normalize import (
    detect_metrics_disabled,
    error_rate,
    parse_metric_totals,
    provider_rows,
)


def test_error_rate_zero_when_no_requests() -> None:
    assert error_rate(total_requests=0, total_errors=10) == 0.0


def test_detect_metrics_disabled() -> None:
    assert detect_metrics_disabled({"# Message": "Request metrics logging is disabled"})


def test_parse_metric_totals_disabled_returns_zeros() -> None:
    totals = parse_metric_totals({"# Message": "Request metrics logging is disabled"})
    assert totals.total_requests == 0
    assert totals.total_errors == 0


def test_provider_rows_basic_shape() -> None:
    rows = provider_rows(
        {
            "total_requests": 10,
            "providers": {
                "openai": {
                    "total_requests": 7,
                    "total_errors": 1,
                    "total_input_tokens": 100,
                    "total_output_tokens": 200,
                    "models": {},
                },
                "anthropic": {
                    "total_requests": 3,
                    "total_errors": 0,
                    "total_input_tokens": 30,
                    "total_output_tokens": 40,
                    "models": {},
                },
            },
        }
    )

    assert {r["provider"] for r in rows} == {"openai", "anthropic"}
    openai = next(r for r in rows if r["provider"] == "openai")
    assert openai["requests"] == 7
    assert openai["errors"] == 1
