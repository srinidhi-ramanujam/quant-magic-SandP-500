"""
XBRL Tag Mapper - Map business terms to XBRL tags.

This module provides flexible mapping between common financial terminology
and XBRL taxonomy tags, handling synonyms and variations.
"""

from typing import List, Dict, Optional
from src.telemetry import get_logger


# Comprehensive mapping of business terms to XBRL tags
METRIC_TO_XBRL: Dict[str, List[str]] = {
    # Revenue synonyms
    "revenue": ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "revenues": ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "sales": ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "turnover": ["Revenues", "SalesRevenueNet"],
    "total revenue": ["Revenues", "SalesRevenueNet"],
    "gross revenue": ["Revenues"],
    
    # Assets
    "assets": ["Assets"],
    "total assets": ["Assets"],
    "current assets": ["AssetsCurrent"],
    "noncurrent assets": ["AssetsNoncurrent"],
    "fixed assets": ["PropertyPlantAndEquipmentNet"],
    "intangible assets": ["IntangibleAssetsNetExcludingGoodwill", "Goodwill"],
    "cash": ["Cash", "CashAndCashEquivalentsAtCarryingValue"],
    "cash and equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "accounts receivable": ["AccountsReceivableNetCurrent"],
    "receivables": ["AccountsReceivableNetCurrent"],
    "inventory": ["InventoryNet"],
    
    # Liabilities
    "liabilities": ["Liabilities"],
    "total liabilities": ["Liabilities"],
    "current liabilities": ["LiabilitiesCurrent"],
    "noncurrent liabilities": ["LiabilitiesNoncurrent"],
    "long term liabilities": ["LiabilitiesNoncurrent"],
    "debt": ["LongTermDebt", "DebtCurrent"],
    "long term debt": ["LongTermDebt"],
    "short term debt": ["DebtCurrent"],
    "current debt": ["DebtCurrent"],
    "accounts payable": ["AccountsPayableCurrent"],
    "payables": ["AccountsPayableCurrent"],
    
    # Equity
    "equity": ["StockholdersEquity"],
    "stockholders equity": ["StockholdersEquity"],
    "shareholders equity": ["StockholdersEquity"],
    "total equity": ["StockholdersEquity"],
    "common stock": ["CommonStockValue"],
    "retained earnings": ["RetainedEarningsAccumulatedDeficit"],
    
    # Income Statement - Revenue & Income
    "net income": ["NetIncomeLoss"],
    "net income loss": ["NetIncomeLoss"],
    "profit": ["NetIncomeLoss"],
    "net profit": ["NetIncomeLoss"],
    "earnings": ["NetIncomeLoss"],
    "net earnings": ["NetIncomeLoss"],
    "income": ["NetIncomeLoss"],
    "gross profit": ["GrossProfit"],
    "operating income": ["OperatingIncomeLoss"],
    "operating profit": ["OperatingIncomeLoss"],
    "ebit": ["OperatingIncomeLoss"],
    "income before tax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
    "pretax income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
    
    # Income Statement - Expenses
    "cost of revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "cost of goods sold": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "cogs": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "operating expenses": ["OperatingExpenses"],
    "research and development": ["ResearchAndDevelopmentExpense"],
    "r&d": ["ResearchAndDevelopmentExpense"],
    "selling general administrative": ["SellingGeneralAndAdministrativeExpense"],
    "sg&a": ["SellingGeneralAndAdministrativeExpense"],
    "interest expense": ["InterestExpense"],
    "depreciation": ["Depreciation", "DepreciationDepletionAndAmortization"],
    "amortization": ["AmortizationOfIntangibleAssets", "DepreciationDepletionAndAmortization"],
    "tax expense": ["IncomeTaxExpenseBenefit"],
    "income tax": ["IncomeTaxExpenseBenefit"],
    
    # Cash Flow Statement
    "operating cash flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "cash from operations": ["NetCashProvidedByUsedInOperatingActivities"],
    "investing cash flow": ["NetCashProvidedByUsedInInvestingActivities"],
    "cash from investing": ["NetCashProvidedByUsedInInvestingActivities"],
    "financing cash flow": ["NetCashProvidedByUsedInFinancingActivities"],
    "cash from financing": ["NetCashProvidedByUsedInFinancingActivities"],
    "free cash flow": ["NetCashProvidedByUsedInOperatingActivities"],  # Note: FCF = OCF - CapEx, calculated
    "capital expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "dividends paid": ["PaymentsOfDividends"],
    
    # Per Share Metrics
    "earnings per share": ["EarningsPerShareBasic", "EarningsPerShareDiluted"],
    "eps": ["EarningsPerShareBasic", "EarningsPerShareDiluted"],
    "basic eps": ["EarningsPerShareBasic"],
    "diluted eps": ["EarningsPerShareDiluted"],
    "book value per share": ["CommonStockValue"],  # Requires calculation
    "dividend per share": ["CommonStockDividendsPerShareDeclared"],
    
    # Shares Outstanding
    "shares outstanding": ["CommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"],
    "common shares": ["CommonStockSharesOutstanding"],
    "weighted average shares": ["WeightedAverageNumberOfSharesOutstandingBasic"],
}


# Additional context-specific mappings
RATIO_COMPONENT_MAPPING: Dict[str, Dict[str, List[str]]] = {
    "roe": {
        "numerator": ["NetIncomeLoss"],
        "denominator": ["StockholdersEquity"],
    },
    "roa": {
        "numerator": ["NetIncomeLoss"],
        "denominator": ["Assets"],
    },
    "current_ratio": {
        "numerator": ["AssetsCurrent"],
        "denominator": ["LiabilitiesCurrent"],
    },
    "quick_ratio": {
        "numerator": ["AssetsCurrent"],  # Minus inventory in calculation
        "denominator": ["LiabilitiesCurrent"],
    },
    "debt_to_equity": {
        "numerator": ["LongTermDebt", "DebtCurrent"],
        "denominator": ["StockholdersEquity"],
    },
    "debt_to_assets": {
        "numerator": ["LongTermDebt", "DebtCurrent"],
        "denominator": ["Assets"],
    },
    "gross_margin": {
        "numerator": ["GrossProfit"],
        "denominator": ["Revenues"],
    },
    "operating_margin": {
        "numerator": ["OperatingIncomeLoss"],
        "denominator": ["Revenues"],
    },
    "net_margin": {
        "numerator": ["NetIncomeLoss"],
        "denominator": ["Revenues"],
    },
    "asset_turnover": {
        "numerator": ["Revenues"],
        "denominator": ["Assets"],
    },
}


class XBRLMapper:
    """Map business terminology to XBRL tags with synonym support."""
    
    def __init__(self):
        """Initialize XBRL mapper."""
        self.logger = get_logger()
        self.metric_to_xbrl = METRIC_TO_XBRL
        self.ratio_components = RATIO_COMPONENT_MAPPING
        
    def map_metric_to_tags(self, metric: str) -> List[str]:
        """
        Map a business metric term to XBRL tag(s).
        
        Args:
            metric: Business term (e.g., "revenue", "net income", "total assets")
            
        Returns:
            List of XBRL tags, ordered by preference (most common first)
            Empty list if no mapping found
        """
        metric_lower = metric.lower().strip()
        
        # Direct lookup
        if metric_lower in self.metric_to_xbrl:
            tags = self.metric_to_xbrl[metric_lower]
            self.logger.debug(f"Mapped '{metric}' to tags: {tags}")
            return tags
        
        # Partial match (search for metric within keys)
        for key, tags in self.metric_to_xbrl.items():
            if metric_lower in key or key in metric_lower:
                self.logger.debug(f"Partial match: '{metric}' -> '{key}' -> {tags}")
                return tags
        
        self.logger.warning(f"No XBRL tag mapping found for metric: '{metric}'")
        return []
    
    def get_ratio_components(self, ratio_name: str) -> Optional[Dict[str, List[str]]]:
        """
        Get numerator and denominator tags for a financial ratio.
        
        Args:
            ratio_name: Name of ratio (e.g., "roe", "current_ratio", "debt_to_equity")
            
        Returns:
            Dictionary with 'numerator' and 'denominator' tag lists, or None if not found
        """
        ratio_lower = ratio_name.lower().strip().replace(" ", "_").replace("-", "_")
        
        if ratio_lower in self.ratio_components:
            return self.ratio_components[ratio_lower]
        
        self.logger.warning(f"No ratio component mapping found for: '{ratio_name}'")
        return None
    
    def get_best_tag_for_company(
        self, 
        cik: str, 
        tag_variants: List[str],
        query_engine=None
    ) -> Optional[str]:
        """
        Find the best XBRL tag for a specific company from variants.
        
        Some companies use different tag variants. This method checks which
        tag actually has data for the given company.
        
        Args:
            cik: Company CIK identifier
            tag_variants: List of possible XBRL tags
            query_engine: Optional QueryEngine instance to check data availability
            
        Returns:
            Best matching tag with data, or first tag if query_engine not provided
        """
        if not tag_variants:
            return None
        
        # If no query engine provided, return first (most common) tag
        if query_engine is None:
            return tag_variants[0]
        
        # Check which tags have data for this company
        for tag in tag_variants:
            try:
                result = query_engine.execute(
                    f"SELECT COUNT(*) as cnt FROM num WHERE cik = '{cik}' AND tag = '{tag}' LIMIT 1"
                )
                if result and len(result) > 0 and result[0]['cnt'] > 0:
                    self.logger.debug(f"Found data for CIK {cik} with tag: {tag}")
                    return tag
            except Exception as e:
                self.logger.debug(f"Error checking tag {tag} for CIK {cik}: {e}")
                continue
        
        # Fallback to first tag
        self.logger.debug(f"No data found for CIK {cik}, using first tag: {tag_variants[0]}")
        return tag_variants[0]
    
    def normalize_metric_name(self, metric: str) -> str:
        """
        Normalize a metric name to a standard form.
        
        Args:
            metric: Raw metric name from question
            
        Returns:
            Normalized metric name
        """
        metric_lower = metric.lower().strip()
        
        # Remove common filler words
        filler_words = ["the", "total", "company's", "company", "latest", "current", "most recent"]
        for word in filler_words:
            metric_lower = metric_lower.replace(word, "").strip()
        
        # Normalize punctuation
        metric_lower = metric_lower.replace("'s", "").replace("'", "")
        
        return metric_lower


# Global mapper instance
_mapper: Optional[XBRLMapper] = None


def get_xbrl_mapper() -> XBRLMapper:
    """Get the global XBRL mapper instance."""
    global _mapper
    if _mapper is None:
        _mapper = XBRLMapper()
    return _mapper

