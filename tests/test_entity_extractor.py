"""
Tests for entity extraction from natural language questions.
"""

import pytest

from src.entity_extractor import EntityExtractor
from src.telemetry import create_request_context


@pytest.fixture
def deterministic_extractor():
    """Provide a deterministic extractor for offline testing."""
    return EntityExtractor(use_llm=False)


def test_extract_company_name(deterministic_extractor):
    """Test extracting company names from questions."""
    extractor = deterministic_extractor
    context = create_request_context("test")

    # Test with capitalized company name
    entities1 = extractor.extract("What is Apple Inc's revenue?", context)
    assert len(entities1.companies) > 0
    assert any("apple" in c.lower() for c in entities1.companies)

    # Test with common company name
    entities2 = extractor.extract("What is microsoft's CIK?", context)
    assert len(entities2.companies) > 0


def test_extract_sector(deterministic_extractor):
    """Test extracting sector names from questions."""
    extractor = deterministic_extractor
    context = create_request_context("test")

    # Test Technology sector
    entities1 = extractor.extract("How many companies in Technology sector?", context)
    assert len(entities1.sectors) > 0
    assert "Information Technology" in entities1.sectors

    # Test Healthcare sector
    entities2 = extractor.extract("How many companies in Healthcare sector?", context)
    assert len(entities2.sectors) > 0
    assert "Health Care" in entities2.sectors

    # Test Financial sector
    entities3 = extractor.extract("Companies in Financials sector", context)
    assert len(entities3.sectors) > 0
    assert "Financials" in entities3.sectors


def test_extract_multiple_entities(deterministic_extractor):
    """Test extracting multiple entities from a single question."""
    extractor = deterministic_extractor
    context = create_request_context("test")

    question = "What is Apple's CIK in the Technology sector?"
    entities = extractor.extract(question, context)

    # Should extract both company and metric
    assert len(entities.companies) > 0
    assert len(entities.metrics) > 0
    assert any(metric.lower() == "cik" for metric in entities.metrics)


def test_confidence_scoring(deterministic_extractor):
    """Test that confidence scores are calculated reasonably."""
    extractor = deterministic_extractor
    context = create_request_context("test")

    # Question with clear entities should have high confidence
    entities1 = extractor.extract("What is Apple Inc's CIK?", context)
    assert entities1.confidence > 0.5

    # Vague question should have lower confidence
    entities2 = extractor.extract("Tell me about something", context)
    assert entities2.confidence <= entities1.confidence


def test_no_match_handling(deterministic_extractor):
    """Test handling when no entities are extracted."""
    extractor = deterministic_extractor
    context = create_request_context("test")

    entities = extractor.extract("Hello world", context)

    # Should still return a valid ExtractedEntities object
    assert entities is not None
    assert isinstance(entities.companies, list)
    assert isinstance(entities.metrics, list)
    assert isinstance(entities.sectors, list)
    assert 0 <= entities.confidence <= 1


def test_ambiguous_entity_handling(deterministic_extractor):
    """Test handling ambiguous or complex extractions."""
    extractor = deterministic_extractor
    context = create_request_context("test")

    # Question with potential ambiguity
    question = "Compare Apple and Microsoft in Technology"
    entities = extractor.extract(question, context)

    # Should extract multiple companies
    assert len(entities.companies) >= 1

    # Should identify question type
    assert entities.question_type is not None
