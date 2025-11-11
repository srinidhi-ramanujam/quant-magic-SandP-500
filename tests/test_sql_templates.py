"""
Execute representative SQL templates against DuckDB to ensure they are schema-compatible.
"""

import pandas as pd
import pytest

from src.query_engine import QueryEngine


TEMPLATE_PATH = "data/parquet/query_intelligence.parquet"
TEMPLATE_DF = pd.read_parquet(TEMPLATE_PATH).set_index("template_id")
DEFAULT_TEMPLATE_PARAMS = {"rank": "1"}


TEMPLATE_CASES = {
    "company_headquarters": {"company": "Apple"},
    "company_incorporation": {"company": "Apple"},
    "companies_by_hq_state": {"state": "CA"},
    "state_with_most_headquarters": {},
    "latest_revenue": {"company": "Apple"},
    "latest_assets": {"company": "Apple"},
    "latest_equity": {"company": "Apple"},
    "latest_net_income": {"company": "Apple"},
    "companies_revenue_above_threshold": {"threshold": "10000000000"},
    "latest_current_ratio": {"company": "Apple"},
    "latest_debt_to_equity": {"company": "Apple"},
    "revenue_yoy_growth": {
        "company": "Apple",
        "start_year": "2020",
        "end_year": "2024",
    },
    "revenue_trend_multi_year": {"company": "Apple", "start_year": "2019"},
    "quarterly_revenue_trend": {"company": "Apple", "start_date": "2020-01-01"},
    "roe_trend_multi_year": {"company": "Apple", "start_year": "2019"},
    "net_margin_trend": {"company": "Apple", "start_year": "2019"},
    "operating_margin_quarterly": {"company": "Apple", "start_date": "2020-01-01"},
}


def render_template(template_id: str, params: dict[str, str]) -> str:
    sql = TEMPLATE_DF.loc[template_id, "sql_template"]
    for key, value in params.items():
        sql = sql.replace(f"{{{key}}}", value)
    for key, value in DEFAULT_TEMPLATE_PARAMS.items():
        placeholder = f"{{{key}}}"
        if placeholder in sql:
            sql = sql.replace(placeholder, value)
    return sql


@pytest.fixture(scope="module")
def query_engine():
    qe = QueryEngine()
    try:
        yield qe
    finally:
        qe.close()


@pytest.mark.parametrize("template_id, params", TEMPLATE_CASES.items())
def test_template_executes_without_error(template_id, params, query_engine):
    sql = render_template(template_id, params)
    result = query_engine.execute(sql)
    assert result is not None
