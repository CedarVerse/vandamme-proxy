import pytest

from src.conversion.errors import SSEParseError
from src.conversion.openai_stream_to_claude_state_machine import parse_openai_sse_line


@pytest.mark.unit
def test_parse_openai_sse_line_raises_sse_parse_error_on_invalid_json() -> None:
    with pytest.raises(SSEParseError) as exc:
        parse_openai_sse_line('data: {"choices": [}\n')

    err = exc.value
    assert err.error_type == "sse_parse_error"
    assert "Failed to parse OpenAI streaming chunk as JSON" in err.message
    assert err.context is not None
    assert "chunk_data" in err.context
