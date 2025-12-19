"""Tests for the tool wrappers."""

from unittest.mock import MagicMock, patch

from src.cli.wrap.wrappers import ClaudeWrapper, GeminiWrapper, get_wrapper


def test_claude_wrapper_command():
    """Test Claude wrapper command."""
    wrapper = ClaudeWrapper("http://127.0.0.1:8082")
    assert wrapper.get_tool_command() == ["claude"]


def test_claude_wrapper_environment():
    """Test Claude wrapper environment setup."""
    wrapper = ClaudeWrapper("http://127.0.0.1:8082")
    env = wrapper.prepare_environment([])

    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8082"
    assert env["ANTHROPIC_API_KEY"] == "proxy-auth-required"
    # Should preserve other environment variables
    assert "PATH" in env


def test_claude_wrapper_settings_file():
    """Test Claude wrapper settings file creation."""
    wrapper = ClaudeWrapper("http://127.0.0.1:8082")

    settings_file = wrapper.create_settings_file()

    # Should return None to avoid creating temporary files that cause conflicts
    assert settings_file is None


def test_claude_wrapper_filter_args():
    """Test Claude wrapper argument filtering."""
    wrapper = ClaudeWrapper("http://127.0.0.1:8082")

    # Should pass through all arguments (base wrapper doesn't filter)
    args = ["--model", "sonnet", "--help"]
    filtered = wrapper.filter_args(args)

    assert filtered == args


def test_gemini_wrapper_command():
    """Test Gemini wrapper command."""
    wrapper = GeminiWrapper("http://127.0.0.1:8082")
    assert wrapper.get_tool_command() == ["gemini"]


def test_gemini_wrapper_environment():
    """Test Gemini wrapper environment setup."""
    wrapper = GeminiWrapper("http://127.0.0.1:8082")
    env = wrapper.prepare_environment([])

    assert env["GEMINI_API_BASE_URL"] == "http://127.0.0.1:8082"


def test_gemini_wrapper_no_settings():
    """Test Gemini wrapper doesn't create settings file."""
    wrapper = GeminiWrapper("http://127.0.0.1:8082")

    settings_file = wrapper.create_settings_file()

    assert settings_file is None


def test_get_wrapper_claude():
    """Test getting Claude wrapper."""
    wrapper = get_wrapper("claude", "http://127.0.0.1:8082")
    assert isinstance(wrapper, ClaudeWrapper)


def test_get_wrapper_gemini():
    """Test getting Gemini wrapper."""
    wrapper = get_wrapper("gemini", "http://127.0.0.1:8082")
    assert isinstance(wrapper, GeminiWrapper)


def test_get_wrapper_case_insensitive():
    """Test that wrapper lookup is case insensitive."""
    wrapper = get_wrapper("CLAUDE", "http://127.0.0.1:8082")
    assert isinstance(wrapper, ClaudeWrapper)


def test_get_wrapper_unknown():
    """Test getting wrapper for unknown tool."""
    wrapper = get_wrapper("unknown", "http://127.0.0.1:8082")
    assert wrapper is None


@patch("subprocess.Popen")
def test_claude_wrapper_run(mock_popen):
    """Test running Claude wrapper."""
    # Mock subprocess
    mock_process = MagicMock()
    mock_process.wait.return_value = 0  # Return value for wait()
    mock_popen.return_value = mock_process

    wrapper = ClaudeWrapper("http://127.0.0.1:8082")

    # Mock signal to avoid actually setting signal handlers
    with patch("signal.signal"):
        result = wrapper.run(["--help"])

    assert result == 0
    mock_popen.assert_called_once()

    # Check that the command does NOT include --settings (since we removed it)
    call_args = mock_popen.call_args[0][0]
    assert call_args[0] == "claude"
    assert "--help" in call_args
    assert "--settings" not in call_args


@patch("subprocess.Popen")
def test_wrapper_signal_handling(mock_popen):
    """Test that wrapper forwards signals to child process."""
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Process still running
    mock_process.send_signal = MagicMock()
    mock_popen.return_value = mock_process

    wrapper = ClaudeWrapper("http://127.0.0.1:8082")

    with patch("signal.signal") as mock_signal:
        # Don't actually run the process, just test signal handler setup
        wrapper.run([])

        # Check that signal handlers were set
        assert mock_signal.call_count >= 2  # Should set SIGINT and SIGTERM
