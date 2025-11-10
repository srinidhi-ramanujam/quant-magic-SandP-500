"""
Entity Extractor - Extract entities from natural language questions.

Stage 1: LLM-first approach using Azure OpenAI for intelligent entity extraction.
Extracts: companies, metrics, sectors, time periods, question type.
"""

import re
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from src.models import ExtractedEntities, LLMEntityRequest, LLMEntityResponse
from src.telemetry import get_logger, RequestContext, log_component_timing
from src.xbrl_mapper import get_xbrl_mapper
from src.azure_client import AzureOpenAIClient
from src.prompts import get_entity_extraction_prompt
from src.config import get_config, Config
from src.hybrid_retrieval import HybridEntityRetriever


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

COMPANY_SUFFIXES = [
    " corporation",
    " corp.",
    " corp",
    " incorporated",
    " inc.",
    " inc",
    " company",
    " co.",
    " co",
    ", inc.",
    ", inc",
]

# Company name aliases (loaded once)
_COMPANY_ALIASES: Dict[str, str] = {}
_ALIASES_LOADED = False


def _load_company_aliases() -> Dict[str, str]:
    """Load company name aliases from CSV file."""
    global _COMPANY_ALIASES, _ALIASES_LOADED

    if _ALIASES_LOADED:
        return _COMPANY_ALIASES

    try:
        alias_file = Path(__file__).parent.parent / "data" / "company_name_aliases.csv"
        if alias_file.exists():
            aliases: Dict[str, str] = {}
            with alias_file.open() as handle:
                header_skipped = False
                for line in handle:
                    if not header_skipped:
                        header_skipped = True
                        continue
                    row = line.strip()
                    if not row:
                        continue
                    parts = [part.strip() for part in row.split(",")]
                    if len(parts) < 3:
                        continue
                    alias = parts[0].lower()
                    official_name = ",".join(parts[1:-1]).strip()
                    if alias:
                        aliases[alias] = official_name

            _COMPANY_ALIASES = aliases
        _ALIASES_LOADED = True
    except Exception as e:
        # Fallback to empty dict if loading fails
        _COMPANY_ALIASES = {}
        _ALIASES_LOADED = True

    return _COMPANY_ALIASES


def get_company_alias_map() -> Dict[str, str]:
    """Expose company alias mapping for other modules."""
    return _load_company_aliases()


def normalize_company_name(company_name: str) -> str:
    """Normalize company names to canonical aliases (uppercase)."""
    if not company_name:
        return ""

    aliases = _load_company_aliases()
    candidate = company_name.lower().strip()
    candidate = candidate.replace("’", "'")
    variants = {
        candidate,
        candidate.replace(".", ""),
        candidate.replace(",", ""),
        candidate.replace(".", " "),
    }

    for variant in list(variants):
        if variant in aliases:
            return aliases[variant]

    for suffix in COMPANY_SUFFIXES:
        if candidate.endswith(suffix):
            base = candidate[: -len(suffix)].strip()
            if base in aliases:
                return aliases[base]
            variants.add(base)
            variants.add(base.replace(".", ""))
            variants.add(base.replace(",", ""))
            variants.add(base.replace(".", " "))

    for variant in variants:
        if variant in aliases:
            return aliases[variant]

    tokenized = re.sub(r"[^a-z0-9]+", " ", candidate).strip()
    if tokenized in aliases:
        return aliases[tokenized]

    tokens = tokenized.split()
    if tokens:
        first_token = tokens[0]
        if first_token in aliases:
            return aliases[first_token]

    cleaned = re.sub(r"[',.]", "", company_name).strip()
    # Replace trailing CORPORATION/COMPANY with CORP/CO if present
    replacements = {
        " CORPORATION": " CORP",
        " COMPANY": " CO",
    }
    upper_cleaned = cleaned.upper()
    for old, new in replacements.items():
        if upper_cleaned.endswith(old):
            upper_cleaned = upper_cleaned[: -len(old)] + new
            break

    return upper_cleaned


# Question type indicators
QUESTION_TYPES = {
    "count": ["how many", "count", "number of"],
    "lookup": ["what is", "what are", "get", "find", "show me"],
    "comparison": ["compare", "versus", "vs", "difference between"],
    "trend": ["trend", "over time", "growth", "change"],
}

# US State name to code mapping
US_STATES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}

# Country name mappings
COUNTRIES = {
    "ireland": "IE",
    "canada": "CA",
    "switzerland": "CH",
    "united kingdom": "GB",
    "bermuda": "BM",
    "cayman islands": "KY",
    "netherlands": "NL",
}


class EntityExtractor:
    """Extract entities from questions using LLM-assisted extraction (Stage 1)."""

    def __init__(self, use_llm: bool = True, config: Optional[Config] = None):
        """
        Initialize entity extractor.

        Args:
            use_llm: Whether to use LLM for extraction.
            config: Optional Config instance (primarily for testing)
        """
        self.logger = get_logger()
        self.config = config or get_config()
        self.use_llm = bool(use_llm)
        # Initialize Azure OpenAI client if LLM is enabled
        if self.use_llm:
            try:
                self.azure_client = AzureOpenAIClient()
                if not self.azure_client.is_available():
                    raise RuntimeError("Azure OpenAI client not available")
                self.logger.info("EntityExtractor initialized (LLM mode)")
            except Exception as e:
                self.logger.error(f"Failed to initialize Azure OpenAI client: {e}")
                self.azure_client = None
                self.use_llm = False
                self.logger.warning("Falling back to deterministic mode")
        else:
            self.azure_client = None
            self.logger.info("EntityExtractor initialized (deterministic mode)")

        # Hybrid retriever (FAISS-based). Optional.
        self.hybrid_retriever = HybridEntityRetriever.create_default()
        if self.hybrid_retriever:
            self.logger.info("Hybrid entity retriever enabled")

    def extract(self, question: str, context: RequestContext) -> ExtractedEntities:
        """
        Extract entities from a natural language question using LLM.

        Args:
            question: Natural language question
            context: Request context for telemetry

        Returns:
            ExtractedEntities with extracted information
        """
        with log_component_timing(context, "entity_extraction"):
            if self.hybrid_retriever:
                entities = self._extract_entities(question)
                coverage = self.hybrid_retriever.enrich(question, entities)
                entities.confidence = self._calculate_confidence(
                    entities.companies,
                    entities.metrics,
                    entities.sectors,
                    entities.time_periods,
                    entities.question_type,
                )
                context.add_metadata("entity_extraction_method", "hybrid")
                if coverage:
                    context.add_metadata("entity_retriever_slots", coverage)
                return entities

            if self.use_llm and self.azure_client:
                try:
                    return self._extract_with_llm(question, context)
                except Exception as e:
                    self.logger.error(
                        f"LLM extraction failed: {e}, using deterministic fallback"
                    )
                    # Fallback to deterministic if LLM fails
                    return self._extract_entities(question)
            else:
                return self._extract_entities(question)

    def _extract_with_llm(
        self, question: str, context: RequestContext
    ) -> ExtractedEntities:
        """
        Extract entities using Azure Open AI (Stage 1: LLM-first approach).

        Args:
            question: Natural language question
            context: Request context for telemetry

        Returns:
            ExtractedEntities with LLM-extracted information

        Raises:
            Exception: If LLM extraction fails after retries
        """
        import time

        # Get entity extraction prompt
        prompt = get_entity_extraction_prompt(question)

        # Create LLM request using the correct model
        llm_request = LLMEntityRequest(
            question=prompt,
            context={},
            temperature=self.config.entity_extraction_temperature,
            max_tokens=500,  # Entity extraction shouldn't need many tokens
        )

        # Call Azure OpenAI with retry logic
        max_retries = self.config.entity_extraction_max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(
                    f"LLM entity extraction attempt {attempt + 1}/{max_retries + 1}"
                )

                start_time = time.time()

                # Call Azure OpenAI directly via the client
                if not self.azure_client.is_available():
                    raise ValueError("Azure OpenAI client not available")

                # Use the client's OpenAI instance directly for entity extraction
                model_name = self.azure_client.config.deployment_name or ""
                self.logger.debug(f"Using deployment: {model_name}")

                # Build request parameters
                # Note: gpt-5 deployment requires specific parameters:
                # - Only supports temperature=1 (default, no custom values)
                # - Doesn't support system messages
                # - Uses max_completion_tokens instead of max_tokens
                # Other models (o1-*) also have similar requirements
                requires_special_params = any(
                    x in model_name.lower() for x in ["o1", "gpt-5"]
                )

                if requires_special_params:
                    # Use parameters compatible with gpt-5 and o1-series models
                    self.logger.debug(
                        f"Using special parameters for model: {model_name}"
                    )
                    response = self.azure_client.client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_completion_tokens=500,
                    )
                else:
                    # Standard models support all parameters
                    response = self.azure_client.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a financial data analyst assistant.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=self.config.entity_extraction_temperature,
                        max_completion_tokens=500,
                    )

                elapsed_ms = int((time.time() - start_time) * 1000)

                # Extract content from response
                content = response.choices[0].message.content

                # Parse JSON from LLM response
                llm_output = self._parse_llm_response(content)

                # Extract token usage from response
                token_usage = {
                    "prompt_tokens": (
                        response.usage.prompt_tokens
                        if hasattr(response, "usage")
                        else 0
                    ),
                    "completion_tokens": (
                        response.usage.completion_tokens
                        if hasattr(response, "usage")
                        else 0
                    ),
                }

                # Validate with Pydantic
                llm_entity_response = LLMEntityResponse(
                    companies=llm_output.get("companies", []),
                    metrics=llm_output.get("metrics", []),
                    sectors=llm_output.get("sectors", []),
                    time_periods=llm_output.get("time_periods", []),
                    question_type=llm_output.get("question_type", "lookup"),
                    confidence=llm_output.get("confidence", 0.5),
                    reasoning=llm_output.get("reasoning", ""),
                    processing_time_ms=elapsed_ms,
                    token_usage=token_usage,
                )

                # Convert to ExtractedEntities
                entities = ExtractedEntities(
                    companies=llm_entity_response.companies,
                    metrics=llm_entity_response.metrics,
                    sectors=llm_entity_response.sectors,
                    time_periods=llm_entity_response.time_periods,
                    question_type=llm_entity_response.question_type,
                    confidence=llm_entity_response.confidence,
                )

                # Log successful extraction
                self.logger.info(
                    f"LLM extraction successful: {len(entities.companies)} companies, "
                    f"{len(entities.metrics)} metrics, confidence={entities.confidence:.2f}, "
                    f"tokens={sum(llm_entity_response.token_usage.values())}, latency={elapsed_ms}ms"
                )

                # Track LLM call in telemetry metadata
                if not context.metadata.get("llm_calls"):
                    context.metadata["llm_calls"] = []
                context.metadata["llm_calls"].append(
                    {
                        "stage": "entity_extraction",
                        "tokens": llm_entity_response.token_usage,
                        "latency_ms": elapsed_ms,
                        "success": True,
                    }
                )

                return entities

            except json.JSONDecodeError as e:
                last_error = f"JSON parsing error: {e}"
                self.logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                if attempt < max_retries:
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    self.use_llm = False
                    self.azure_client = None
                    self.logger.warning(
                        "Disabling LLM entity extraction after repeated parsing failures"
                    )
                    raise ValueError(
                        f"Failed to parse LLM response after {max_retries + 1} attempts: {last_error}"
                    )

            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
                if attempt < max_retries:
                    time.sleep(1 * (attempt + 1))
                    continue
                else:
                    self.use_llm = False
                    self.azure_client = None
                    self.logger.warning(
                        "Disabling LLM entity extraction after repeated failures; "
                        "falling back to deterministic extraction"
                    )
                    raise Exception(
                        f"LLM extraction failed after {max_retries + 1} attempts: {last_error}"
                    )

        # Should never reach here, but just in case
        raise Exception(f"LLM extraction failed: {last_error}")

    def _parse_llm_response(self, response_text: str) -> Dict:
        """
        Parse JSON response from LLM.

        Handles various formats: plain JSON, markdown code blocks, etc.

        Args:
            response_text: Raw text from LLM

        Returns:
            Parsed dictionary

        Raises:
            json.JSONDecodeError: If parsing fails
        """
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text.lower():
            # Extract content between ```json and ```
            start = response_text.lower().find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        elif "```" in response_text:
            # Extract content between ``` and ```
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        else:
            # Assume it's plain JSON
            json_str = response_text.strip()

        # Parse JSON
        if not json_str:
            raise json.JSONDecodeError("Empty LLM response", json_str, 0)
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            # Look for { ... } pattern
            import re

            match = re.search(r"\{[^}]+\}", json_str, re.DOTALL)
            if match:
                return json.loads(match.group())
            else:
                raise

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

        # Pattern 2: Check alias mappings (loaded from CSV)
        aliases = _load_company_aliases()
        question_lower = question.lower()

        # Sort aliases by length (longest first) to match "Apple Inc." before "Apple"
        sorted_aliases = sorted(aliases.keys(), key=len, reverse=True)

        for alias in sorted_aliases:
            if alias in question_lower:
                # Get the official name from alias
                official_name = aliases[alias]
                if official_name not in companies:
                    companies.append(official_name)

        # Pattern 3: Common company names (case-insensitive fallback)
        # Check for well-known company names even if lowercase
        common_companies = [
            "microsoft",
            "apple",
            "google",
            "amazon",
            "meta",
            "tesla",
            "nvidia",
            "netflix",
            "facebook",
            "ibm",
            "oracle",
            "salesforce",
        ]
        for company in common_companies:
            if company in question_lower and not any(
                company.lower() in c.lower() for c in companies
            ):
                # Capitalize first letter for standardization
                companies.append(company.capitalize())

        aliases = _load_company_aliases()
        normalized: List[str] = []
        for company_name in companies:
            canonical = normalize_company_name(company_name)
            if canonical and canonical not in normalized:
                normalized.append(canonical)

        return normalized

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

    def _extract_date_range(self, question: str) -> Optional[Dict[str, any]]:
        """
        Extract date range from question.

        Handles patterns like:
        - "2020-2024" or "from 2020 to 2024"
        - "last 3 years" or "past 5 years"
        - "Q1 2020 to Q4 2023"

        Returns:
            Dictionary with start_year, end_year, or None
        """
        question_lower = question.lower()

        # Pattern 1: Explicit year range (2020-2024, from 2020 to 2024)
        range_pattern = r"(from\s+)?(\d{4})\s*(?:-|to)\s*(\d{4})"
        match = re.search(range_pattern, question_lower)
        if match:
            return {
                "start_year": int(match.group(2)),
                "end_year": int(match.group(3)),
            }

        # Pattern 2: Relative time (last N years, past N years)
        relative_pattern = r"(?:last|past|previous)\s+(\d+)\s+years?"
        match = re.search(relative_pattern, question_lower)
        if match:
            n_years = int(match.group(1))
            current_year = datetime.now().year
            return {
                "start_year": current_year - n_years,
                "end_year": current_year,
            }

        # Pattern 3: "over N years" or "N year trend"
        trend_pattern = r"(?:over|across)\s+(\d+)\s+years?"
        match = re.search(trend_pattern, question_lower)
        if match:
            n_years = int(match.group(1))
            current_year = datetime.now().year
            return {
                "start_year": current_year - n_years + 1,
                "end_year": current_year,
            }

        return None

    def _extract_fiscal_periods(self, question: str) -> List[str]:
        """
        Extract fiscal period indicators from question.

        Returns list of fiscal periods: ["Q1", "Q2", "FY", "quarterly", "annual"]
        """
        periods = []
        question_lower = question.lower()

        # Quarter patterns
        if re.search(r"\bq[1-4]\b", question_lower):
            quarters = re.findall(r"\b(q[1-4])\b", question_lower)
            periods.extend([q.upper() for q in quarters])

        # General quarterly
        if any(word in question_lower for word in ["quarterly", "quarter", "qtrs"]):
            periods.append("quarterly")

        # Fiscal year
        if any(
            word in question_lower
            for word in ["fy", "fiscal year", "annual", "annually"]
        ):
            periods.append("annual")

        return list(set(periods))

    def _normalize_state_code(self, state: str) -> Optional[str]:
        """
        Normalize state name to 2-letter code.

        Args:
            state: State name or code (e.g., "California" or "CA")

        Returns:
            2-letter state code or None if not found
        """
        state_lower = state.lower().strip()

        # Already a 2-letter code
        if len(state_lower) == 2 and state_lower.upper() in US_STATES.values():
            return state_lower.upper()

        # Look up in state names
        if state_lower in US_STATES:
            return US_STATES[state_lower]

        # Check countries too
        if state_lower in COUNTRIES:
            return COUNTRIES[state_lower]

        return None

    def _parse_threshold_value(self, text: str) -> Optional[float]:
        """
        Parse numeric threshold from text.

        Handles patterns like:
        - "$50 billion" -> 50000000000
        - "50B" -> 50000000000
        - "50M" -> 50000000
        - "50 million" -> 50000000
        - "50%" -> 0.5

        Args:
            text: Text containing threshold value

        Returns:
            Numeric value or None
        """
        text_lower = text.lower()

        # Pattern 1: Number with B/M/K suffix (50B, 50M, 50K)
        pattern1 = r"(\$?\s*)(\d+\.?\d*)\s*([bmk])\b"
        match = re.search(pattern1, text_lower)
        if match:
            number = float(match.group(2))
            suffix = match.group(3)
            multipliers = {"b": 1e9, "m": 1e6, "k": 1e3}
            return number * multipliers[suffix]

        # Pattern 2: Number with spelled-out multiplier (50 billion, 50 million)
        pattern2 = r"(\$?\s*)(\d+\.?\d*)\s*(billion|million|thousand)\b"
        match = re.search(pattern2, text_lower)
        if match:
            number = float(match.group(2))
            multiplier_word = match.group(3)
            multipliers = {"billion": 1e9, "million": 1e6, "thousand": 1e3}
            return number * multipliers[multiplier_word]

        # Pattern 3: Percentage (50%, 0.5)
        pattern3 = r"(\d+\.?\d*)\s*%"
        match = re.search(pattern3, text_lower)
        if match:
            return float(match.group(1)) / 100.0

        # Pattern 4: Plain number (try to parse as is)
        pattern4 = r"\$?\s*(\d+\.?\d*)"
        match = re.search(pattern4, text_lower)
        if match:
            return float(match.group(1))

        return None

    def _map_metric_variants(self, metric: str) -> List[str]:
        """
        Map metric name to XBRL tag variants.

        Args:
            metric: Business metric name (e.g., "revenue", "net income")

        Returns:
            List of XBRL tags for this metric
        """
        mapper = get_xbrl_mapper()
        return mapper.map_metric_to_tags(metric)

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


def get_entity_extractor(force_refresh: bool = False) -> EntityExtractor:
    """Get the global entity extractor instance."""
    global _extractor
    if _extractor is None or force_refresh:
        _extractor = EntityExtractor(config=get_config())

    return _extractor
