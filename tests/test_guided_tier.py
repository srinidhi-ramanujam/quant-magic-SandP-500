"""Regression tests for the guided questions tier."""

import json
from pathlib import Path

import pandas as pd

from src.intelligence_loader import IntelligenceLoader
from src.template_metadata import TemplateMetadataStore


GUIDED_TEMPLATE_IDS = {
    "sector_growth_leaders",
    "sector_margin_trend",
    "sector_fcf_stability",
    "sector_roic_improvers",
    "sector_share_gainers",
    "company_rev_margin_trend",
    "company_fcf_stability",
    "company_peer_margin_compare",
    "company_segment_growth",
    "company_leverage_liquidity",
}


def test_guided_templates_present_in_catalog():
    df = pd.read_parquet("data/parquet/query_intelligence.parquet")
    template_ids = set(df["template_id"])
    missing = GUIDED_TEMPLATE_IDS - template_ids
    assert not missing, f"Missing guided templates in catalog: {missing}"


def test_guided_metadata_loaded():
    store = TemplateMetadataStore()
    missing = [tid for tid in GUIDED_TEMPLATE_IDS if not store.get_metadata(tid)]
    assert not missing, f"Missing guided metadata rows: {missing}"


def test_vector_store_metadata_has_guided_tier():
    path = Path("artifacts/vector_store/templates_metadata.json")
    data = json.loads(path.read_text())
    guided_meta = {item["template_id"]: item.get("metadata", {}) for item in data}
    missing_tier = [
        tid
        for tid in GUIDED_TEMPLATE_IDS
        if tid not in guided_meta or guided_meta[tid].get("tier") != "guided_questions"
    ]
    assert not missing_tier, f"Templates missing guided tier metadata: {missing_tier}"


def test_guided_questions_match_templates():
    loader = IntelligenceLoader(use_phase_0_only=False)

    question_sector = "Which Technology companies lead revenue growth since 2020?"
    match_sector = loader.match_pattern(question_sector)
    assert match_sector.template
    assert match_sector.template.template_id == "sector_growth_leaders"

    question_company = "Show revenue and operating margin trends for Apple since 2020."
    match_company = loader.match_pattern(question_company)
    assert match_company.template
    assert match_company.template.template_id == "company_rev_margin_trend"


def test_all_guided_questions_from_suite_match():
    loader = IntelligenceLoader(use_phase_0_only=False)
    suite = json.loads(Path("evaluation/questions/guided_questions.json").read_text())

    for entry in suite["questions"]:
        match = loader.match_pattern(entry["question"])
        assert match.template, f"No match for guided question {entry['id']}"
        assert (
            match.template.template_id == entry["template_id"]
        ), f"Mismatch for {entry['id']}"


def test_guided_parameters_include_year_windows_and_tier():
    df = pd.read_parquet("data/parquet/query_intelligence.parquet")
    assert "tier" in df.columns, "query_intelligence missing tier column"

    guided_rows = df[df["template_id"].isin(GUIDED_TEMPLATE_IDS)]
    assert not guided_rows.empty
    assert set(guided_rows["tier"]) == {"guided_questions"}

    company_row = guided_rows[guided_rows["template_id"] == "company_rev_margin_trend"]
    params = json.loads(company_row.iloc[0]["parameters"])
    for required in ["company", "start_year", "end_year"]:
        assert required in params, f"Missing {required} in company_rev_margin_trend params"


def test_guided_questions_have_multi_year_and_min_revenue_defaults():
    loader = IntelligenceLoader(use_phase_0_only=False)
    suite = json.loads(Path("evaluation/questions/guided_questions.json").read_text())

    for entry in suite["questions"]:
        match = loader.match_pattern(entry["question"])
        assert match.template, f"No match for guided question {entry['id']}"
        template = match.template
        params = match.matched_parameters

        if "company" in template.parameters:
            assert params.get("company"), f"Missing company for {template.template_id}"

        if "start_year" in template.parameters and "end_year" in template.parameters:
            assert "start_year" in params and "end_year" in params, f"Missing years for {template.template_id}"
            try:
                start = int(params["start_year"])
                end = int(params["end_year"])
            except (ValueError, TypeError):
                raise AssertionError(f"Non-numeric years for {template.template_id}: {params}")
            assert end > start, f"Non-multi-year window for {template.template_id}: {start}->{end}"

        if "min_revenue" in template.parameters:
            assert "min_revenue" in params, f"Missing min_revenue for {template.template_id}"

