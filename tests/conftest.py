"""
Pytest configuration for the test suite.
"""
import pytest


def pytest_configure(config):
    """Register custom pytest marks."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests that require real API calls"
    )

