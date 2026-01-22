"""Integration tests for profile reload functionality."""

import asyncio
import os

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get test port from environment or use default (matching development server)
TEST_PORT = int(os.environ.get("VDM_TEST_PORT", "8082"))


@pytest.mark.integration
async def test_reload_through_dependencies_module():
    """Test reload through dependencies.reload_profiles()."""
    from src.core.dependencies import initialize_app, reload_profiles

    # Initialize dependencies first
    initialize_app()

    # Get initial profile count
    from src.core.dependencies import get_profile_manager

    initial_profiles = get_profile_manager().list_profiles()

    # Reload should work without errors
    await reload_profiles()

    # Verify profiles were reloaded
    reloaded_profiles = get_profile_manager().list_profiles()
    # The profiles should be the same after reload (no config change)
    assert set(initial_profiles) == set(reloaded_profiles)


@pytest.mark.integration
def test_strict_validation_failure():
    """Test that strict validation raises RuntimeError."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from src.core import dependencies

    # Reset dependencies to test fresh initialization
    dependencies._config = None
    dependencies._profile_manager = None
    dependencies._provider_manager = None
    dependencies._alias_manager = None
    dependencies._model_manager = None
    dependencies._alias_service = None

    # Create a temporary config file with an invalid profile
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "vandamme-config.toml"
        config_path.write_text(
            """
[defaults]
timeout = 90
max-retries = 2

["#invalid"]
aliases = { "haiku" = "nonexistent:model" }
"""
        )

        # Patch AliasConfigLoader to use our temp config
        from src.core import alias_config

        original_load = alias_config.AliasConfigLoader.load_config

        def mock_load(self, force_reload=False):
            if force_reload or not hasattr(self, "_test_config"):
                import tomllib

                with open(config_path, "rb") as f:
                    raw_config = tomllib.load(f)
                # Process the raw config to match AliasConfigLoader.load_config() output
                self._test_config = {"providers": {}, "profiles": {}, "defaults": {}}
                for key, value in raw_config.items():
                    if key == "defaults":
                        self._test_config["defaults"] = value
                    elif key.startswith("#"):
                        # Profile section
                        profile_name = key[1:]  # Strip # for storage
                        self._test_config["profiles"][profile_name] = {
                            "source": "local",
                            "timeout": value.get("timeout"),
                            "max-retries": value.get("max-retries"),
                            "aliases": value.get("aliases", {}),
                        }
                    else:
                        # Provider section
                        self._test_config["providers"][key.lower()] = value
            return self._test_config

        try:
            with patch.object(alias_config.AliasConfigLoader, "load_config", mock_load):
                # Set strict validation via environment variable
                original_strict = os.environ.get("VDM_STRICT_PROFILE_VALIDATION")
                os.environ["VDM_STRICT_PROFILE_VALIDATION"] = "true"
                try:
                    dependencies.initialize_app()
                    pytest.fail("Should have raised RuntimeError")
                except RuntimeError as e:
                    assert "Profile validation failed" in str(e)
                finally:
                    # Restore original environment variable
                    if original_strict is None:
                        os.environ.pop("VDM_STRICT_PROFILE_VALIDATION", None)
                    else:
                        os.environ["VDM_STRICT_PROFILE_VALIDATION"] = original_strict
        finally:
            # Restore original load function
            alias_config.AliasConfigLoader.load_config = original_load


@pytest.mark.integration
def test_lenient_validation_warning():
    """Test that lenient validation logs warning but continues."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from src.core import dependencies

    # Reset dependencies to test fresh initialization
    dependencies._config = None
    dependencies._profile_manager = None
    dependencies._provider_manager = None
    dependencies._alias_manager = None
    dependencies._model_manager = None
    dependencies._alias_service = None

    # Create a temporary config file with an invalid profile
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "vandamme-config.toml"
        config_path.write_text(
            """
[defaults]
timeout = 90
max-retries = 2

["#invalid"]
aliases = { "haiku" = "nonexistent:model" }
"""
        )

        # Patch AliasConfigLoader to use our temp config
        from src.core import alias_config

        original_load = alias_config.AliasConfigLoader.load_config

        def mock_load(self, force_reload=False):
            if force_reload or not hasattr(self, "_test_config"):
                import tomllib

                with open(config_path, "rb") as f:
                    raw_config = tomllib.load(f)
                # Process the raw config to match AliasConfigLoader.load_config() output
                self._test_config = {"providers": {}, "profiles": {}, "defaults": {}}
                for key, value in raw_config.items():
                    if key == "defaults":
                        self._test_config["defaults"] = value
                    elif key.startswith("#"):
                        # Profile section
                        profile_name = key[1:]  # Strip # for storage
                        self._test_config["profiles"][profile_name] = {
                            "source": "local",
                            "timeout": value.get("timeout"),
                            "max-retries": value.get("max-retries"),
                            "aliases": value.get("aliases", {}),
                        }
                    else:
                        # Provider section
                        self._test_config["providers"][key.lower()] = value
            return self._test_config

        try:
            with patch.object(alias_config.AliasConfigLoader, "load_config", mock_load):
                # Set lenient validation via environment variable (must be explicitly false)
                original_strict = os.environ.get("VDM_STRICT_PROFILE_VALIDATION")
                os.environ["VDM_STRICT_PROFILE_VALIDATION"] = "false"

                try:
                    # Should not raise, just log warnings
                    dependencies.initialize_app()
                    # Verify dependencies were initialized despite validation errors
                    assert dependencies._config is not None
                    assert dependencies._profile_manager is not None
                finally:
                    # Restore original environment variable
                    if original_strict is None:
                        os.environ.pop("VDM_STRICT_PROFILE_VALIDATION", None)
                    else:
                        os.environ["VDM_STRICT_PROFILE_VALIDATION"] = original_strict
        finally:
            # Restore original load function
            alias_config.AliasConfigLoader.load_config = original_load


@pytest.mark.integration
async def test_concurrent_reload_safe():
    """Verify concurrent reloads don't cause race conditions.

    This test ensures that multiple concurrent reload_profiles() calls
    are properly serialized by the asyncio lock and don't cause
    race conditions or corruption.
    """
    from src.core.dependencies import get_profile_manager, initialize_app, reload_profiles

    initialize_app()

    # Simulate concurrent reloads
    tasks = [reload_profiles() for _ in range(10)]
    await asyncio.gather(*tasks)

    # Verify profile manager is still functional
    pm = get_profile_manager()
    assert pm is not None
    assert pm.list_profiles() is not None
    # Should have at least the default profiles
    assert len(pm.list_profiles()) > 0


@pytest.mark.integration
async def test_reload_during_concurrent_access():
    """Verify reload is safe while profiles are being accessed.

    This test simulates the scenario where profiles are being read
    while a reload is in progress.
    """
    from src.core.dependencies import get_profile_manager, initialize_app, reload_profiles

    initialize_app()
    pm = get_profile_manager()

    async def access_profiles():
        """Simulate reading profiles during reload."""
        for _ in range(50):
            profiles = pm.list_profiles()
            assert profiles is not None
            # Try to get each profile
            for name in profiles:
                profile = pm.get_profile(name)
                # Profile should either exist or be None during reload
                assert profile is None or profile.name == name.lower()
            await asyncio.sleep(0.001)

    async def do_reloads():
        """Simulate reloads during access."""
        for _ in range(5):
            await reload_profiles()
            await asyncio.sleep(0.01)

    # Run access and reloads concurrently
    await asyncio.gather(access_profiles(), do_reloads())

    # Verify final state is consistent
    assert len(pm.list_profiles()) > 0
