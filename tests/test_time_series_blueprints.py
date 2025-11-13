"""
Tests for time-series blueprint templates covering advanced ratio and volatility scenarios.
"""

from src.intelligence_loader import (
    IntelligenceLoader,
    BLUEPRINT_TEMPLATES,
)
from src.template_metadata import TemplateMetadataStore


BLUEPRINT_IDS = {
    "roe_consecutive_streak_blueprint",
    "equity_to_assets_trend_blueprint",
    "operating_cfo_volatility_blueprint",
    "loan_loss_provision_trend_blueprint",
}


def test_blueprint_templates_registered():
    loader = IntelligenceLoader(use_phase_0_only=False)
    template_ids = {template.template_id for template in loader.get_all_templates()}
    for template_id in BLUEPRINT_IDS:
        assert (
            template_id in template_ids
        ), f"{template_id} should be registered in IntelligenceLoader"


def test_blueprint_sql_contains_key_tags():
    sql_lookup = {
        template.template_id: template.sql_template for template in BLUEPRINT_TEMPLATES
    }
    assert "NetIncomeLoss" in sql_lookup["roe_consecutive_streak_blueprint"]
    assert "StockholdersEquity" in sql_lookup["equity_to_assets_trend_blueprint"]
    assert (
        "NetCashProvidedByUsedInOperatingActivities"
        in sql_lookup["operating_cfo_volatility_blueprint"]
    )
    assert (
        "ProvisionForLoanAndLeaseLosses"
        in sql_lookup["loan_loss_provision_trend_blueprint"]
    )


def test_blueprint_metadata_available():
    metadata_store = TemplateMetadataStore()
    for template_id in BLUEPRINT_IDS:
        metadata = metadata_store.get_metadata(template_id)
        assert metadata is not None, f"{template_id} metadata should be available"
        assert metadata.returns_multiple_rows is True


def test_match_pattern_routes_to_blueprints():
    loader = IntelligenceLoader(use_phase_0_only=False)

    roe_question = (
        "Which large US banks maintained ROE above 12% for three consecutive years "
        "between 2021 and 2023?"
    )
    match = loader.match_pattern(roe_question)
    assert match.template is not None
    assert match.template.template_id == "roe_consecutive_streak_blueprint"

    equity_assets_question = (
        "Track the equity-to-total-assets ratio for JPMorgan, Bank of America, "
        "Citigroup, and Wells Fargo from 2019 to 2024."
    )
    match = loader.match_pattern(equity_assets_question)
    assert match.template is not None
    assert match.template.template_id == "equity_to_assets_trend_blueprint"

    volatility_question = (
        "Show quarterly operating cash flow volatility (coefficient of variation) "
        "for Financial sector companies from 2021 to 2023."
    )
    match = loader.match_pattern(volatility_question)
    assert match.template is not None
    assert match.template.template_id == "operating_cfo_volatility_blueprint"
