"""
Entity Extractor - Extract entities from natural language questions.

For Phase 0, uses deterministic pattern matching (no LLM).
Extracts: companies, metrics, sectors, time periods, question type.
"""

import re
from typing import List
from src.models import ExtractedEntities
from src.telemetry import get_logger, RequestContext, log_component_timing


# Known sectors (GICS classification)
KNOWN_SECTORS = {
    "information technology",
    "technology",
    "tech",
    "healthcare",
    "health care",
    "health",
    "financials",
    "financial services",
    "finance",
    "consumer discretionary",
    "discretionary",
    "communication services",
    "communications",
    "telecom",
    "industrials",
    "industrial",
    "consumer staples",
    "staples",
    "energy",
    "utilities",
    "real estate",
    "materials",
}

# Known metrics/financial terms
KNOWN_METRICS = {
    "cik",
    "revenue",
    "assets",
    "liabilities",
    "equity",
    "profit",
    "loss",
    "income",
    "earnings",
    "cash",
    "debt",
    "sector",
    "industry",
    "gics",
}

# Question type indicators
QUESTION_TYPES = {
    "count": ["how many", "count", "number of"],
    "lookup": ["what is", "what are", "get", "find", "show me"],
    "comparison": ["compare", "versus", "vs", "difference between"],
    "trend": ["trend", "over time", "growth", "change"],
}


class EntityExtractor:
    """Extract entities from questions using deterministic pattern matching."""

    def __init__(self):
        """Initialize entity extractor."""
        self.logger = get_logger()
        self.logger.info("EntityExtractor initialized (deterministic mode)")

    def extract(self, question: str, context: RequestContext) -> ExtractedEntities:
        """
        Extract entities from a natural language question.

        Args:
            question: Natural language question
            context: Request context for telemetry

        Returns:
            ExtractedEntities with extracted information
        """
        with log_component_timing(context, "entity_extraction"):
            return self._extract_entities(question)

    def _extract_entities(self, question: str) -> ExtractedEntities:
        """Internal extraction logic."""
        question_lower = question.lower().strip()

        # Extract each entity type
        companies = self._extract_companies(question)
        metrics = self._extract_metrics(question_lower)
        sectors = self._extract_sectors(question_lower)
        time_periods = self._extract_time_periods(question)
        question_type = self._determine_question_type(question_lower)

        # Calculate confidence based on what was extracted
        confidence = self._calculate_confidence(
            companies, metrics, sectors, time_periods, question_type
        )

        entities = ExtractedEntities(
            companies=companies,
            metrics=metrics,
            sectors=sectors,
            time_periods=time_periods,
            question_type=question_type,
            confidence=confidence,
        )

        self.logger.debug(
            f"Extracted entities: companies={len(companies)}, "
            f"metrics={len(metrics)}, sectors={len(sectors)}, "
            f"confidence={confidence:.2f}"
        )

        return entities

    def _extract_companies(self, question: str) -> List[str]:
        """
        Extract company names from question.

        Uses capitalization patterns and known company indicators.
        """
        companies = []

        # Pattern 1: Capitalized words (likely company names)
        # Look for sequences of capitalized words
        cap_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+Inc\.?|\s+Corp\.?|\s+Corporation)?)\b"
        matches = re.findall(cap_pattern, question)

        for match in matches:
            # Filter out common question words
            if match.lower() not in ["what", "which", "when", "where", "who", "how"]:
                companies.append(match)

        # Pattern 2: Common company names (case-insensitive shortcuts)
        common_companies = [
            "apple",
            "microsoft",
            "google",
            "alphabet",
            "amazon",
            "meta",
            "facebook",
            "tesla",
            "nvidia",
            "netflix",
            "jpmorgan",
            "jp morgan",
            "goldman sachs",
            "bank of america",
            "wells fargo",
            "walmart",
            "target",
            "costco",
            "exxon",
            "chevron",
            "pfizer",
            "johnson & johnson",
            "merck",
        ]

        question_lower = question.lower()
        for company in common_companies:
            if company in question_lower:
                # Capitalize properly
                capitalized = " ".join(word.capitalize() for word in company.split())
                if capitalized not in companies:
                    companies.append(capitalized)

        return list(set(companies))  # Remove duplicates

    def _extract_metrics(self, question_lower: str) -> List[str]:
        """Extract financial metrics from question."""
        metrics = []

        for metric in KNOWN_METRICS:
            if metric in question_lower:
                metrics.append(metric.upper() if metric == "cik" else metric.title())

        return list(set(metrics))

    def _extract_sectors(self, question_lower: str) -> List[str]:
        """Extract sector names from question."""
        sectors = []

        for sector in KNOWN_SECTORS:
            if sector in question_lower:
                # Normalize to standard GICS sector name
                normalized = self._normalize_sector_name(sector)
                if normalized and normalized not in sectors:
                    sectors.append(normalized)

        return sectors

    def _normalize_sector_name(self, sector: str) -> str:
        """Normalize sector name to standard GICS classification."""
        sector_lower = sector.lower()

        # Map variations to standard names
        mapping = {
            "technology": "Information Technology",
            "tech": "Information Technology",
            "information technology": "Information Technology",
            "healthcare": "Health Care",
            "health care": "Health Care",
            "health": "Health Care",
            "financials": "Financials",
            "financial services": "Financials",
            "finance": "Financials",
            "consumer discretionary": "Consumer Discretionary",
            "discretionary": "Consumer Discretionary",
            "communication services": "Communication Services",
            "communications": "Communication Services",
            "telecom": "Communication Services",
            "industrials": "Industrials",
            "industrial": "Industrials",
            "consumer staples": "Consumer Staples",
            "staples": "Consumer Staples",
            "energy": "Energy",
            "utilities": "Utilities",
            "real estate": "Real Estate",
            "materials": "Materials",
        }

        return mapping.get(sector_lower, sector.title())

    def _extract_time_periods(self, question: str) -> List[str]:
        """Extract time periods from question."""
        periods = []

        # Pattern 1: Year (YYYY)
        year_pattern = r"\b(20\d{2}|19\d{2})\b"
        years = re.findall(year_pattern, question)
        periods.extend(years)

        # Pattern 2: Quarter (Q1, Q2, Q3, Q4)
        quarter_pattern = r"\b(Q[1-4])\b"
        quarters = re.findall(quarter_pattern, question, re.IGNORECASE)
        periods.extend([q.upper() for q in quarters])

        # Pattern 3: Fiscal year (FY2023, FY 2023)
        fy_pattern = r"\b(FY\s*20\d{2})\b"
        fiscal_years = re.findall(fy_pattern, question, re.IGNORECASE)
        periods.extend([fy.replace(" ", "") for fy in fiscal_years])

        return list(set(periods))

    def _determine_question_type(self, question_lower: str) -> str:
        """Determine the type of question being asked."""
        # Check each question type pattern
        for qtype, indicators in QUESTION_TYPES.items():
            for indicator in indicators:
                if indicator in question_lower:
                    return qtype

        # Default to lookup if no specific type identified
        return "lookup"

    def _calculate_confidence(
        self,
        companies: List[str],
        metrics: List[str],
        sectors: List[str],
        time_periods: List[str],
        question_type: str,
    ) -> float:
        """
        Calculate confidence score based on extracted entities.

        Higher confidence if we extracted key entities.
        """
        confidence = 0.5  # Base confidence

        # Boost confidence for each entity type found
        if companies:
            confidence += 0.15
        if metrics:
            confidence += 0.15
        if sectors:
            confidence += 0.1
        if time_periods:
            confidence += 0.05
        if question_type != "lookup":
            confidence += 0.05

        # Cap at 1.0
        return min(confidence, 1.0)


# Global instance
_extractor: EntityExtractor = None


def get_entity_extractor() -> EntityExtractor:
    """Get the global entity extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor
