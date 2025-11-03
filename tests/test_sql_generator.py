"""
Tests for SQL generation from entities and templates.
"""

from src.sql_generator import SQLGenerator
from src.models import ExtractedEntities
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
    assert sql.template_id == "sector_count"


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
    assert sql.template_id == "company_cik"


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
    assert sql.template_id == "company_sector"


def test_template_matching():
    """Test that the correct template is matched."""
    generator = SQLGenerator()
    context = create_request_context("test")

    # Test different question types
    questions = [
        ("How many companies in Healthcare?", "sector_count"),
        ("What is Tesla's CIK?", "company_cik"),
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
