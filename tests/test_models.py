"""
Tests for Pydantic models and data validation.
"""

import pytest
from datetime import datetime
import pandas as pd

from src.models import (
    QueryRequest,
    ExtractedEntities,
    QueryTemplate,
    IntelligenceMatch,
    GeneratedSQL,
    QueryResult,
    FormattedResponse,
    TelemetryData,
)


def test_query_request_validation():
    """Test QueryRequest model validation."""
    # Valid request
    request = QueryRequest(question="What is Apple's CIK?")
    assert request.question == "What is Apple's CIK?"
    assert request.debug_mode is False
    assert isinstance(request.timestamp, datetime)

    # Test with empty question (should fail)
    with pytest.raises(Exception):
        QueryRequest(question="")


def test_extracted_entities_validation():
    """Test ExtractedEntities model validation."""
    entities = ExtractedEntities(
        companies=["Apple"],
        metrics=["CIK"],
        sectors=[],
        time_periods=[],
        question_type="lookup",
        confidence=0.95,
    )

    assert len(entities.companies) == 1
    assert entities.companies[0] == "Apple"
    assert entities.confidence == 0.95
    assert entities.question_type == "lookup"

    # Test confidence validation (should be 0-1)
    with pytest.raises(Exception):
        ExtractedEntities(confidence=1.5)


def test_intelligence_match_model():
    """Test IntelligenceMatch model."""
    template = QueryTemplate(
        template_id="test_template",
        name="Test Template",
        pattern="test pattern",
        sql_template="SELECT * FROM test",
        parameters=["param1"],
    )

    match = IntelligenceMatch(
        template=template,
        match_confidence=0.90,
        matched_parameters={"param1": "value1"},
        fallback_to_llm=False,
    )

    assert match.template.template_id == "test_template"
    assert match.match_confidence == 0.90
    assert match.matched_parameters["param1"] == "value1"
    assert match.fallback_to_llm is False


def test_generated_sql_model():
    """Test GeneratedSQL model."""
    sql = GeneratedSQL(
        sql="SELECT COUNT(*) FROM companies WHERE sector = 'Technology'",
        parameters={"sector": "Technology"},
        template_id="sector_count",
        generation_method="template",
        confidence=1.0,
    )

    assert "SELECT" in sql.sql
    assert sql.parameters["sector"] == "Technology"
    assert sql.template_id == "sector_count"
    assert sql.generation_method == "template"


def test_query_result_model():
    """Test QueryResult model."""
    # Create a simple DataFrame
    df = pd.DataFrame({"count": [143]})

    result = QueryResult(
        data=df,
        row_count=1,
        columns=["count"],
        execution_time_seconds=0.05,
        sql_executed="SELECT COUNT(*) FROM companies",
    )

    assert result.row_count == 1
    assert "count" in result.columns
    assert result.execution_time_seconds == 0.05

    # Test to_dict conversion
    result_dict = result.to_dict()
    assert isinstance(result_dict, dict)
    assert "data" in result_dict
    assert "row_count" in result_dict


def test_formatted_response_model():
    """Test FormattedResponse model."""
    response = FormattedResponse(
        answer="There are 143 companies in the Technology sector.",
        confidence=0.95,
        sources=["companies.parquet"],
        metadata={"request_id": "test123"},
        success=True,
    )

    assert response.success is True
    assert response.confidence == 0.95
    assert len(response.answer) > 0
    assert "companies.parquet" in response.sources

    # Test to_dict conversion
    response_dict = response.to_dict()
    assert isinstance(response_dict, dict)
    assert response_dict["success"] is True
    assert response_dict["answer"] == response.answer


def test_telemetry_data_model():
    """Test TelemetryData model."""
    telemetry = TelemetryData(
        request_id="abc123",
        question="Test question",
        total_time_seconds=0.150,
        component_timings={"comp1": 0.05, "comp2": 0.08},
        success=True,
    )

    assert telemetry.request_id == "abc123"
    assert telemetry.total_time_seconds == 0.150
    assert len(telemetry.component_timings) == 2
    assert telemetry.success is True

    # Test overhead calculation
    overhead = telemetry.telemetry_overhead_pct()
    assert overhead >= 0
    assert overhead <= 100


def test_model_serialization():
    """Test that all models can be serialized to dict/JSON."""
    # QueryRequest
    request = QueryRequest(question="Test")
    assert request.model_dump() is not None

    # ExtractedEntities
    entities = ExtractedEntities(confidence=0.8)
    assert entities.model_dump() is not None

    # FormattedResponse
    response = FormattedResponse(answer="Test answer", success=True)
    response_dict = response.to_dict()
    assert isinstance(response_dict, dict)

    # TelemetryData
    telemetry = TelemetryData(
        request_id="test", question="test", total_time_seconds=1.0, success=True
    )
    assert telemetry.model_dump() is not None
