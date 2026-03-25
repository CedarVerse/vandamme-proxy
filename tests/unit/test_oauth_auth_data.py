"""Unit tests for AuthData storage dataclass.

Key learnings:
- `from datetime import datetime` imports the *class*, not the module.
  `datetime.timezone` does not exist on the class — only `datetime.timezone`
  as accessed through the *module* does.  The fix: also import `timezone`
  directly so `datetime.now(timezone.utc)` is unambiguous.
- When `last_refresh` is None, `to_dict()` falls back to "now". This test
  guards against regressions on that code path.
"""

from datetime import datetime, timezone

import pytest

from src.core.oauth.storage import AuthData


def _make_auth_data(**overrides) -> AuthData:
    """Factory for minimal valid AuthData (reduces boilerplate).

    Token values must be at least 20 characters long (ValidationLimits.MIN_TOKEN_LENGTH).
    """
    defaults = {
        "access_token": "access-token-value-abcdef1234",
        "refresh_token": "refresh-token-value-abcdef1234",
        "id_token": "id-token-value-abcdef1234-xyz",
        "account_id": "user-123",
    }
    defaults.update(overrides)
    return AuthData(**defaults)


@pytest.mark.unit
class TestAuthDataToDict:
    """Tests for AuthData.to_dict() serialization."""

    def test_to_dict_with_last_refresh_none_does_not_raise(self):
        """Regression guard: to_dict() must not raise when last_refresh is None.

        Before the fix, datetime.now(datetime.timezone.utc) would raise
        AttributeError because `datetime` (the class) has no `.timezone`
        attribute — only the `datetime` *module* does.
        """
        auth = _make_auth_data(last_refresh=None)
        # Must not raise AttributeError
        result = auth.to_dict()
        assert "last_refresh" in result

    def test_to_dict_last_refresh_none_returns_iso_timestamp(self):
        """When last_refresh is None, to_dict() substitutes the current UTC time."""
        before = datetime.now(timezone.utc)
        auth = _make_auth_data(last_refresh=None)
        result = auth.to_dict()
        after = datetime.now(timezone.utc)

        last_refresh_str = result["last_refresh"]
        assert isinstance(last_refresh_str, str), "last_refresh must be an ISO string"

        # Parse the returned value and verify it's a real, plausible timestamp.
        # fromisoformat() accepts the UTC offset suffix produced by .isoformat().
        ts = datetime.fromisoformat(last_refresh_str)
        # Make ts timezone-aware for comparison (it carries +00:00 from isoformat)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        assert before <= ts <= after, (
            f"Fallback timestamp {ts!r} should be between {before!r} and {after!r}"
        )

    def test_to_dict_with_explicit_last_refresh_is_preserved(self):
        """When last_refresh is set, to_dict() returns it unchanged."""
        ts = "2025-06-01T12:00:00+00:00"
        auth = _make_auth_data(last_refresh=ts)
        result = auth.to_dict()
        assert result["last_refresh"] == ts

    def test_to_dict_includes_all_required_fields(self):
        """to_dict() output must include every field required for round-trip."""
        auth = _make_auth_data()
        result = auth.to_dict()
        required_keys = {"access_token", "refresh_token", "id_token", "account_id", "last_refresh"}
        assert required_keys.issubset(result.keys())

    def test_to_dict_round_trips_via_from_dict(self):
        """A dict produced by to_dict() must be parseable by from_dict()."""
        original = _make_auth_data(expires_at="2025-12-31T23:59:59+00:00")
        serialized = original.to_dict()
        restored = AuthData.from_dict(serialized)

        assert restored.access_token == original.access_token
        assert restored.refresh_token == original.refresh_token
        assert restored.id_token == original.id_token
        assert restored.account_id == original.account_id
