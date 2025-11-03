"""
End-to-end integration tests for the CLI.
"""

import pytest
import json
from src.cli import FinancialCLI


@pytest.fixture
def cli():
    """Create a CLI instance for testing."""
    cli_instance = FinancialCLI()
    yield cli_instance
    cli_instance.close()


def test_cli_sector_count_question(cli):
    """Test CLI with sector count question."""
    question = "How many companies are in the Information Technology sector?"
    response = cli.process_question(question, debug_mode=False)

    assert response.success is True
    assert len(response.answer) > 0
    assert response.confidence > 0.5
    assert "metadata" in response.to_dict()


def test_cli_company_cik_question(cli):
    """Test CLI with company CIK lookup question."""
    question = "What is Apple's CIK?"
    response = cli.process_question(question, debug_mode=False)

    assert response.success is True
    # CIK should be in the answer
    assert "CIK" in response.answer or "cik" in response.answer.lower()
    assert response.confidence > 0.5


def test_cli_company_sector_question(cli):
    """Test CLI with company sector lookup question."""
    question = "What sector is Microsoft in?"
    response = cli.process_question(question, debug_mode=False)

    assert response.success is True
    assert "sector" in response.answer.lower()
    assert response.confidence > 0.5


def test_cli_debug_mode(cli):
    """Test CLI debug mode returns additional information."""
    question = "How many companies in Healthcare sector?"
    response = cli.process_question(question, debug_mode=True)

    assert response.success is True
    assert response.debug_info is not None
    assert "entities" in response.debug_info
    assert "sql_executed" in response.debug_info
    assert "component_timings" in response.debug_info


def test_cli_error_handling(cli):
    """Test CLI error handling for invalid questions."""
    question = "This is a completely invalid question with no clear intent"
    response = cli.process_question(question, debug_mode=False)

    # Should handle gracefully, not crash
    assert response is not None
    # Might succeed with low confidence or fail gracefully
    assert isinstance(response.success, bool)


def test_cli_json_output_format(cli):
    """Test that CLI response can be serialized to JSON."""
    question = "How many companies in Energy sector?"
    response = cli.process_question(question, debug_mode=True)

    # Convert to dict
    response_dict = response.to_dict()

    # Should be JSON-serializable
    json_str = json.dumps(response_dict)
    assert len(json_str) > 0

    # Check key fields
    parsed = json.loads(json_str)
    assert "answer" in parsed
    assert "success" in parsed
    assert "confidence" in parsed
    assert "metadata" in parsed
