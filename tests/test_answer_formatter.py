"""
Unit tests for the AnswerFormatter orchestration layer.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from src.answer_formatter import AnswerFormatter
from src.models import ConversationTurn, ExtractedEntities, QueryResult
from src.telemetry import create_request_context


def _mock_azure_client(payload: dict[str, object]) -> MagicMock:
    """Create a mocked Azure client that returns the provided payload."""
    mock_client = MagicMock()
    mock_client.is_available.return_value = True
    mock_client.config.deployment_name = "gpt-5"
    mock_client._parse_api_response.side_effect = lambda resp: resp.output_text
    mock_client._extract_token_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }

    response = SimpleNamespace(
        output_text=json.dumps(payload),
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            output_tokens_details=SimpleNamespace(reasoning_tokens=2),
        ),
    )

    mock_rest_client = MagicMock()
    mock_rest_client.responses.create.return_value = response
    mock_client.client = mock_rest_client

    return mock_client


def _sample_query_result() -> QueryResult:
    df = pd.DataFrame(
        [
            {"name": "Sample Co", "revenue": 14.2, "year": 2023},
            {"name": "Another Co", "revenue": 9.1, "year": 2023},
        ]
    )
    return QueryResult(
        data=df,
        row_count=len(df),
        columns=list(df.columns),
        execution_time_seconds=0.05,
        sql_executed="SELECT * FROM sample",
    )


def test_answer_formatter_returns_presentation_payload():
    payload = {
        "narrative": "Sample narrative",
        "highlights": ["Point A"],
        "table": {"columns": ["name"], "rows": [{"name": "Sample Co"}], "truncated": False},
        "warnings": [],
    }
    mock_client = _mock_azure_client(payload)
    formatter = AnswerFormatter(azure_client=mock_client)
    context = create_request_context("Test question")

    outcome = formatter.format_answer(
        question="What is the revenue?",
        base_answer="Base answer",
        query_result=_sample_query_result(),
        entities=ExtractedEntities(question_type="lookup"),
        template_id="revenue_lookup",
        context=context,
        history=[
            ConversationTurn(role="user", content="Hi", timestamp=None),
            ConversationTurn(role="assistant", content="Hello", timestamp=None),
        ],
    )

    assert outcome.presentation is not None
    assert outcome.presentation.narrative == "Sample narrative"
    assert outcome.token_usage["total_tokens"] == 15


def test_answer_formatter_skips_empty_results():
    formatter = AnswerFormatter(azure_client=_mock_azure_client({}))
    context = create_request_context("Test question")
    empty_result = QueryResult(
        data=pd.DataFrame([]),
        row_count=0,
        columns=[],
        execution_time_seconds=0.01,
        sql_executed="SELECT * FROM sample",
    )

    outcome = formatter.format_answer(
        question="What is the revenue?",
        base_answer="Base answer",
        query_result=empty_result,
        entities=None,
        template_id=None,
        context=context,
        history=[],
    )

    assert outcome.presentation is None
    assert outcome.error == "empty_rows"
