"""Safe operation primitives for Vandamme Proxy.

This module provides utilities for handling operations that may fail
in non-critical ways, replacing bare except clauses with specific,
logged exception handling.

Philosophy:
- Be specific about exceptions you catch
- Always log before falling back
- Maintain existing behavior
- Make debugging possible
"""

from .context import (
    soft_fail,
    suppress_and_log,
)
from .decorators import (
    log_and_reraise,
    log_and_return_default,
)
from .parsers import (
    JSON_PARSE_EXCEPTIONS,
    safe_json_loads,
)

__all__ = [
    "safe_json_loads",
    "JSON_PARSE_EXCEPTIONS",
    "log_and_return_default",
    "log_and_reraise",
    "suppress_and_log",
    "soft_fail",
]
