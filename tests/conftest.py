"""
Pytest configuration for the test suite.
"""

import pytest

from src.llm_guard import ensure_llm_available, LLMAvailabilityError


def pytest_configure(config):
    """Register custom pytest marks."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests that require real API calls",
    )


def pytest_sessionstart(session):
    """Fail fast if Azure OpenAI is not reachable."""
    try:
        ensure_llm_available("Pytest suite")
    except LLMAvailabilityError as exc:
        pytest.exit(
            f"Azure OpenAI unavailable – cannot run tests.\n{exc}",
            returncode=1,
        )
