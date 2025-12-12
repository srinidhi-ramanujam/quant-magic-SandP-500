"""
Template Metadata - Pydantic models and utilities for template metadata.

This module defines the metadata structure for SQL templates and provides
utilities for loading and managing template metadata for LLM-based selection.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
import pandas as pd
from pathlib import Path

from src.config import get_parquet_path
from src.telemetry import get_logger


class TemplateMetadata(BaseModel):
    """Metadata for LLM-based template discovery and selection."""

    # Core identification
    template_id: str = Field(description="Unique template identifier")
    name: str = Field(description="Human-readable template name")
    description: str = Field(
        description="Detailed description of what this template does"
    )

    # Categorization
    category: str = Field(
        description="Primary category: company_lookup, sector_analysis, geographic, financial_metrics, financial_ratios, time_series_revenue, time_series_profitability"
    )
    subcategory: Optional[str] = Field(
        None, description="Optional subcategory for finer grouping"
    )

    # Requirements - what entities/parameters are needed
    requires_company: bool = Field(
        description="Does this template need a company name/CIK?"
    )
    requires_sector: bool = Field(
        default=False, description="Does this template need a sector?"
    )
    requires_time: bool = Field(
        default=False, description="Does this template need time period?"
    )
    requires_threshold: bool = Field(
        default=False, description="Does this template need numeric threshold?"
    )

    # Capabilities - what this template can do
    metric_type: Optional[str] = Field(
        None,
        description="Type of metric: revenue, assets, equity, roe, net_margin, etc.",
    )
    ratio_type: Optional[str] = Field(
        None, description="Type of ratio: profitability, liquidity, leverage"
    )
    time_granularity: Optional[str] = Field(
        None, description="Time granularity: annual, quarterly, monthly"
    )

    # Output characteristics
    answer_type: str = Field(
        description="Type of answer: single_fact, single_number, percentage, ratio, list, table, time_series_table"
    )
    returns_multiple_rows: bool = Field(
        description="Whether this returns multiple rows (vs single value/row)"
    )

    # Complexity
    sql_complexity: str = Field(
        description="SQL complexity level: simple, moderate, high"
    )
    estimated_execution_time: str = Field(
        description="Estimated execution time: <1s, 1-3s, 3-5s"
    )

    # Pattern matching
    keywords: List[str] = Field(description="Key terms that indicate this template")
    example_questions: List[str] = Field(
        description="Example questions this template can answer"
    )

    # LLM selection hints
    semantic_description: str = Field(
        description="Natural language description for LLM matching - comprehensive explanation of use case"
    )
    when_to_use: str = Field(
        description="Guidance for LLM on when to select this template - specific criteria"
    )
    similar_templates: List[str] = Field(
        default_factory=list, description="IDs of related/similar templates"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "template_id": "latest_revenue",
                "name": "Get most recent revenue",
                "description": "Retrieve the latest annual revenue for a specific company",
                "category": "financial_metrics",
                "subcategory": "income_statement",
                "requires_company": True,
                "requires_sector": False,
                "requires_time": False,
                "requires_threshold": False,
                "metric_type": "revenue",
                "ratio_type": None,
                "time_granularity": None,
                "answer_type": "single_number_with_date",
                "returns_multiple_rows": False,
                "sql_complexity": "moderate",
                "estimated_execution_time": "<1s",
                "keywords": ["revenue", "sales", "latest", "recent", "current"],
                "example_questions": [
                    "What is Apple's most recent revenue?",
                    "Show Microsoft's latest sales",
                ],
                "semantic_description": "Use this template when the user wants to find the most recent annual revenue figure for a specific company. It retrieves the latest value from the num table.",
                "when_to_use": "Select this template when: (1) User asks about revenue/sales, (2) Wants latest/most recent/current value, (3) Specifies a company name, (4) No time range specified",
                "similar_templates": [
                    "latest_assets",
                    "latest_net_income",
                    "revenue_trend_multi_year",
                ],
            }
        }


ADDITIONAL_TEMPLATE_METADATA: List[TemplateMetadata] = [
    TemplateMetadata(
        template_id="roe_consecutive_streak_blueprint",
        name="ROE consecutive streak blueprint",
        description="Blueprint for identifying companies whose return on equity stays above a threshold across consecutive fiscal years.",
        category="financial_ratios",
        subcategory="profitability",
        requires_company=False,
        requires_sector=False,
        requires_time=True,
        requires_threshold=True,
        metric_type="roe",
        ratio_type="profitability",
        time_granularity="annual",
        answer_type="time_series_table",
        returns_multiple_rows=True,
        sql_complexity="high",
        estimated_execution_time="1-3s",
        keywords=["roe", "return on equity", "consecutive", "streak", "threshold"],
        example_questions=[
            "Which large US banks maintained ROE above 12% for three consecutive years between 2021 and 2023?"
        ],
        semantic_description=(
            "Guidance for computing ROE (NetIncomeLoss divided by StockholdersEquity) and applying window logic to enforce consecutive-year streaks."
        ),
        when_to_use=(
            "Use when the user references ROE thresholds across consecutive fiscal years or streak analysis."
        ),
        similar_templates=[
            "energy_roe_threshold_detector",
            "roe_revenue_divergence",
            "semiconductor_roe_trend",
        ],
    ),
    TemplateMetadata(
        template_id="equity_to_assets_trend_blueprint",
        name="Equity-to-assets ratio blueprint",
        description="Blueprint for tracking stockholders' equity relative to total assets across companies and fiscal years.",
        category="financial_ratios",
        subcategory="leverage",
        requires_company=False,
        requires_sector=False,
        requires_time=True,
        requires_threshold=False,
        metric_type="equity_to_assets_ratio",
        ratio_type="leverage",
        time_granularity="annual",
        answer_type="time_series_table",
        returns_multiple_rows=True,
        sql_complexity="moderate",
        estimated_execution_time="1-3s",
        keywords=["equity to assets", "balance sheet ratio", "capital adequacy"],
        example_questions=[
            "Track the equity-to-total-assets ratio for JPMorgan, Bank of America, Citigroup, and Wells Fargo from 2019 to 2024."
        ],
        semantic_description=(
            "Shows how to combine StockholdersEquity and Assets tags for cohorts, with hooks for optional sector or geography filters."
        ),
        when_to_use="Use when the user requests equity-to-assets ratios across a multi-year window.",
        similar_templates=[
            "current_ratio_trend",
            "net_debt_to_ebitda_trend",
            "asset_turnover_trend",
        ],
    ),
    TemplateMetadata(
        template_id="operating_cfo_volatility_blueprint",
        name="Operating cash flow volatility blueprint",
        description="Blueprint for measuring the volatility (coefficient of variation) of quarterly operating cash flow.",
        category="cash_flow",
        subcategory="quality_of_earnings",
        requires_company=False,
        requires_sector=False,
        requires_time=True,
        requires_threshold=False,
        metric_type="operating_cash_flow",
        ratio_type="volatility",
        time_granularity="quarterly",
        answer_type="time_series_table",
        returns_multiple_rows=True,
        sql_complexity="high",
        estimated_execution_time="1-3s",
        keywords=["operating cash flow", "volatility", "coefficient of variation"],
        example_questions=[
            "Show quarterly operating cash flow volatility (coefficient of variation) for Financial sector companies from 2021 to 2023."
        ],
        semantic_description=(
            "Illustrates how to gather quarterly NetCashProvidedByUsedInOperatingActivities values and compute STDDEV/AVG for volatility analysis."
        ),
        when_to_use="Use when the user explicitly mentions volatility or coefficient of variation on operating cash flow.",
        similar_templates=[
            "top_tech_cfo_trend",
            "cfo_to_net_income_trend",
        ],
    ),
    TemplateMetadata(
        template_id="loan_loss_provision_trend_blueprint",
        name="Loan-loss provision trend blueprint",
        description="Blueprint for extracting quarterly loan-loss provision expense trends for specified banks.",
        category="financial_metrics",
        subcategory="credit_quality",
        requires_company=False,
        requires_sector=False,
        requires_time=True,
        requires_threshold=False,
        metric_type="loan_loss_provision",
        ratio_type=None,
        time_granularity="quarterly",
        answer_type="time_series_table",
        returns_multiple_rows=True,
        sql_complexity="moderate",
        estimated_execution_time="1-3s",
        keywords=["loan loss provision", "credit quality", "banks", "allowance"],
        example_questions=[
            "Track quarterly loan-loss provision expense for JPMorgan, Bank of America, Citigroup, and Wells Fargo across 2018-2023 to highlight spikes and normalization."
        ],
        semantic_description=(
            "Shows how to pull ProvisionForLoanAndLeaseLosses facts for major banks across quarters."
        ),
        when_to_use="Use when the user requests loan-loss or credit reserve trends over time.",
        similar_templates=[
            "operating_cfo_volatility_blueprint",
            "roe_consecutive_streak_blueprint",
        ],
    ),
]


class TemplateMetadataStore:
    """Store and manage template metadata."""

    def __init__(self, metadata_path: Optional[Path] = None):
        """
        Initialize metadata store.

        Args:
            metadata_path: Path to template_metadata.parquet file. If None, uses default.
        """
        self.logger = get_logger()

        if metadata_path is None:
            metadata_path = get_parquet_path("template_metadata.parquet")

        self.metadata_path = metadata_path
        self.metadata_df: Optional[pd.DataFrame] = None
        self.metadata_dict: Dict[str, TemplateMetadata] = {}

        if metadata_path.exists():
            self._load_metadata()
        else:
            self.logger.warning(f"Template metadata file not found: {metadata_path}")

    def _load_metadata(self):
        """Load metadata from parquet file."""
        try:
            self.metadata_df = pd.read_parquet(self.metadata_path)

            # Convert to Pydantic models
            for _, row in self.metadata_df.iterrows():
                template_id = row["template_id"]

                # Parse list fields from JSON strings if needed
                metadata_dict = row.to_dict()

                # Ensure list fields are actually lists
                for list_field in [
                    "keywords",
                    "example_questions",
                    "similar_templates",
                ]:
                    if list_field in metadata_dict and isinstance(
                        metadata_dict[list_field], str
                    ):
                        import json

                        metadata_dict[list_field] = json.loads(
                            metadata_dict[list_field]
                        )

                metadata = TemplateMetadata(**metadata_dict)
                self.metadata_dict[template_id] = metadata

            for metadata in ADDITIONAL_TEMPLATE_METADATA:
                if metadata.template_id not in self.metadata_dict:
                    self.metadata_dict[metadata.template_id] = metadata

            self.logger.info(f"Loaded metadata for {len(self.metadata_dict)} templates")

        except Exception as e:
            self.logger.error(f"Error loading template metadata: {e}")
            raise

    def get_metadata(self, template_id: str) -> Optional[TemplateMetadata]:
        """
        Get metadata for a specific template.

        Args:
            template_id: Template identifier

        Returns:
            TemplateMetadata or None if not found
        """
        return self.metadata_dict.get(template_id)

    def get_all_metadata(self) -> List[TemplateMetadata]:
        """Get metadata for all templates."""
        return list(self.metadata_dict.values())

    def filter_by_requirements(
        self,
        requires_company: Optional[bool] = None,
        requires_sector: Optional[bool] = None,
        requires_time: Optional[bool] = None,
        requires_threshold: Optional[bool] = None,
    ) -> List[TemplateMetadata]:
        """
        Filter templates by their requirements.

        Args:
            requires_company: Filter by company requirement
            requires_sector: Filter by sector requirement
            requires_time: Filter by time requirement
            requires_threshold: Filter by threshold requirement

        Returns:
            List of matching templates
        """
        filtered = self.get_all_metadata()

        if requires_company is not None:
            filtered = [t for t in filtered if t.requires_company == requires_company]

        if requires_sector is not None:
            filtered = [t for t in filtered if t.requires_sector == requires_sector]

        if requires_time is not None:
            filtered = [t for t in filtered if t.requires_time == requires_time]

        if requires_threshold is not None:
            filtered = [
                t for t in filtered if t.requires_threshold == requires_threshold
            ]

        return filtered

    def filter_by_category(self, category: str) -> List[TemplateMetadata]:
        """
        Filter templates by category.

        Args:
            category: Category name

        Returns:
            List of templates in that category
        """
        return [t for t in self.get_all_metadata() if t.category == category]

    def search_by_keywords(self, keywords: List[str]) -> List[TemplateMetadata]:
        """
        Search templates by keywords.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of templates matching any keyword
        """
        keywords_lower = [k.lower() for k in keywords]
        matching = []

        for template in self.get_all_metadata():
            template_keywords = [k.lower() for k in template.keywords]
            if any(kw in template_keywords for kw in keywords_lower):
                matching.append(template)

        return matching


# Global metadata store instance
_metadata_store: Optional[TemplateMetadataStore] = None


def get_metadata_store() -> TemplateMetadataStore:
    """Get the global template metadata store instance."""
    global _metadata_store
    if _metadata_store is None:
        _metadata_store = TemplateMetadataStore()
    return _metadata_store


def load_template_metadata(
    metadata_path: Optional[Path] = None,
) -> TemplateMetadataStore:
    """
    Load template metadata from parquet file.

    Args:
        metadata_path: Path to metadata file, or None for default location

    Returns:
        TemplateMetadataStore instance
    """
    global _metadata_store
    _metadata_store = TemplateMetadataStore(metadata_path)
    return _metadata_store
