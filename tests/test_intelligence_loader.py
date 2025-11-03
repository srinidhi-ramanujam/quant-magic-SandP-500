"""
Tests for intelligence loader and template matching.
"""

from src.intelligence_loader import (
    IntelligenceLoader,
)


def test_load_query_intelligence():
    """Test loading query intelligence templates."""
    loader = IntelligenceLoader(use_phase_0_only=True)

    templates = loader.get_all_templates()

    # Should have exactly 3 Phase 0 templates
    assert len(templates) >= 3

    # Check that Phase 0 templates are present
    template_ids = [t.template_id for t in templates]
    assert "sector_count" in template_ids
    assert "company_cik" in template_ids
    assert "company_sector" in template_ids


def test_get_template_by_id():
    """Test retrieving a specific template by ID."""
    loader = IntelligenceLoader(use_phase_0_only=True)

    # Get sector_count template
    template = loader.get_template_by_id("sector_count")

    assert template is not None
    assert template.template_id == "sector_count"
    assert "sector" in template.parameters
    assert "SELECT" in template.sql_template

    # Try non-existent template
    missing = loader.get_template_by_id("non_existent")
    assert missing is None


def test_match_pattern():
    """Test pattern matching against questions."""
    loader = IntelligenceLoader(use_phase_0_only=True)

    # Test 1: Sector count question
    question1 = "How many companies are in the Technology sector?"
    match1 = loader.match_pattern(question1)

    assert match1.template is not None
    assert match1.template.template_id == "sector_count"
    assert match1.match_confidence > 0.5
    assert "sector" in match1.matched_parameters
    assert match1.fallback_to_llm is False

    # Test 2: Company CIK question
    question2 = "What is Apple's CIK?"
    match2 = loader.match_pattern(question2)

    assert match2.template is not None
    assert match2.template.template_id == "company_cik"
    assert "company" in match2.matched_parameters

    # Test 3: Company sector question
    question3 = "What sector is Microsoft in?"
    match3 = loader.match_pattern(question3)

    assert match3.template is not None
    assert match3.template.template_id == "company_sector"
    assert "company" in match3.matched_parameters

    # Test 4: No match
    question4 = "This is a completely unrelated question"
    match4 = loader.match_pattern(question4)

    assert match4.template is None
    assert match4.fallback_to_llm is True
