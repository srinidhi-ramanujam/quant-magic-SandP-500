"""Regression tests for template parameter extraction helpers."""

from src.intelligence_loader import IntelligenceLoader


def _loader() -> IntelligenceLoader:
    # Use full template catalog to exercise parquet-backed templates.
    return IntelligenceLoader(use_phase_0_only=False)


def test_currency_parameter_extraction_for_cad():
    loader = _loader()
    question = "How many facts are denominated in Canadian dollars (CAD)?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "fact_count_by_currency"
    assert match.matched_parameters.get("currency") == "CAD"


def test_unit_parameter_extraction_for_shares():
    loader = _loader()
    question = "How many facts use 'shares' as the unit of measure?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "fact_count_by_unit"
    assert match.matched_parameters.get("unit") == "shares"


def test_distinct_unit_question_uses_distinct_template():
    loader = _loader()
    question = "How many different unit types are present in the dataset?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "distinct_uom_count"
