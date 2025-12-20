"""Top-models recommendation subsystem.

This package is responsible for fetching a curated list of recommended models
(from pluggable sources), caching it, and exposing it to API/CLI layers.

It is intentionally kept independent from the Claude/OpenAI request conversion
logic so that it can evolve without affecting the proxying pipeline.
"""
