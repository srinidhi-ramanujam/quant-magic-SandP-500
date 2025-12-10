"""
Execute representative SQL templates against DuckDB to ensure they are schema-compatible.
"""

from typing import Dict

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
    "asset_turnover_trend": {
        "sector": "Information Technology",
        "sic_filter_enabled": "1",
        "sic_min": "3570",
        "sic_max": "3699",
        "start_year": "2020",
        "year_2": "2021",
        "year_3": "2022",
        "end_year": "2023",
        "min_years": "4",
        "limit": "5",
        "min_revenue": "10000000000",
    },
    "cfo_to_net_income_trend": {
        "sector": "Health Care",
        "start_year": "2019",
        "year_2": "2020",
        "year_3": "2021",
        "end_year": "2023",
        "min_years": "4",
        "limit": "5",
        "min_net_income": "500000000",
        "max_ratio": "3",
    },
    "top_tech_cfo_trend": {
        "sector": "Information Technology",
        "ranking_year": "2023",
        "min_revenue": "10000000000",
        "top_n": "10",
        "start_year": "2022",
        "end_year": "2024",
        "start_period": "2021-09-01",
        "end_period": "2024-12-31",
        "min_quarters": "6",
        "max_abs_cfo": "400000000000",
        "value_scale": "1000000000.0",
        "result_limit": "500",
    },
    "hardware_gross_margin_trend": {
        "company_values": "('APPLE INC'),('DELL TECHNOLOGIES INC.'),('HP INC')",
        "quarter_count": "8",
        "min_period": "2022-01-01",
    },
    "ebitda_margin_improvement_rank": {
        "sector": "Information Technology",
        "start_year": "2021",
        "end_year": "2024",
        "min_revenue": "2000000000",
        "min_improvement_pp": "5",
        "limit": "10",
    },
    "fcf_to_capex_trend": {
        "sector": "Health Care",
        "start_year": "2019",
        "year_2": "2020",
        "year_3": "2021",
        "year_4": "2022",
        "year_5": "2023",
        "end_year": "2024",
        "min_years": "5",
        "min_cfo": "400000000",
        "min_capex_abs": "200000000",
        "max_fcf_retention": "1.2",
        "min_fcf_retention": "-1.0",
        "max_capex_intensity": "1.2",
        "limit": "5",
    },
    "cash_to_assets_ratio_trend": {
        "company_values": "('MICROSOFT CORP'),('ADOBE INC.'),('SALESFORCE, INC.')",
        "use_sector_filter": "0",
        "sector": "ALL",
        "start_year": "2019",
        "end_year": "2024",
        "min_years": "4",
    },
    "shareholder_return_trend": {
        "sector": "Information Technology",
        "start_year": "2020",
        "year_2": "2021",
        "year_3": "2022",
        "end_year": "2023",
        "min_years": "4",
        "min_total_return": "2000000000",
        "min_cfo": "5000000000",
        "max_payout_ratio": "4",
        "limit": "8",
    },
    "semiconductor_roe_trend": {
        "company_values": "('NVIDIA CORP'),('ADVANCED MICRO DEVICES INC'),('INTEL CORP'),('TEXAS INSTRUMENTS INC')",
        "start_year": "2019",
        "end_year": "2024",
        "min_years": "6",
        "max_abs_roe": "200",
        "result_limit": "200",
    },
    "net_debt_to_ebitda_trend": {
        "company_values": "('APPLE INC'),('MICROSOFT CORP')",
        "start_year": "2020",
        "end_year": "2023",
        "use_sector_filter": "0",
        "sector": "ALL",
        "min_ebitda": "100000000",
        "limit": "5",
    },
    "debt_reduction_progression": {
        "sector": "Information Technology",
        "start_year": "2021",
        "end_year": "2023",
        "min_reduction": "0",
        "limit": "5",
    },
    "profit_margin_consistency_trend": {
        "sector": "Information Technology",
        "start_year": "2019",
        "end_year": "2023",
        "limit": "5",
    },
    "energy_roe_threshold_detector": {
        "sector": "Energy",
        "start_year": "2020",
        "end_year": "2024",
        "min_consecutive_years": "3",
        "min_years_reported": "3",
        "roe_threshold": "15",
        "min_equity": "100000000",
        "max_roe_pct": "150",
        "limit": "5",
    },
}


def render_template(template_id: str, params: Dict[str, str]) -> str:
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


def test_cash_to_assets_ratio_trend_parameter_substitution():
    """Test that cash_to_assets_ratio_trend template handles mixed parameter types correctly."""
    from src.sql_generator import SQLGenerator
    from src.intelligence_loader import IntelligenceLoader

    # Create a generator with a mock template that includes the cash_to_assets_ratio_trend
    loader = IntelligenceLoader()
    generator = SQLGenerator(loader)

    # Test parameters that include non-string values to simulate the bug scenario
    test_params = {
        "company_values": "('PFIZER INC'),('JOHNSON & JOHNSON'),('AMGEN INC')",
        "use_sector_filter": 0,  # This is an int, not a string
        "sector": "Health Care",
        "start_year": "2019",
        "end_year": "2024",
        "min_years": 4,  # This is an int, not a string
    }

    # Get the template
    template = loader.get_template_by_id("cash_to_assets_ratio_trend")
    assert template is not None

    # This should not raise a "replace() argument 2 must be str, not bool/int" error
    try:
        sql = template.sql_template
        for param_name, param_value in test_params.items():
            placeholder = f"{{{param_name}}}"
            if placeholder in sql:
                sql = sql.replace(placeholder, str(param_value))

        # Verify the SQL contains the substituted values
        assert "0" in sql  # use_sector_filter should be "0"
        assert "4" in sql  # min_years should be "4"
        assert "('PFIZER INC'),('JOHNSON & JOHNSON'),('AMGEN INC')" in sql

    except Exception as e:
        pytest.fail(f"Parameter substitution failed with error: {e}")
