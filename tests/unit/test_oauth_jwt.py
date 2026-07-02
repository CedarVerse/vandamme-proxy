import base64
import json

import pytest

from src.core.oauth.jwt import extract_account_id


def _encode_segment(payload: dict[str, str | dict[str, str]]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _jwt_with_claims(claims: dict[str, str | dict[str, str]]) -> str:
    header = _encode_segment({"alg": "none"})
    payload = _encode_segment(claims)
    return f"{header}.{payload}.signature"


@pytest.mark.unit
def test_extract_account_id_prefers_chatgpt_account_id_over_user_id():
    token = _jwt_with_claims(
        {
            "https://api.openai.com/auth": {
    "chatgpt_account_id": "00000000-0000-4000-8000-000000000000",
    "user_id": "user-testFixtureOnly000000000000000",
            },
            "sub": "auth0|fallback",
        }
    )

    assert extract_account_id(token) == "00000000-0000-4000-8000-000000000000"
