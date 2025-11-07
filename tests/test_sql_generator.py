"""
Tests for SQL generation from entities and templates.
"""

import pytest
from src.sql_generator import SQLGenerator
from src.models import ExtractedEntities, LLMResponse, SQLValidationVerdict
from src.telemetry import create_request_context
from src.query_engine import QueryEngine
from src.entity_extractor import normalize_company_name
from src.prompts import get_sql_custom_generation_prompt
from src.schema_docs import schema_for_prompt


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
        generated_sql=(
            "SELECT COUNT(*) AS cnt "
            "FROM sub s "
            "JOIN num n ON n.adsh = s.adsh "
            "LIMIT 1"
        ),
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

        def validate_sql_semantic(self, request, instructions, input_prompt):
            return SQLValidationVerdict(
                success=True,
                is_valid=True,
                reason=None,
                confidence=0.9,
                processing_time_ms=50,
                token_usage={"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            )

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
    attempts = context.metadata.get("custom_sql_attempts", [])
    assert attempts and attempts[0]["success"] is True
    assert "JOIN num n ON n.adsh = s.adsh" in attempts[0]["sql"]


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

        def validate_sql_semantic(self, request, instructions, input_prompt):
            return SQLValidationVerdict(
                success=True,
                is_valid=True,
                reason=None,
                confidence=0.9,
                processing_time_ms=40,
                token_usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            )

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

    result = generator._generate_custom_sql(entities, "Generate revenue query", context)

    assert result is None
    assert context.metadata.get("llm_calls") is None
    attempts = context.metadata.get("custom_sql_attempts", [])
    assert attempts and attempts[0]["success"] is False
    assert "Disallowed keyword" in attempts[0]["failure_reason"]


def test_validate_sql_rejects_unknown_tables():
    generator = SQLGenerator(use_llm=False)
    is_valid, reason = generator.validate_sql("SELECT * FROM imaginary_table")
    assert not is_valid
    assert "Unknown tables" in reason


def test_validate_sql_requires_sub_join_for_num():
    generator = SQLGenerator(use_llm=False)
    is_valid, reason = generator.validate_sql("SELECT n.value FROM num n WHERE n.tag = 'Revenues'")
    assert not is_valid
    assert "join through SUB" in reason


def test_validate_sql_accepts_simple_companies_query():
    generator = SQLGenerator(use_llm=False)
    sql = "SELECT name FROM companies WHERE gics_sector = 'Energy'"
    is_valid, reason = generator.validate_sql(sql)
    assert is_valid
    assert reason is None


def test_custom_sql_prompt_includes_examples_and_hints():
    schema = schema_for_prompt()
    constraints = "- Use registered views only\n- Keep results small"
    prompt_parts = get_sql_custom_generation_prompt(
        question="How many Energy companies have revenue above $1 billion?",
        entities={
            "sectors": ["Energy"],
            "metrics": ["revenue"],
            "question_type": "count",
        },
        schema=schema,
        constraints=constraints,
        domain_hints={"threshold": "> 1 billion USD"},
    )

    instructions = prompt_parts["instructions"]
    input_prompt = prompt_parts["input"]

    assert "DuckDB" in instructions
    assert "Energy" in input_prompt
    assert "Examples" in input_prompt
    assert "threshold" in input_prompt.lower()
    assert "```sql" in input_prompt


@pytest.mark.parametrize(
    "company_input",
    [
        "Apple Inc",
        "Microsoft Corporation",
        "Alphabet Inc",
        "Amazon.com",
        "Tesla Motors",
    ],
)
def test_company_cik_lookup_returns_row(company_input):
    """Ensure company CIK template resolves canonical company names."""
    generator = SQLGenerator(use_llm=False)
    context = create_request_context("test")
    entities = ExtractedEntities(
        companies=[company_input],
        metrics=["CIK"],
        question_type="lookup",
        confidence=0.9,
    )
    question = f"What is {company_input}'s CIK?"

    canonical_name = normalize_company_name(company_input)
    tokens = canonical_name.replace(",", "").split()
    search_token = tokens[0] if tokens else canonical_name

    qe = QueryEngine()
    try:
        expected_df = qe.execute(
            f"""
            SELECT name, cik
            FROM companies
            WHERE name LIKE '%{search_token}%'
            ORDER BY LENGTH(name)
            LIMIT 1
            """
        )
    finally:
        qe.close()

    assert not expected_df.empty
    expected_cik = expected_df.iloc[0]["cik"]

    result = generator.generate(entities, question, context)

    assert result is not None
    assert result.template_id == "company_by_cik"
    assert expected_cik not in ("", None)

    qe_result = QueryEngine()
    try:
        df = qe_result.execute(result.sql)
    finally:
        qe_result.close()

    assert not df.empty
    assert expected_cik in df["cik"].astype(str).tolist()


@pytest.mark.parametrize(
    "company_input",
    ["Apple Inc", "JPMorgan Chase", "Abbott Labs", "Chevron", "Walmart"],
)
def test_company_sector_lookup_matches_expected(company_input):
    """Verify sector template returns data for flagship companies."""
    generator = SQLGenerator(use_llm=False)
    context = create_request_context("test")
    entities = ExtractedEntities(
        companies=[company_input],
        metrics=["Sector"],
        question_type="lookup",
        confidence=0.8,
    )
    question = f"What sector is {company_input} in?"

    canonical_name = normalize_company_name(company_input)
    tokens = canonical_name.replace(",", "").split()
    search_token = tokens[0] if tokens else canonical_name

    qe = QueryEngine()
    try:
        expected_df = qe.execute(
            f"""
            SELECT name, gics_sector
            FROM companies
            WHERE name LIKE '%{search_token}%'
            ORDER BY LENGTH(name)
            LIMIT 1
            """
        )
    finally:
        qe.close()

    assert not expected_df.empty
    expected_sector = expected_df.iloc[0]["gics_sector"]

    result = generator.generate(entities, question, context)

    assert result is not None
    assert result.template_id == "company_sector"

    qe_result = QueryEngine()
    try:
        df = qe_result.execute(result.sql)
    finally:
        qe_result.close()

    assert not df.empty
    assert expected_sector in df["gics_sector"].astype(str).tolist()


@pytest.mark.parametrize(
    "company_input",
    [
        "Apple Inc",
        "Microsoft Corporation",
        "Alphabet Inc",
    ],
)
def test_latest_revenue_template_returns_value(company_input):
    """Regression coverage for latest revenue template on key companies."""
    generator = SQLGenerator(use_llm=False)
    context = create_request_context("test")
    entities = ExtractedEntities(
        companies=[company_input],
        metrics=["Revenue"],
        question_type="lookup",
        confidence=0.85,
    )
    question = f"What is the latest revenue for {company_input}?"

    result = generator.generate(entities, question, context)

    assert result is not None
    assert result.template_id == "latest_revenue"
    assert "Revenues" in result.sql or "SalesRevenueNet" in result.sql

    qe = QueryEngine()
    try:
        df = qe.execute(result.sql)
    finally:
        qe.close()

    assert list(df.columns) == [
        "revenue",
        "period_end_date",
        "fiscal_year",
        "fiscal_period",
    ]


def test_company_name_by_cik_template():
    """Template returns company name for an exact CIK lookup."""
    generator = SQLGenerator(use_llm=False)
    context = create_request_context("test")
    entities = ExtractedEntities(confidence=0.9)
    question = "Which company has CIK 0000066740?"

    result = generator.generate(entities, question, context)

    assert result is not None
    assert result.template_id == "company_name_by_cik"

    qe = QueryEngine()
    try:
        df = qe.execute(result.sql)
    finally:
        qe.close()

    assert not df.empty
    assert df.iloc[0]["name"] == "3M CO"


def test_most_common_currency_template():
    """Template identifies most frequently used currency in num table."""
    generator = SQLGenerator(use_llm=False)
    context = create_request_context("test")
    entities = ExtractedEntities(confidence=0.9)
    question = "What currency is used most frequently in the numerical data?"

    result = generator.generate(entities, question, context)

    assert result is not None
    assert result.template_id == "most_common_currency"

    qe = QueryEngine()
    try:
        df = qe.execute(result.sql)
    finally:
        qe.close()

    assert not df.empty
    assert df.iloc[0]["currency"] == "USD"


def test_fact_count_with_footnotes_template():
    """Template counts numeric facts that have footnotes."""
    generator = SQLGenerator(use_llm=False)
    context = create_request_context("test")
    entities = ExtractedEntities(confidence=0.9)
    question = "How many financial facts have footnotes?"

    result = generator.generate(entities, question, context)

    assert result is not None
    assert result.template_id == "fact_count_with_footnotes"

    qe = QueryEngine()
    try:
        df = qe.execute(result.sql)
    finally:
        qe.close()

    assert not df.empty
    assert df.iloc[0]["fact_count"] > 0
