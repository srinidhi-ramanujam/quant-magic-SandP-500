"""
Unit and Integration Tests for LLM-Assisted Entity Extraction (Stage 1)

Tests the EntityExtractor with LLM integration using:
- Mock LLM responses for deterministic unit testing
- Real Azure OpenAI API for integration testing
- Various question types and edge cases
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.entity_extractor import EntityExtractor
from src.models import ExtractedEntities, LLMAnalysisResponse, QueryComplexity
from src.telemetry import RequestContext


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def create_mock_openai_response(entity_dict: dict) -> Mock:
    """
    Create a properly structured mock OpenAI API response.

    Args:
        entity_dict: Dictionary with companies, metrics, sectors, etc.

    Returns:
        Mock object with proper response structure
    """
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    mock_message.content = json.dumps(entity_dict)
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = Mock()
    mock_usage.prompt_tokens = 120
    mock_usage.completion_tokens = 36
    mock_response.usage = mock_usage
    return mock_response


def assert_contains_case_insensitive(sequence, target, label="sequence"):
    """Assert helper that ignores casing when looking for an item in a list."""
    target_lower = target.lower()
    assert any(
        (item or "").lower() == target_lower for item in sequence
    ), f"Expected '{target}' in {label}, got {sequence}"


# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def mock_azure_client():
    """Mock Azure OpenAI client for deterministic testing."""
    with patch("src.entity_extractor.AzureOpenAIClient") as mock_client_class:
        mock_client = Mock()

        # Mock the is_available method
        mock_client.is_available.return_value = True

        # Mock the config
        mock_config = Mock()
        mock_config.deployment_name = "gpt-4"
        mock_client.config = mock_config

        # Mock the client.chat.completions.create method with proper structure
        mock_openai_client = Mock()
        mock_client.client = mock_openai_client

        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def request_context():
    """Create a request context for telemetry."""
    context = RequestContext(request_id="test-123", question="test question")
    context.llm_calls = []
    return context


@pytest.fixture
def entity_extractor(mock_azure_client):
    """Create EntityExtractor instance with mocked Azure client."""
    extractor = EntityExtractor(use_llm=True)
    return extractor


# ==============================================================================
# UNIT TESTS: Simple Questions
# ==============================================================================


def test_extract_simple_company_question(
    entity_extractor, mock_azure_client, request_context
):
    """Test extracting entities from 'What is Apple's CIK?'"""
    question = "What is Apple's CIK?"

    # Mock OpenAI API response
    mock_response = create_mock_openai_response(
        {
            "companies": ["APPLE INC"],
            "metrics": ["cik"],
            "sectors": [],
            "time_periods": [],
            "question_type": "lookup",
            "confidence": 0.95,
            "reasoning": "Clear company name (Apple → APPLE INC) and specific metric (CIK) requested.",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    # Extract entities
    entities = entity_extractor.extract(question, request_context)

    # Assertions
    assert isinstance(entities, ExtractedEntities)
    assert "APPLE INC" in entities.companies
    assert_contains_case_insensitive(entities.metrics, "cik", "metrics")
    assert len(entities.sectors) == 0
    assert entities.question_type == "lookup"
    assert entities.confidence >= 0.9

    # Verify LLM was called
    assert mock_azure_client.client.chat.completions.create.called


def test_extract_ambiguous_company_ticker(
    entity_extractor, mock_azure_client, request_context
):
    """Test extracting entities from 'What's AAPL's revenue?'"""
    question = "What's AAPL's revenue?"

    mock_response = create_mock_openai_response(
        {
            "companies": ["APPLE INC"],
            "metrics": ["revenue"],
            "sectors": [],
            "time_periods": ["latest"],
            "question_type": "lookup",
            "confidence": 0.9,
            "reasoning": "Ticker AAPL converted to APPLE INC. 'Latest' period implied.",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    entities = entity_extractor.extract(question, request_context)

    assert "APPLE INC" in entities.companies
    assert_contains_case_insensitive(entities.metrics, "revenue", "metrics")
    assert_contains_case_insensitive(entities.time_periods, "latest", "time_periods")
    assert entities.question_type == "lookup"


def test_extract_multiple_entities(
    entity_extractor, mock_azure_client, request_context
):
    """Test extracting entities from 'Compare Apple and Microsoft revenue'"""
    question = "Compare Apple and Microsoft's revenue"

    mock_response = create_mock_openai_response(
        {
            "companies": ["APPLE INC", "MICROSOFT CORP"],
            "metrics": ["revenue"],
            "sectors": [],
            "time_periods": ["latest"],
            "question_type": "comparison",
            "confidence": 0.92,
            "reasoning": "Comparison question with two companies. Both converted to official names.",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    entities = entity_extractor.extract(question, request_context)

    assert len(entities.companies) == 2
    assert "APPLE INC" in entities.companies
    assert "MICROSOFT CORP" in entities.companies
    assert_contains_case_insensitive(entities.metrics, "revenue", "metrics")
    assert entities.question_type == "comparison"


def test_extract_metric_synonyms(entity_extractor, mock_azure_client, request_context):
    """Test extracting entities from 'What's MSFT's sales?' (sales → revenue)"""
    question = "What's MSFT's sales?"

    mock_response = create_mock_openai_response(
        {
            "companies": ["MICROSOFT CORP"],
            "metrics": ["revenue"],
            "sectors": [],
            "time_periods": ["latest"],
            "question_type": "lookup",
            "confidence": 0.88,
            "reasoning": "Ticker MSFT → MICROSOFT CORP. 'Sales' synonym mapped to 'revenue'.",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    entities = entity_extractor.extract(question, request_context)

    assert "MICROSOFT CORP" in entities.companies
    assert_contains_case_insensitive(
        entities.metrics, "revenue", "metrics"
    )  # sales normalized to revenue
    assert entities.question_type == "lookup"


def test_extract_time_period_explicit(
    entity_extractor, mock_azure_client, request_context
):
    """Test extracting entities from 'Apple revenue in Q3 2024'"""
    question = "Apple revenue in Q3 2024"

    mock_response = create_mock_openai_response(
        {
            "companies": ["APPLE INC"],
            "metrics": ["revenue"],
            "sectors": [],
            "time_periods": ["Q3", "2024"],
            "question_type": "lookup",
            "confidence": 0.95,
            "reasoning": "Clear time period specification: Q3 2024.",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    entities = entity_extractor.extract(question, request_context)

    assert "APPLE INC" in entities.companies
    assert_contains_case_insensitive(entities.metrics, "revenue", "metrics")
    assert_contains_case_insensitive(entities.time_periods, "Q3", "time_periods")
    assert_contains_case_insensitive(entities.time_periods, "2024", "time_periods")


def test_extract_implicit_time_period(
    entity_extractor, mock_azure_client, request_context
):
    """Test extracting entities from 'Apple's latest revenue'"""
    question = "Apple's latest revenue"

    mock_response = create_mock_openai_response(
        {
            "companies": ["APPLE INC"],
            "metrics": ["revenue"],
            "sectors": [],
            "time_periods": ["latest"],
            "question_type": "lookup",
            "confidence": 0.9,
            "reasoning": "'Latest' indicates most recent available period.",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    entities = entity_extractor.extract(question, request_context)

    assert "APPLE INC" in entities.companies
    assert_contains_case_insensitive(entities.metrics, "revenue", "metrics")
    assert_contains_case_insensitive(entities.time_periods, "latest", "time_periods")


def test_extract_sector_question(entity_extractor, mock_azure_client, request_context):
    """Test extracting entities from 'Companies in Technology sector'"""
    question = "Companies in Technology sector"

    mock_response = create_mock_openai_response(
        {
            "companies": [],
            "metrics": [],
            "sectors": ["Information Technology"],
            "time_periods": [],
            "question_type": "list",
            "confidence": 0.9,
            "reasoning": "Technology normalized to official GICS name 'Information Technology'.",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    entities = entity_extractor.extract(question, request_context)

    assert len(entities.companies) == 0
    assert "Information Technology" in entities.sectors
    assert entities.question_type == "list"


# ==============================================================================
# UNIT TESTS: Edge Cases and Error Handling
# ==============================================================================


def test_extract_with_llm_failure_fallback(
    entity_extractor, mock_azure_client, request_context
):
    """Test fallback to deterministic when LLM fails"""
    question = "How many companies in Technology?"

    # Mock LLM to raise exception
    mock_azure_client.client.chat.completions.create.side_effect = Exception(
        "API Error"
    )

    # Should fallback to deterministic extraction
    entities = entity_extractor.extract(question, request_context)

    assert isinstance(entities, ExtractedEntities)
    # Deterministic extraction should still work
    assert isinstance(entities.confidence, float)
    assert entities.question_type in [
        "count",
        "lookup",
        "list",
        "comparison",
        "calculation",
        "trend",
    ]


def test_extract_json_parsing_retry(
    entity_extractor, mock_azure_client, request_context
):
    """Test retry logic on JSON parsing errors"""
    question = "What is Apple's CIK?"

    # First attempt: invalid JSON, second attempt: valid JSON
    invalid_response = Mock()
    invalid_choice = Mock()
    invalid_message = Mock()
    invalid_message.content = "Invalid JSON {"  # Malformed JSON
    invalid_choice.message = invalid_message
    invalid_response.choices = [invalid_choice]
    invalid_response.usage = Mock()
    invalid_response.usage.prompt_tokens = 100
    invalid_response.usage.completion_tokens = 20

    valid_response = create_mock_openai_response(
        {
            "companies": ["APPLE INC"],
            "metrics": ["cik"],
            "sectors": [],
            "time_periods": [],
            "question_type": "lookup",
            "confidence": 0.95,
            "reasoning": "Retry successful",
        }
    )

    mock_azure_client.client.chat.completions.create.side_effect = [
        invalid_response,
        valid_response,
    ]

    entities = entity_extractor.extract(question, request_context)

    # Should succeed on second attempt
    assert "APPLE INC" in entities.companies
    assert mock_azure_client.client.chat.completions.create.call_count == 2


def test_extract_pydantic_validation_error(
    entity_extractor, mock_azure_client, request_context
):
    """Test handling of Pydantic validation errors"""
    question = "Test question"

    # Mock response with invalid confidence (>1.0) - this should fail Pydantic validation
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    mock_message.content = json.dumps(
        {
            "companies": [],
            "metrics": [],
            "sectors": [],
            "time_periods": [],
            "question_type": "lookup",
            "confidence": 1.5,  # Invalid: >1.0
            "reasoning": "Test",
        }
    )
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 20

    mock_azure_client.client.chat.completions.create.return_value = mock_response

    # Should handle validation error and fallback to deterministic
    entities = entity_extractor.extract(question, request_context)
    assert isinstance(entities, ExtractedEntities)


# ==============================================================================
# UNIT TESTS: Telemetry Tracking
# ==============================================================================


def test_extract_tracks_llm_call(entity_extractor, mock_azure_client, request_context):
    """Test that LLM calls are tracked in telemetry"""
    question = "What is Apple's CIK?"

    mock_response = create_mock_openai_response(
        {
            "companies": ["APPLE INC"],
            "metrics": ["cik"],
            "sectors": [],
            "time_periods": [],
            "question_type": "lookup",
            "confidence": 0.95,
            "reasoning": "Test",
        }
    )
    mock_azure_client.client.chat.completions.create.return_value = mock_response

    entities = entity_extractor.extract(question, request_context)

    # Verify LLM call was tracked in metadata
    llm_calls = request_context.metadata.get("llm_calls", [])
    assert llm_calls, "LLM call did not succeed"
    llm_call = llm_calls[0]
    assert llm_call["stage"] == "entity_extraction"
    assert "tokens" in llm_call
    assert "latency_ms" in llm_call
    assert llm_call["success"] is True


# ==============================================================================
# INTEGRATION TESTS (require real Azure OpenAI API)
# ==============================================================================


@pytest.mark.integration
def test_extract_real_llm_simple_question(request_context, request):
    """Integration test with real Azure OpenAI API"""
    extractor = EntityExtractor(use_llm=True)
    assert extractor.azure_client is not None, "Azure OpenAI client not initialized"

    question = "What is Apple's CIK?"
    entities = extractor.extract(question, request_context)

    # Verify extraction quality
    assert isinstance(entities, ExtractedEntities)
    assert len(entities.companies) > 0  # Should extract Apple
    assert "cik" in entities.metrics or len(entities.metrics) > 0
    assert entities.confidence > 0.7  # Should have decent confidence

    # Verify telemetry in metadata
    llm_calls = request_context.metadata.get("llm_calls", [])
    assert llm_calls, "LLM call did not succeed"
    print(f"\nReal LLM extraction: {entities}")
    print(f"Tokens used: {llm_calls[0].get('tokens', {})}")
    print(f"Latency: {llm_calls[0].get('latency_ms', 0)}ms")


@pytest.mark.integration
def test_extract_real_llm_comparison_question(request_context, request):
    """Integration test with real Azure OpenAI API - comparison question"""
    extractor = EntityExtractor(use_llm=True)
    assert extractor.azure_client is not None, "Azure OpenAI client not initialized"

    question = "Compare Apple and Microsoft revenue"
    entities = extractor.extract(question, request_context)

    # Verify extraction quality
    assert isinstance(entities, ExtractedEntities)
    assert len(entities.companies) >= 2  # Should extract both companies
    assert any("revenue" in m.lower() for m in entities.metrics)
    assert entities.question_type in ["comparison", "lookup", "list"]

    print(f"\\nReal LLM extraction (comparison): {entities}")


# ==============================================================================
# PYTEST CONFIGURATION
# ==============================================================================


def pytest_addoption(parser):
    """Add command-line option for integration tests."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests with real Azure OpenAI API",
    )


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires Azure OpenAI API)",
    )
