"""Bridge subprocess lifecycle management for vdm server start.

Manages the agent-cli-to-api bridge process alongside the proxy server.
Follows the same Popen/health-check/cleanup pattern as ProxyManager.
"""

import logging
import os
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

logger = logging.getLogger(__name__)

# Known bridge providers and their agent-cli-to-api positional argument names.
BRIDGE_PROVIDERS = {
    "cursor": "cursor-agent",
    "codex": "codex",
    "gemini": "gemini",
    "claude": "claude",
}

# Default ports when not resolved from TOML config.
DEFAULT_BRIDGE_PORTS = {
    "cursor": 8766,
    "codex": 8767,
    "gemini": 8768,
    "claude": 8769,
}

# Sentinel API key value that triggers provider auto-discovery.
BRIDGE_API_KEY = "bridge"

# How long to wait for the bridge to become healthy (seconds).
HEALTH_CHECK_TIMEOUT = 10
HEALTH_CHECK_INTERVAL = 0.5


class BridgeManager:
    """Manages an agent-cli-to-api bridge subprocess lifecycle."""

    def __init__(self, provider: str, host: str = "127.0.0.1", port: int | None = None):
        if provider not in BRIDGE_PROVIDERS:
            raise ValueError(
                f"Unknown bridge provider '{provider}'. Supported: {', '.join(BRIDGE_PROVIDERS)}"
            )
        self.provider = provider
        self.bridge_arg = BRIDGE_PROVIDERS[provider]
        self.host = host
        self.port = port or DEFAULT_BRIDGE_PORTS[provider]
        self._process: subprocess.Popen | None = None
        self._we_started_it = False

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> bool:
        """Start the bridge subprocess and wait for readiness.

        Returns True if the bridge is healthy (started by us or already running).
        """
        if self._is_healthy():
            logger.info(f"Bridge already running at {self.base_url}")
            self._we_started_it = False
            return True

        env_key = f"{self.provider.upper()}_API_KEY"
        logger.info(
            f"Starting {self.bridge_arg} bridge on {self.host}:{self.port} "
            f"(setting {env_key}={BRIDGE_API_KEY})"
        )

        cmd = [
            "agent-cli-to-api",
            self.bridge_arg,
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--log-level",
            "warning",
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            logger.error(
                "agent-cli-to-api not found. Install with: "
                "uv tool install git+https://github.com/leeguooooo/agent-cli-to-api"
            )
            return False

        # Wait for bridge to become healthy
        deadline = time.monotonic() + HEALTH_CHECK_TIMEOUT
        while time.monotonic() < deadline:
            # Check if process died
            if self._process.poll() is not None:
                _, stderr = self._process.communicate()
                logger.error(
                    f"Bridge exited with code {self._process.returncode}: "
                    f"{stderr.decode(errors='replace')[:500]}"
                )
                self._process = None
                return False

            if self._is_healthy():
                self._we_started_it = True
                # Set the env var so the proxy discovers the provider
                os.environ[env_key] = BRIDGE_API_KEY
                logger.info(f"Bridge ready at {self.base_url}")
                return True

            time.sleep(HEALTH_CHECK_INTERVAL)

        # Timeout — bridge never became healthy
        logger.error(f"Bridge did not become healthy within {HEALTH_CHECK_TIMEOUT}s")
        if self._process:
            self._process.terminate()
            self._process = None
        return False

    def cleanup(self) -> None:
        """Stop the bridge subprocess if we started it."""
        if not self._we_started_it or not self._process:
            return

        logger.info(f"Stopping bridge (PID {self._process.pid})")
        try:
            self._process.terminate()
            # Grace period
            try:
                self._process.wait(timeout=2.5)
            except subprocess.TimeoutExpired:
                logger.warning("Bridge didn't terminate gracefully, force killing")
                self._process.kill()
                self._process.wait()
        except Exception as e:
            logger.error(f"Error stopping bridge: {e}")
        finally:
            self._process = None
            self._we_started_it = False

    def _is_healthy(self) -> bool:
        """Check if the bridge is responding on its port."""
        try:
            resp = urlopen(f"{self.base_url}/v1/models", timeout=2)
            return bool(resp.status == 200)
        except (URLError, OSError):
            return False
