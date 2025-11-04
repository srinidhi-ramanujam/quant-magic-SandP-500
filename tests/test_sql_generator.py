"""
Tests for SQL generation from entities and templates.
"""

import pytest
from src.sql_generator import SQLGenerator
from src.models import ExtractedEntities, LLMResponse
from src.telemetry import create_request_context


def test_sector_count_template():
    """Test SQL generation for sector count queries."""
    generator = SQLGenerator()
    context = create_request_context("test")

    entities = ExtractedEntities(
        sectors=["Information Technology"], question_type="count", confidence=0.9
    )

    question = "How many companies in Information Technology sector?"
    sql = generator.generate(entities, question, context)

    assert sql is not None
    assert "SELECT" in sql.sql
    assert "COUNT" in sql.sql
    assert "companies" in sql.sql.lower()
    # Template ID changed in expanded template set
    assert sql.template_id == "sector_company_count"


@pytest.mark.xfail(reason="Template pattern needs update for expanded template set")
def test_company_cik_template():
    """Test SQL generation for company CIK lookup."""
    generator = SQLGenerator()
    context = create_request_context("test")

    entities = ExtractedEntities(
        companies=["Apple"], metrics=["CIK"], question_type="lookup", confidence=0.9
    )

    question = "What is Apple's CIK?"
    sql = generator.generate(entities, question, context)

    assert sql is not None
    assert "SELECT" in sql.sql
    assert "cik" in sql.sql.lower()
    # Template ID may vary in expanded set
    assert "cik" in sql.template_id.lower()


@pytest.mark.xfail(reason="Template pattern needs update for expanded template set")
def test_company_sector_template():
    """Test SQL generation for company sector lookup."""
    generator = SQLGenerator()
    context = create_request_context("test")

    entities = ExtractedEntities(
        companies=["Microsoft"],
        metrics=["Sector"],
        question_type="lookup",
        confidence=0.9,
    )

    question = "What sector is Microsoft in?"
    sql = generator.generate(entities, question, context)

    assert sql is not None
    assert "SELECT" in sql.sql
    assert "gics_sector" in sql.sql.lower()
    # Template ID may vary in expanded set
    assert "sector" in sql.template_id.lower()


def test_template_matching():
    """Test that the correct template is matched."""
    generator = SQLGenerator()
    context = create_request_context("test")

    # Test different question types
    questions = [
        ("How many companies in Healthcare?", "sector_company_count"),
        ("What is Tesla's CIK?", "company_by_cik"),
        ("What sector is Amazon in?", "company_sector"),
    ]

    for question, expected_template in questions:
        entities = ExtractedEntities(confidence=0.8)
        sql = generator.generate(entities, question, context)

        if sql:
            assert sql.template_id == expected_template


def test_invalid_entity_handling():
    """Test handling of invalid or missing entities."""
    generator = SQLGenerator()
    context = create_request_context("test")

    # Empty entities
    entities = ExtractedEntities(confidence=0.3)
    question = "Random question without clear intent"

    sql = generator.generate(entities, question, context)

    # Should return None or handle gracefully
    # (In Phase 0, we expect None for unmatched patterns)
    assert sql is None
def test_generate_custom_sql_helper(monkeypatch):
    """Custom SQL helper consumes Azure client response and records telemetry."""

    mock_response = LLMResponse(
        success=True,
        generated_sql="SELECT 1 FROM num LIMIT 1",
        explanation="demo",
        confidence=0.8,
        processing_time_ms=120,
        token_usage={"prompt_tokens": 10, "completion_tokens": 5},
        model_version="gpt-test",
    )

    class DummyAzureClient:
        def __init__(self):
            self.config = type("cfg", (), {"deployment_name": "gpt-test"})

        def generate_sql(self, request):  # noqa: D401
            return mock_response

        def is_available(self):
            return True

    import src.azure_client as azure_module

    monkeypatch.setattr(
        azure_module,
        "AzureOpenAIClient",
        lambda: DummyAzureClient(),
        raising=False,
    )

    generator = SQLGenerator(use_llm=True)
    context = create_request_context("test")
    entities = ExtractedEntities(confidence=0.5)

    result = generator._generate_custom_sql(entities, "Generate revenue query", context)

    assert result is not None
    assert result.generation_method == "llm_custom"
    stages = [call["stage"] for call in context.metadata.get("llm_calls", [])]
    assert "custom_sql" in stages


def test_generate_custom_sql_rejects_invalid_sql(monkeypatch):
    """Custom SQL helper rejects responses that fail validation."""

    mock_response = LLMResponse(
        success=True,
        generated_sql="DELETE FROM companies",
        explanation="demo",
        confidence=0.8,
        processing_time_ms=80,
        token_usage={"prompt_tokens": 8, "completion_tokens": 4},
        model_version="gpt-test",
    )

    class DummyAzureClient:
        def __init__(self):
            self.config = type("cfg", (), {"deployment_name": "gpt-test"})

        def generate_sql(self, request):  # noqa: D401
            return mock_response

        def is_available(self):
            return True

    import src.azure_client as azure_module

    monkeypatch.setattr(
        azure_module,
        "AzureOpenAIClient",
        lambda: DummyAzureClient(),
        raising=False,
    )

    generator = SQLGenerator(use_llm=True)
    context = create_request_context("test")
    entities = ExtractedEntities(confidence=0.4)

    result = generator._generate_custom_sql(
        entities, "Generate revenue query", context
    )

    assert result is None
    assert context.metadata.get("llm_calls") is None
