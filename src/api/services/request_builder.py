"""Request builder services for API endpoints.

This module provides utilities for building requests in different formats
for various providers.
"""

from typing import TYPE_CHECKING, Any

from src.models.claude import ClaudeMessagesRequest

if TYPE_CHECKING:
    from src.core.model_manager import ModelManager


def build_anthropic_passthrough_request(
    *,
    request: ClaudeMessagesRequest,
    provider_name: str,
    model_manager: "ModelManager",
) -> tuple[str, dict[str, Any]]:
    """Build request dict for Anthropic-format passthrough.

    For Anthropic-compatible providers (direct passthrough without format conversion),
    this builds the request dictionary with the resolved model name.

    Args:
        request: The Claude Messages API request.
        provider_name: Name of the provider (for model resolution).
        model_manager: The ModelManager instance for model resolution.

    Returns:
        A tuple of (resolved_model, claude_request_dict) where:
        - resolved_model: The model name without provider prefix
        - claude_request_dict: The request dict with _provider and model set
    """
    _, resolved_model = model_manager.resolve_model(request.model)
    claude_request_dict = request.model_dump(exclude_none=True)
    claude_request_dict["_provider"] = provider_name
    claude_request_dict["model"] = resolved_model
    return resolved_model, claude_request_dict
