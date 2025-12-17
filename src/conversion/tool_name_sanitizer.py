import hashlib
import re
from collections.abc import Iterable

_TOOL_NAME_ALLOWED_RE = re.compile(r"[^A-Za-z0-9_]", re.UNICODE)
_TOOL_NAME_START_RE = re.compile(r"^[A-Za-z_]", re.UNICODE)


def sanitize_tool_name(name: str) -> str:
    """Return a provider-safe tool/function name.

    We intentionally keep the rules conservative to maximize compatibility across
    OpenAI-compatible providers.
    """

    stripped = name.strip()
    if not stripped:
        return "t_empty"

    # Replace disallowed chars with underscores.
    sanitized = _TOOL_NAME_ALLOWED_RE.sub("_", stripped)

    # Collapse repeated underscores.
    sanitized = re.sub(r"_+", "_", sanitized)

    # Ensure it starts with a letter/underscore.
    if not _TOOL_NAME_START_RE.match(sanitized):
        sanitized = f"t_{sanitized}"

    # Keep length reasonable; append hash to preserve uniqueness.
    max_len = 64
    if len(sanitized) > max_len:
        suffix = hashlib.sha256(stripped.encode("utf-8")).hexdigest()[:8]
        sanitized = f"{sanitized[: max_len - 9]}_{suffix}"

    return sanitized


def build_tool_name_maps(
    original_names: Iterable[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build forward and inverse maps, resolving collisions deterministically."""

    forward: dict[str, str] = {}
    inverse: dict[str, str] = {}

    # Preserve stable iteration order for deterministic collision suffixes.
    for original in original_names:
        if original in forward:
            continue

        base = sanitize_tool_name(original)
        candidate = base
        counter = 2
        while candidate in inverse and inverse[candidate] != original:
            candidate = f"{base}__{counter}"
            counter += 1

        forward[original] = candidate
        inverse[candidate] = original

    return forward, inverse
