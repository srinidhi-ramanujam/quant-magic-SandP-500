"""
Tests for response formatting into natural language.
"""

import pandas as pd
from src.response_formatter import ResponseFormatter
from src.models import QueryResult, ExtractedEntities
from src.telemetry import create_request_context


def test_format_count_response():
    """Test formatting count query responses."""
    formatter = ResponseFormatter()
    context = create_request_context("test")

    # Create a count result
    df = pd.DataFrame({"count": [143]})
    query_result = QueryResult(
        data=df,
        row_count=1,
        columns=["count"],
        execution_time_seconds=0.05,
        sql_executed="SELECT COUNT(*) FROM companies",
    )

    entities = ExtractedEntities(
        sectors=["Information Technology"], question_type="count", confidence=0.9
    )

    response = formatter.format(query_result, entities, context)

    assert response.success is True
    assert "143" in response.answer
    assert "Information Technology" in response.answer
    assert response.confidence > 0.5


def test_format_lookup_response():
    """Test formatting lookup query responses."""
    formatter = ResponseFormatter()
    context = create_request_context("test")

    # Create a CIK lookup result
    df = pd.DataFrame({"name": ["APPLE INC"], "cik": ["0000320193"]})

    query_result = QueryResult(
        data=df,
        row_count=1,
        columns=["name", "cik"],
        execution_time_seconds=0.03,
        sql_executed="SELECT name, cik FROM companies WHERE name LIKE '%Apple%'",
    )

    entities = ExtractedEntities(
        companies=["Apple"], metrics=["CIK"], question_type="lookup", confidence=0.95
    )

    response = formatter.format(query_result, entities, context)

    assert response.success is True
    assert "CIK" in response.answer
    assert "0000320193" in response.answer


def test_add_context_metadata():
    """Test that metadata is added to responses."""
    formatter = ResponseFormatter()
    context = create_request_context("test")

    df = pd.DataFrame({"count": [50]})
    query_result = QueryResult(
        data=df,
        row_count=1,
        columns=["count"],
        execution_time_seconds=0.04,
        sql_executed="SELECT COUNT(*) FROM companies",
    )

    entities = ExtractedEntities(
        sectors=["Healthcare"], question_type="count", confidence=0.9
    )

    response = formatter.format(query_result, entities, context, debug_mode=True)

    # Check metadata
    assert "request_id" in response.metadata
    assert "total_time_seconds" in response.metadata
    assert response.metadata["request_id"] == context.request_id

    # Check debug info
    assert response.debug_info is not None
    assert "entities" in response.debug_info
    assert "sql_executed" in response.debug_info


def test_error_response_formatting():
    """Test formatting error responses."""
    formatter = ResponseFormatter()
    context = create_request_context("test")

    error = ValueError("Template not found")
    response = formatter.format_error(error, context, debug_mode=True)

    assert response.success is False
    assert response.error is not None
    assert response.confidence == 0.0
    assert len(response.answer) > 0  # Should have user-friendly message

    # Check debug info for errors
    if response.debug_info:
        assert "error_type" in response.debug_info
