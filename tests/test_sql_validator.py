import pytest

from src.sql_validator import SQLValidator
from src.telemetry import create_request_context
from src.models import SQLValidationVerdict


def test_static_validation_blocks_dangerous_keyword():
    validator = SQLValidator(use_llm=False)
    is_valid, reason = validator.validate_static("DELETE FROM companies")
    assert not is_valid
    assert "Disallowed keyword" in reason


def test_static_validation_allows_cte_usage():
    validator = SQLValidator(use_llm=False)
    sql = """
    WITH latest AS (
        SELECT *
        FROM sub
        LIMIT 1
    )
    SELECT *
    FROM latest
    JOIN sub ON latest.adsh = sub.adsh
    """
    is_valid, reason = validator.validate_static(sql)
    assert is_valid
    assert reason is None


def test_semantic_validation_success(monkeypatch):
    class DummyAzureClient:
        def __init__(self):
            self.config = type("cfg", (), {"deployment_name": "gpt-test", "max_tokens": 1024})

        def is_available(self):
            return True

        def validate_sql_semantic(self, request, instructions, input_prompt):
            return SQLValidationVerdict(
                success=True,
                is_valid=True,
                reason=None,
                confidence=0.92,
                processing_time_ms=120,
                token_usage={"prompt_tokens": 150, "completion_tokens": 30, "total_tokens": 180},
            )

    import src.azure_client as azure_module

    monkeypatch.setattr(
        azure_module,
        "AzureOpenAIClient",
        lambda: DummyAzureClient(),
        raising=False,
    )

    validator = SQLValidator(use_llm=True)
    context = create_request_context("How many companies are in Energy?")
    ok, reason, confidence = validator.validate(
        "SELECT COUNT(*) FROM companies WHERE gics_sector = 'Energy'",
        "How many companies are in Energy?",
        {"sectors": ["Energy"], "question_type": "count"},
        context,
    )

    assert ok
    assert reason is None
    assert confidence == pytest.approx(0.92, rel=1e-3)
    assert any(record["stage"] == "semantic" for record in context.metadata["sql_validation"])


def test_semantic_validation_failure(monkeypatch):
    class DummyAzureClient:
        def __init__(self):
            self.config = type("cfg", (), {"deployment_name": "gpt-test", "max_tokens": 1024})

        def is_available(self):
            return True

        def validate_sql_semantic(self, request, instructions, input_prompt):
            return SQLValidationVerdict(
                success=True,
                is_valid=False,
                reason="SQL does not answer the question",
                confidence=0.4,
                processing_time_ms=90,
                token_usage={"prompt_tokens": 120, "completion_tokens": 20, "total_tokens": 140},
            )

    import src.azure_client as azure_module

    monkeypatch.setattr(
        azure_module,
        "AzureOpenAIClient",
        lambda: DummyAzureClient(),
        raising=False,
    )

    validator = SQLValidator(use_llm=True)
    context = create_request_context("How many companies are in Energy?")
    ok, reason, confidence = validator.validate(
        "SELECT name FROM companies LIMIT 5",
        "How many companies are in Energy?",
        {},
        context,
    )

    assert not ok
    assert "does not answer" in reason
    assert confidence == pytest.approx(0.4, rel=1e-3)


def test_semantic_validation_skipped_when_llm_disabled():
    validator = SQLValidator(use_llm=False)
    context = create_request_context("Dummy question")
    ok, reason, confidence = validator.validate(
        "SELECT name FROM companies",
        "Dummy question",
        {},
        context,
    )

    assert ok
    assert reason is None
    assert confidence == pytest.approx(0.0)
    semantic_records = [
        record for record in context.metadata["sql_validation"] if record["stage"] == "semantic"
    ]
    assert semantic_records and semantic_records[0].get("skipped")
