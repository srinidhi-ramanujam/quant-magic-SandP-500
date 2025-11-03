"""
Intelligence Loader - Load and match query intelligence templates.

For Phase 0, we focus on 3 simple templates:
1. Sector count: "How many companies in X sector?"
2. Company CIK lookup: "What is X's CIK?"
3. Company sector lookup: "What sector is X in?"
"""

import re
from typing import List, Optional, Dict
import pandas as pd

from src.config import get_parquet_path
from src.models import QueryTemplate, IntelligenceMatch
from src.telemetry import get_logger


# Phase 0 templates - simple patterns for PoC
PHASE_0_TEMPLATES = [
    QueryTemplate(
        template_id="sector_count",
        name="Count companies by sector",
        pattern=r"how many .*(companies|firms|corporations).* (in|from) .* (sector|industry)",
        sql_template="SELECT COUNT(*) as count FROM companies WHERE UPPER(gics_sector) LIKE UPPER('%{sector}%')",
        parameters=["sector"],
        description="Count number of companies in a given sector",
    ),
    QueryTemplate(
        template_id="company_cik",
        name="Get company CIK",
        pattern=r"what (is|are) .* cik",
        sql_template="SELECT cik, name FROM companies WHERE UPPER(name) LIKE UPPER('%{company}%') LIMIT 1",
        parameters=["company"],
        description="Look up a company's CIK identifier",
    ),
    QueryTemplate(
        template_id="company_sector",
        name="Get company sector",
        pattern=r"what sector (is|does) .* (in|belong)",
        sql_template="SELECT name, gics_sector FROM companies WHERE UPPER(name) LIKE UPPER('%{company}%') LIMIT 1",
        parameters=["company"],
        description="Find which sector a company belongs to",
    ),
]


class IntelligenceLoader:
    """Load and manage query intelligence templates."""

    def __init__(self, use_phase_0_only: bool = True):
        """
        Initialize intelligence loader.

        Args:
            use_phase_0_only: If True, only use Phase 0 templates (default).
                             If False, also load templates from parquet files.
        """
        self.logger = get_logger()
        self.templates: List[QueryTemplate] = []
        self.use_phase_0_only = use_phase_0_only

        # Load templates
        self._load_templates()

        self.logger.info(f"Loaded {len(self.templates)} query templates")

    def _load_templates(self):
        """Load query templates from parquet and Phase 0 templates."""
        # Always load Phase 0 templates first
        self.templates.extend(PHASE_0_TEMPLATES)

        # Optionally load advanced templates from parquet
        if not self.use_phase_0_only:
            try:
                parquet_path = get_parquet_path("query_intelligence.parquet")
                if parquet_path.exists():
                    df = pd.read_parquet(parquet_path)

                    for _, row in df.iterrows():
                        template = QueryTemplate(
                            template_id=row["template_id"],
                            name=row.get("intent_category", ""),
                            pattern=row["natural_language_pattern"],
                            sql_template=row["sql_template"],
                            parameters=self._extract_parameters(row["sql_template"]),
                            description=f"{row.get('tactical_strategic', '')} {row.get('intent_category', '')}",
                        )
                        self.templates.append(template)

                    self.logger.info(f"Loaded {len(df)} templates from parquet")

            except Exception as e:
                self.logger.warning(f"Could not load templates from parquet: {e}")

    def _extract_parameters(self, sql_template: str) -> List[str]:
        """Extract parameter names from SQL template."""
        # Find all {parameter} patterns
        params = re.findall(r"\{(\w+)\}", sql_template)
        return list(set(params))  # Remove duplicates

    def get_all_templates(self) -> List[QueryTemplate]:
        """Get all loaded templates."""
        return self.templates.copy()

    def get_template_by_id(self, template_id: str) -> Optional[QueryTemplate]:
        """
        Get a specific template by ID.

        Args:
            template_id: Template identifier

        Returns:
            QueryTemplate if found, None otherwise
        """
        for template in self.templates:
            if template.template_id == template_id:
                return template

        self.logger.warning(f"Template not found: {template_id}")
        return None

    def match_pattern(
        self, question: str, min_confidence: float = 0.5
    ) -> IntelligenceMatch:
        """
        Match a question to a template using pattern matching.

        Args:
            question: Natural language question
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            IntelligenceMatch with best matching template
        """
        self.logger.debug(f"Matching question: {question}")

        # Normalize question
        question_lower = question.lower().strip()

        best_match = None
        best_confidence = 0.0
        best_params = {}

        for template in self.templates:
            # Try regex pattern match
            pattern = template.pattern.lower()
            match = re.search(pattern, question_lower, re.IGNORECASE)

            if match:
                # Calculate confidence based on match quality
                confidence = 0.8  # Base confidence for regex match

                # Extract parameters from question
                params = self._extract_template_parameters(question, template)

                # Boost confidence if parameters extracted successfully
                if len(params) == len(template.parameters):
                    confidence = 0.95

                if confidence > best_confidence:
                    best_match = template
                    best_confidence = confidence
                    best_params = params

        # Build intelligence match result
        if best_match and best_confidence >= min_confidence:
            self.logger.info(
                f"Matched template '{best_match.template_id}' "
                f"with confidence {best_confidence:.2f}"
            )

            return IntelligenceMatch(
                template=best_match,
                match_confidence=best_confidence,
                matched_parameters=best_params,
                fallback_to_llm=False,
            )
        else:
            self.logger.info(
                f"No template match found (best: {best_confidence:.2f}), will fallback to LLM"
            )

            return IntelligenceMatch(
                template=None,
                match_confidence=0.0,
                matched_parameters={},
                fallback_to_llm=True,
            )

    def _extract_template_parameters(
        self, question: str, template: QueryTemplate
    ) -> Dict[str, str]:
        """
        Extract parameter values from question based on template.

        Args:
            question: Natural language question
            template: Query template

        Returns:
            Dictionary of parameter name -> value
        """
        params = {}
        question_lower = question.lower()

        # Template-specific extraction logic
        if template.template_id == "sector_count":
            # Extract sector name
            # Patterns: "Technology sector", "in Technology", "Healthcare sector"
            sector_patterns = [
                r"(in|from) (the )?([\w\s]+) (sector|industry)",
                r"([\w\s]+) (sector|industry)",
            ]

            for pattern in sector_patterns:
                match = re.search(pattern, question_lower)
                if match:
                    # Get the sector name (group 3 or 1 depending on pattern)
                    sector = (
                        match.group(3) if len(match.groups()) >= 3 else match.group(1)
                    )
                    params["sector"] = sector.strip()
                    break

        elif template.template_id in ["company_cik", "company_sector"]:
            # Extract company name
            # Remove common words and extract likely company name
            # Patterns: "What is Apple's CIK", "Apple Inc's CIK", "What sector is Microsoft in"

            # Remove question words and punctuation
            cleaned = re.sub(
                r"(what|is|are|the|sector|cik|'s|does|belong|to|in)", "", question_lower
            )
            # Remove punctuation
            cleaned = re.sub(r"[?!.,;:]", "", cleaned)
            cleaned = cleaned.strip()

            # Take the remaining text as company name (first significant word/phrase)
            words = cleaned.split()
            if words:
                # Capitalize for better matching
                company = " ".join(words[:3])  # Take first 3 words max
                params["company"] = company.strip()

        self.logger.debug(f"Extracted parameters: {params}")
        return params


# Global loader instance
_loader: Optional[IntelligenceLoader] = None


def get_intelligence_loader(use_phase_0_only: bool = True) -> IntelligenceLoader:
    """Get the global intelligence loader instance."""
    global _loader
    if _loader is None:
        _loader = IntelligenceLoader(use_phase_0_only=use_phase_0_only)
    return _loader
