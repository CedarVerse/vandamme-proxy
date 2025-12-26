"""Tests for the proxy manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.cli.wrap.proxy_manager import ProxyManager


@pytest_asyncio.fixture
async def proxy_manager():
    """Create a proxy manager instance."""
    return ProxyManager(host="127.0.0.1", port=8082)


@pytest.mark.asyncio
async def test_is_proxy_running_success():
    """Test successful proxy health check."""
    manager = ProxyManager()

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await manager._is_proxy_running()
        assert result is True


@pytest.mark.asyncio
async def test_is_proxy_running_failure():
    """Test failed proxy health check."""
    manager = ProxyManager()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get.side_effect = Exception(
            "Connection failed"
        )

        result = await manager._is_proxy_running()
        assert result is False


@pytest.mark.asyncio
async def test_ensure_proxy_running_already_running():
    """Test ensure_proxy_running when proxy is already running."""
    manager = ProxyManager()
    manager._is_proxy_running = AsyncMock(return_value=True)

    result = await manager.ensure_proxy_running()
    assert result is False
    assert manager._we_started_it is False


@pytest.mark.asyncio
async def test_ensure_proxy_running_starts_successfully():
    """Test ensure_proxy_running when proxy needs to be started."""
    manager = ProxyManager()

    # Mock _is_proxy_running to return False first, then True
    manager._is_proxy_running = AsyncMock(side_effect=[False, True])

    # Mock subprocess to simulate successful start
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process still running
        mock_popen.return_value = mock_process

        result = await manager.ensure_proxy_running()
        assert result is True
        assert manager._we_started_it is True


@pytest.mark.asyncio
async def test_start_proxy_success():
    """Test successful proxy startup."""
    manager = ProxyManager()

    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process still running
        mock_popen.return_value = mock_process

        # Mock the health check to succeed after starting
        manager._is_proxy_running = AsyncMock(side_effect=[False, True])

        result = await manager._start_proxy()
        assert result is True
        assert manager._process == mock_process
        assert manager._we_started_it is True


@pytest.mark.asyncio
async def test_start_proxy_failure():
    """Test proxy startup failure."""
    manager = ProxyManager()

    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process exited immediately
        mock_process.communicate.return_value = ("", "Error message")
        mock_popen.return_value = mock_process

        # Mock _is_proxy_running to return False
        with patch.object(manager, "_is_proxy_running", return_value=False):
            result = await manager._start_proxy()
            assert result is False
            # _process is NOT None in immediate failure case - only set to None
            # after timeout or in exception handler
            assert manager._process is mock_process


@pytest.mark.asyncio
async def test_cleanup_if_needed_started_by_us():
    """Test cleanup when we started the proxy."""
    manager = ProxyManager()
    manager._we_started_it = True

    mock_process = MagicMock()
    manager._process = mock_process

    await manager.cleanup_if_needed()

    mock_process.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_if_needed_not_started_by_us():
    """Test cleanup when we didn't start the proxy."""
    manager = ProxyManager()
    manager._we_started_it = False
    manager._process = None

    await manager.cleanup_if_needed()

    # Should not attempt to terminate anything
    assert manager._process is None


def test_get_proxy_url():
    """Test getting proxy URL."""
    manager = ProxyManager(host="localhost", port=9999)
    assert manager.get_proxy_url() == "http://localhost:9999"


@pytest.mark.asyncio
@patch("src.cli.wrap.proxy_manager.subprocess.Popen")
async def test_start_proxy_includes_systemd_flag(mock_popen):
    """Test that _start_proxy passes --systemd flag to subprocess."""
    manager = ProxyManager(host="127.0.0.1", port=8082)

    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Process still running
    mock_popen.return_value = mock_process

    # Mock the health check to succeed after starting
    manager._is_proxy_running = AsyncMock(side_effect=[False, True])

    await manager._start_proxy()

    # Verify subprocess.Popen was called
    assert mock_popen.called
    call_args = mock_popen.call_args

    # Get the command from the call
    cmd = call_args[0][0]

    # Verify --systemd flag is present
    assert "--systemd" in cmd, f"Expected --systemd flag in command: {cmd}"
