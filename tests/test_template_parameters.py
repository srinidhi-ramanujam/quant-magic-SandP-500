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


def test_tag_question_routes_to_tag_unit_template():
    loader = _loader()
    question = "How many XBRL tags have 'shares' as unit of measure in numerical data?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "tag_count_by_unit"
    assert match.matched_parameters.get("unit") == "shares"


def test_debit_credit_question_uses_new_template():
    loader = _loader()
    question = "How many XBRL tags have a debit-credit flag of 'Debit'?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "tag_count_by_debit_credit"


def test_dimhash_question_uses_dimhash_template():
    loader = _loader()
    question = "How many financial facts have duplicate values (dimhash populated)?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "fact_count_dimhash_populated"


def test_roe_threshold_extraction():
    loader = _loader()
    question = "How many companies have Return on Equity above 20%?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "companies_return_on_equity_above_threshold"
    assert match.matched_parameters.get("threshold") == "20"


def test_company_roe_template_selected():
    loader = _loader()
    question = "What is Google's (Alphabet) return on equity (ROE)?"
    match = loader.match_pattern(question)

    assert match.template is not None
    assert match.template.template_id == "latest_roe"
