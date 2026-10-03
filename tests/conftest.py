"""Pytest configuration for pushover-hermes-plugin tests."""
# noqa: E402 -- sys.path manipulation requires imports after setup
import sys
from pathlib import Path

_mock_dir = Path(__file__).parent / "mocks"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

import pytest
from gateway.platform_registry import platform_registry, PlatformEntry


@pytest.fixture(autouse=True)
def _register_pushover_platform():
    """Ensure pushover platform is registered in platform_registry before tests.

    Platform._missing_() checks platform_registry.is_registered() as a
    fallback when the value is not a built-in enum member.  Without this,
    Platform("pushover") raises ValueError in test context where the
    plugin's register() flow hasn't been executed.
    """
    if not platform_registry.is_registered("pushover"):
        platform_registry.register(PlatformEntry(
            name="pushover",
            label="Pushover",
            adapter_factory=lambda cfg: None,
            check_fn=lambda: True,
        ))
    yield
