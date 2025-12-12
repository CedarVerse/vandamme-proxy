"""Vandamme Proxy

A proxy server that converts Claude API requests to OpenAI-compatible API calls.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file
# Only load if not in test environment (tests manage their own environment)
if os.environ.get("PYTEST_CURRENT_TEST") is None:
    load_dotenv()

# Dynamic version from Git
try:
    from ._version import version as __version__  # type: ignore[import-untyped]
except ImportError:
    # Fallback for development installs
    try:
        from importlib.metadata import version

        __version__ = version("vandamme-proxy")
    except ImportError:
        __version__ = "1.0.0"
__author__ = "Vandamme Proxy"
