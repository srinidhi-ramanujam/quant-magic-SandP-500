from __future__ import annotations

from typing import Optional

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.app import app, get_query_service
from src.models import FormattedResponse, GeneratedSQL, QueryRequest, QueryResult
from src.services import QueryServiceResult
from src.telemetry import create_request_context


class _StubQueryService:
    """Simple stub that always returns the provided result."""

    def __init__(self, result: QueryServiceResult) -> None:
        self._result = result
        self.called_with: Optional[QueryRequest] = None

    def run(self, question: str, *, debug_mode: bool = False):
        self.called_with = QueryRequest(question=question, debug_mode=debug_mode)
        return self._result


def _success_result() -> QueryServiceResult:
    context = create_request_context("How many companies are there?")
    context.component_timings["query_execution"] = 0.012

    df = pd.DataFrame([{"count": 11}])
    query_result = QueryResult(
        data=df,
        row_count=len(df),
        columns=list(df.columns),
        execution_time_seconds=0.012,
        sql_executed="SELECT 11",
    )

    response = FormattedResponse(
        answer="There are 11 companies in the Technology sector.",
        confidence=0.92,
        sources=["companies_with_sectors.parquet"],
        metadata={"row_count": 1},
        success=True,
        error=None,
        debug_info={"sql_executed": "SELECT 11"},
    )

    generated_sql = GeneratedSQL(
        sql="SELECT 11",
        parameters={},
        template_id="sector_count",
        generation_method="template",
        confidence=0.92,
    )

    return QueryServiceResult(
        response=response,
        context=context,
        entities=None,
        generated_sql=generated_sql,
        query_result=query_result,
        success=True,
        error=None,
    )


def _failure_result() -> QueryServiceResult:
    context = create_request_context("Unknown question?")
    response = FormattedResponse(
        answer="An error occurred while processing your question: unable to process",
        confidence=0.0,
        sources=[],
        metadata={},
        success=False,
        error="unable to process",
        debug_info=None,
    )

    return QueryServiceResult(
        response=response,
        context=context,
        entities=None,
        generated_sql=None,
        query_result=None,
        success=False,
        error="unable to process",
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Ensure dependency overrides do not leak between tests."""
    yield
    app.dependency_overrides.clear()


def test_healthcheck():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_endpoint_returns_answer_and_sql():
    stub = _StubQueryService(_success_result())
    app.dependency_overrides[get_query_service] = lambda: stub

    client = TestClient(app)
    response = client.post("/query", json={"question": "How many companies?"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["success"] is True
    assert payload["answer"].startswith("There are 11")
    assert payload["sql"] == "SELECT 11"
    assert payload["metadata"]["row_count"] == 1
    assert "component_timings" in payload["metadata"]
    # Debug info is hidden by default
    assert payload.get("debug") is None


def test_query_endpoint_includes_debug_when_requested():
    stub = _StubQueryService(_success_result())
    app.dependency_overrides[get_query_service] = lambda: stub

    client = TestClient(app)
    response = client.post("/query", json={"question": "How many?", "debug_mode": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["debug"] is not None
    assert payload["debug"]["sql_executed"] == "SELECT 11"


def test_query_endpoint_surfaces_errors():
    stub = _StubQueryService(_failure_result())
    app.dependency_overrides[get_query_service] = lambda: stub

    client = TestClient(app)
    response = client.post("/query", json={"question": "Break it"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["success"] is False
    assert payload["error"] == "unable to process"
    assert payload["answer"].startswith("An error occurred")
    assert payload["sql"] is None
