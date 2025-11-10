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
from src.entity_extractor import get_company_alias_map, normalize_company_name


# Common currency synonyms to support template parameter extraction.
_CURRENCY_SYNONYMS: Dict[str, List[str]] = {
    "USD": [
        "usd",
        "u.s. dollar",
        "us dollar",
        "u.s. dollars",
        "us dollars",
        "united states dollar",
        "united states dollars",
        "american dollar",
    ],
    "CAD": ["cad", "canadian dollar", "canadian dollars"],
    "EUR": ["eur", "euro", "euros"],
    "GBP": ["gbp", "british pound", "british pounds", "pound sterling"],
    "CHF": ["chf", "swiss franc", "swiss francs"],
    "JPY": ["jpy", "japanese yen", "yen"],
    "AUD": ["aud", "australian dollar", "australian dollars"],
    "MXN": ["mxn", "mexican peso", "mexican pesos"],
    "HKD": ["hkd", "hong kong dollar", "hong kong dollars"],
    "CNY": ["cny", "chinese yuan", "renminbi"],
}


# Key unit synonyms for unit-of-measure templates.
_UNIT_SYNONYMS: Dict[str, List[str]] = {
    "shares": ["share", "shares", "per share", "per-share", "per unit"],
    "pure": ["percentage", "percent", "%", "ratio"],
    "barrels": ["barrel", "barrels", "bbl"],
    "days": ["day", "days"],
    "square feet": ["square foot", "square feet", "sqft", "sq ft"],
}


def _find_currency_in_question(question: str) -> Optional[str]:
    """Return ISO currency code if a known currency is mentioned."""

    question_lower = question.lower()

    for code, synonyms in _CURRENCY_SYNONYMS.items():
        for term in synonyms:
            if term in question_lower:
                return code

    # Look for explicit three-letter code in parentheses or standalone
    token_match = re.search(r"\b([A-Z]{3})\b", question.upper())
    if token_match:
        token = token_match.group(1)
        if token in _CURRENCY_SYNONYMS:
            return token

    return None


def _find_unit_in_question(question: str) -> Optional[str]:
    """Return a normalized unit-of-measure token if present in the question."""

    question_lower = question.lower()

    # Prefer explicitly quoted units first (e.g., 'shares')
    quoted = re.findall(r"'([^']+)'", question_lower)
    for token in quoted:
        normalized = _normalize_unit_token(token.strip())
        if normalized:
            return normalized

    normalized = _normalize_unit_token(question_lower)
    if normalized:
        return normalized

    return None


def _normalize_unit_token(token: str) -> Optional[str]:
    """Normalize free-form unit text using the synonyms mapping."""

    token = token.strip().lower()
    if not token:
        return None

    for canonical, synonyms in _UNIT_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in token:
                return canonical

    return None


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

    def __init__(self, use_phase_0_only: bool = False):
        """
        Initialize intelligence loader.

        Args:
            use_phase_0_only: If True, only use Phase 0 templates.
                             If False, load all templates from parquet files (default).
        """
        self.logger = get_logger()
        self.templates: List[QueryTemplate] = []
        self.use_phase_0_only = use_phase_0_only

        # Load templates
        self._load_templates()

        self.logger.info(f"Loaded {len(self.templates)} query templates")

    def _load_templates(self):
        """Load query templates from parquet and Phase 0 templates."""
        if self.use_phase_0_only:
            # Phase 0 only: Use hardcoded templates
            self.templates.extend(PHASE_0_TEMPLATES)
        else:
            # Phase 1+: Load from parquet file (includes all 25 templates)
            try:
                parquet_path = get_parquet_path("query_intelligence.parquet")
                if parquet_path.exists():
                    import json

                    df = pd.read_parquet(parquet_path)

                    for _, row in df.iterrows():
                        # Parse parameters from JSON if stored as string
                        params = row.get("parameters", [])
                        if isinstance(params, str):
                            params = json.loads(params)

                        template = QueryTemplate(
                            template_id=row["template_id"],
                            name=row.get("name", row.get("intent_category", "")),
                            pattern=row["natural_language_pattern"],
                            sql_template=row["sql_template"],
                            parameters=(
                                params
                                if params
                                else self._extract_parameters(row["sql_template"])
                            ),
                            description=row.get("description", ""),
                        )
                        self.templates.append(template)

                    self.logger.info(f"Loaded {len(df)} templates from parquet")
                else:
                    self.logger.warning(
                        f"Template file not found: {parquet_path}, falling back to Phase 0 templates"
                    )
                    self.templates.extend(PHASE_0_TEMPLATES)

            except Exception as e:
                self.logger.error(
                    f"Error loading templates from parquet: {e}, falling back to Phase 0 templates"
                )
                self.templates.extend(PHASE_0_TEMPLATES)

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
        year_tokens = re.findall(r"(20\d{2})", question_lower)

        # Template-specific extraction logic driven by required parameters
        if "sector" in template.parameters:
            # Patterns: "Technology sector", "in Technology", "Healthcare sector"
            sector_patterns = [
                r"(?:in|from)\s+(?:the\s+)?([\w\s&\-]+?)\s+(?:sector|industry)",
                r"([\w\s&\-]+?)\s+(?:sector|industry)",
            ]

            for pattern in sector_patterns:
                match = re.search(pattern, question_lower)
                if match:
                    sector = match.group(1)
                    params["sector"] = sector.strip()
                    break

        if "company" in template.parameters:
            # Remove helper words and punctuation to isolate company tokens
            cleaned = re.sub(
                r"(what|which|is|are|the|sector|cik|ticker|symbol|'s|does|belong|to|in)",
                "",
                question_lower,
            )
            cleaned = re.sub(r"[?!.,;:]", " ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

            if cleaned:
                words = cleaned.split()
                company = " ".join(words[:3]).strip()
                params["company"] = normalize_company_name(company)

        if "metric" in template.parameters:
            metric_match = re.search(
                r"(revenue|revenues|net income|income|earnings|asset|liabilit[y|ies]|debt|cash)",
                question_lower,
            )
            if metric_match:
                params["metric"] = metric_match.group(1)

        if "time_period" in template.parameters:
            period_match = re.search(
                r"(201\d|202\d|last year|previous quarter|current quarter|past (\d+) years)",
                question_lower,
            )
            if period_match:
                params["time_period"] = period_match.group(0)

        if "jurisdiction" in template.parameters or "state" in template.parameters:
            from src.entity_extractor import US_STATES, COUNTRIES, get_entity_extractor

            extractor = get_entity_extractor()
            normalized = None

            # Prioritize full state names (e.g., "new york")
            for state_name, state_code in sorted(
                US_STATES.items(), key=lambda x: -len(x[0])
            ):
                if state_name in question_lower:
                    normalized = state_code
                    break

            if not normalized:
                # Check for country names
                for country_name, country_code in sorted(
                    COUNTRIES.items(), key=lambda x: -len(x[0])
                ):
                    if country_name in question_lower:
                        normalized = country_code
                        break

            if not normalized:
                # Check for two-letter codes in the question (only uppercase tokens)
                tokens = re.findall(r"[A-Za-z]{2,}", question)
                for token in tokens:
                    if not token.isupper():
                        continue
                    state_code = extractor._normalize_state_code(token)
                    if state_code:
                        normalized = state_code
                        break

            if normalized:
                if "jurisdiction" in template.parameters:
                    params["jurisdiction"] = normalized
                if "state" in template.parameters:
                    params["state"] = normalized

        if "currency" in template.parameters and "currency" not in params:
            currency = _find_currency_in_question(question)
            if currency:
                params["currency"] = currency

        if "unit" in template.parameters and "unit" not in params:
            unit = _find_unit_in_question(question)
            if unit:
                params["unit"] = unit

        if "fye" in template.parameters and "fye" not in params:
            fye_match = re.search(r"\b(\d{4})\b", question_lower)
            if fye_match:
                params["fye"] = fye_match.group(1)

        if "fiscal_year" in template.parameters and "fiscal_year" not in params:
            fiscal_match = re.search(r"\b(20\d{2})\b", question_lower)
            if fiscal_match:
                params["fiscal_year"] = fiscal_match.group(1)

        if "threshold" in template.parameters and "threshold" not in params:
            threshold_match = re.search(
                r"(\d+[,\d]*(?:\.\d+)?)\s*(percent|percentage|%)?", question_lower
            )
            if threshold_match:
                threshold_token = threshold_match.group(1).replace(",", "")
                unit_token = threshold_match.group(2)

                try:
                    numeric_value = float(threshold_token)
                except ValueError:
                    numeric_value = None

                if numeric_value is not None:
                    scale = 1.0
                    if "trillion" in question_lower:
                        scale = 1_000_000_000_000.0
                    elif "billion" in question_lower:
                        scale = 1_000_000_000.0
                    elif "million" in question_lower:
                        scale = 1_000_000.0
                    elif "thousand" in question_lower:
                        scale = 1_000.0

                    numeric_value *= scale
                    params["threshold"] = str(numeric_value)

        if "rank" in template.parameters and "rank" not in params:
            ordinal_map = {
                "second": 2,
                "2nd": 2,
                "two": 2,
                "third": 3,
                "3rd": 3,
                "three": 3,
                "first": 1,
                "1st": 1,
                "one": 1,
                "most": 1,
            }
            for token, value in ordinal_map.items():
                if token in question_lower:
                    params["rank"] = str(value)
                    break

        if "rank" in template.parameters and "rank" not in params:
            params["rank"] = "1"

        if "cik" in template.parameters and "cik" not in params:
            cik_match = re.search(r"\b\d{10}\b", question_lower)
            if cik_match:
                params["cik"] = cik_match.group(0)

        if "form" in template.parameters and "form" not in params:
            form_match = re.search(
                r"(10[-\s]?k|10[-\s]?q|8[-\s]?k|s-1|s-4)", question_lower
            )
            if form_match:
                token = form_match.group(1).upper().replace(" ", "-")
                if not token.startswith("S"):
                    token = (
                        token.replace("10K", "10-K")
                        .replace("10Q", "10-Q")
                        .replace("8K", "8-K")
                    )
                params["form"] = token

        if "currency" in template.parameters and "currency" not in params:
            currency_map = {
                "usd": "USD",
                "u.s. dollar": "USD",
                "dollar": "USD",
                "eur": "EUR",
                "euro": "EUR",
                "gbp": "GBP",
                "pound": "GBP",
                "cad": "CAD",
                "aud": "AUD",
                "jpy": "JPY",
                "yen": "JPY",
                "cny": "CNY",
                "rmb": "CNY",
            }
            for token, code in currency_map.items():
                if token in question_lower:
                    params["currency"] = code
                    break

        if "keyword" in template.parameters and "keyword" not in params:
            quote_match = re.search(r"[\"']([^\"']+)[\"']", question)
            if quote_match:
                params["keyword"] = quote_match.group(1).upper()
            else:
                # Fall back to uppercase words like CORP, INC, LLC
                uppercase_tokens = re.findall(r"\b[A-Z]{2,}\b", question)
                for token in uppercase_tokens:
                    if token in {"CORP", "INC", "LLC", "CO", "PLC"}:
                        params["keyword"] = token
                        break

        if "flag" in template.parameters and "flag" not in params:
            if "debit" in question_lower:
                params["flag"] = "Debit"
            elif "credit" in question_lower:
                params["flag"] = "Credit"

        if "datatype" in template.parameters and "datatype" not in params:
            if "monetary" in question_lower:
                params["datatype"] = "monetary"
            elif "per-share" in question_lower or "per share" in question_lower:
                params["datatype"] = "per-share"
            elif "string" in question_lower:
                params["datatype"] = "string"

        if "qtrs" in template.parameters and "qtrs" not in params:
            qtrs_match = re.search(r"qtrs\s*=\s*(\d)", question_lower)
            if qtrs_match:
                params["qtrs"] = qtrs_match.group(1)
            elif "quarterly" in question_lower:
                params["qtrs"] = "1"
            elif "annual" in question_lower:
                params["qtrs"] = "0"

        if "threshold" in template.parameters and "threshold" not in params:
            threshold_match = re.search(
                r"([\$]?)([0-9][0-9,\.]*)(?:\s*(billion|million|thousand|bn|m|k|percent|%)|\s*(companies))?",
                question_lower,
            )
            if threshold_match:
                raw_number = threshold_match.group(2)
                unit = threshold_match.group(3)
                value = float(raw_number.replace(",", ""))
                if unit in {"billion", "bn"}:
                    value *= 1_000_000_000
                elif unit in {"million", "m"}:
                    value *= 1_000_000
                elif unit in {"thousand", "k"}:
                    value *= 1_000
                formatted = int(value) if float(value).is_integer() else value
                params["threshold"] = str(formatted)

        if "min_revenue" in template.parameters and "min_revenue" not in params:
            revenue_match = re.search(
                r"(?:revenue|sales|topline|turnover)[^0-9]{0,20}([\$]?[0-9][0-9,\.]*)(?:\s*(billion|million|thousand|bn|m|k))?",
                question_lower,
            )
            if revenue_match:
                raw_number = revenue_match.group(1)
                unit = revenue_match.group(2)
                value = float(raw_number.replace("$", "").replace(",", ""))
                if unit in {"billion", "bn"}:
                    value *= 1_000_000_000
                elif unit in {"million", "m"}:
                    value *= 1_000_000
                elif unit in {"thousand", "k"}:
                    value *= 1_000
                formatted = int(value) if float(value).is_integer() else value
                params["min_revenue"] = str(formatted)

        if "limit" in template.parameters and "limit" not in params:
            limit_match = re.search(r"(top|first)\s+(\d{1,3})", question_lower)
            if limit_match:
                params["limit"] = limit_match.group(2)

        if "fiscal_year" in template.parameters and "fiscal_year" not in params:
            year_match = re.search(r"(20\d\d)", question_lower)
            if year_match:
                params["fiscal_year"] = year_match.group(1)

        if "start_year" in template.parameters and "start_year" not in params:
            if year_tokens:
                params["start_year"] = year_tokens[0]

        if "end_year" in template.parameters and "end_year" not in params:
            if len(year_tokens) >= 2:
                params["end_year"] = year_tokens[1]
            elif year_tokens:
                params["end_year"] = year_tokens[0]

        if "fiscal_period" in template.parameters and "fiscal_period" not in params:
            period_match = re.search(r"\b(q[1-4]|fy)\b", question_lower)
            if period_match:
                params["fiscal_period"] = period_match.group(1).upper()

        if "flag" in template.parameters and params.get("flag"):
            params["flag"] = params["flag"].capitalize()

        self.logger.debug(f"Extracted parameters: {params}")
        return params

    def extract_parameters_for_template(
        self, question: str, template: QueryTemplate
    ) -> Dict[str, str]:
        """Public helper to extract template parameters from a question."""
        return self._extract_template_parameters(question, template)

    @staticmethod
    def _normalize_company_param(company_value: str) -> str:
        """Normalize company parameters to match canonical aliases."""
        return normalize_company_name(company_value)


# Global loader instance
_loader: Optional[IntelligenceLoader] = None


def get_intelligence_loader(use_phase_0_only: bool = True) -> IntelligenceLoader:
    """Get the global intelligence loader instance."""
    global _loader
    if _loader is None:
        _loader = IntelligenceLoader(use_phase_0_only=use_phase_0_only)
    return _loader
