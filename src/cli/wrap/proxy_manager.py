"""Proxy lifecycle management for vdm wrap."""

import asyncio
import logging
import os
import subprocess
import sys

import httpx

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manages the proxy server lifecycle for wrap commands."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8082):
        self.host = host
        self.port = port
        self._process: subprocess.Popen | None = None
        self._we_started_it = False

    async def ensure_proxy_running(self) -> bool:
        """Ensure proxy is running, start it if needed.

        Returns:
            True if we started the proxy, False if it was already running
        """
        if await self._is_proxy_running():
            logger.info(f"Proxy already running at {self.host}:{self.port}")
            self._we_started_it = False
            return False

        logger.info(f"Starting proxy at {self.host}:{self.port}")
        return await self._start_proxy()

    async def _is_proxy_running(self) -> bool:
        """Check if proxy is already running at the given host:port."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://{self.host}:{self.port}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def _start_proxy(self) -> bool:
        """Start the proxy server.

        The proxy is started with --systemd flag to:
        - Route logs to syslog instead of console
        - Suppress Rich table output (wrap has its own UI)
        - Keep subprocess output clean for the wrapper tool
        """
        # Use uv run to ensure we're in the right environment
        cmd = ["uv", "run", "vdm", "server", "start", "--host", self.host, "--port", str(self.port), "--systemd"]

        # Check if we're already in a uv environment
        if not os.environ.get("VIRTUAL_ENV") and not os.environ.get("UV_ACTIVE"):
            # If not in uv, try to use python directly
            cmd = [
                sys.executable,
                "-m",
                "src.cli.main",
                "server",
                "start",
                "--host",
                self.host,
                "--port",
                str(self.port),
                "--systemd",
            ]

        try:
            # Start the process
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            # Wait a bit and check if it started successfully
            for _ in range(10):  # Try for 5 seconds
                await asyncio.sleep(0.5)
                if await self._is_proxy_running():
                    self._we_started_it = True
                    logger.info(f"Proxy started successfully at {self.host}:{self.port}")
                    return True

                # Check if process exited with error
                if self._process.poll() is not None:
                    stdout, stderr = self._process.communicate()
                    logger.error(f"Proxy failed to start: {stderr}")
                    return False

            # If we get here, the proxy didn't become healthy
            logger.error("Proxy did not become healthy within 5 seconds")
            if self._process:
                self._process.terminate()
                self._process = None
            return False

        except Exception as e:
            logger.error(f"Failed to start proxy: {e}")
            return False

    async def cleanup_if_needed(self) -> None:
        """Clean up the proxy if we started it."""
        if self._we_started_it and self._process:
            logger.info("Stopping proxy that we started")
            try:
                self._process.terminate()
                # Give it a moment to terminate gracefully
                for _ in range(5):
                    if self._process.poll() is not None:
                        break
                    await asyncio.sleep(0.5)

                # Force kill if it didn't terminate
                if self._process.poll() is None:
                    logger.warning("Proxy didn't terminate gracefully, force killing")
                    self._process.kill()
                    self._process.wait()

            except Exception as e:
                logger.error(f"Error stopping proxy: {e}")
            finally:
                self._process = None
                self._we_started_it = False

    def get_proxy_url(self) -> str:
        """Get the proxy URL."""
        return f"http://{self.host}:{self.port}"
