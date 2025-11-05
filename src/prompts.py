"""
Prompt Engineering Module for LLM Integration

This module contains all prompts for the 4-stage LLM pipeline:
- Stage 1: Entity Extraction
- Stage 2: Template Selection
- Stage 3: SQL Generation
- Stage 4: SQL Validation

All prompts are designed for Azure OpenAI gpt-5 deployment with structured output.
"""

from typing import List, Dict, Optional, Any


# ==============================================================================
# STAGE 1: ENTITY EXTRACTION PROMPTS
# ==============================================================================


def get_entity_extraction_prompt(question: str) -> str:
    """
    Generate prompt for LLM-assisted entity extraction.

    Args:
        question: User's natural language question

    Returns:
        Structured prompt for entity extraction
    """
    prompt = f"""You are a financial data analyst assistant. Extract structured entities from the user's question about S&P 500 companies.

QUESTION: "{question}"

Your task is to extract the following entities:

1. **companies**: List of company names (use official S&P 500 names)
   - Convert tickers to full names (AAPL → APPLE INC, MSFT → MICROSOFT CORP)
   - Standardize to uppercase official names
   - Extract multiple companies if comparison requested

2. **metrics**: List of financial metrics requested
   - Standardize synonyms (sales → revenue, profit → net_income)
   - Use lowercase with underscores (net_income, total_assets, stockholders_equity)
   - Common metrics: revenue, net_income, assets, liabilities, equity, cash, debt

3. **sectors**: List of GICS sector names (if mentioned)
   - Use official GICS sectors: Information Technology, Health Care, Financials, 
     Consumer Discretionary, Communication Services, Industrials, Consumer Staples,
     Energy, Utilities, Real Estate, Materials
   - Normalize variations (Tech → Information Technology)

4. **time_periods**: List of time references
   - Extract years (2024, 2023), quarters (Q1, Q2, Q3, Q4)
   - Convert "latest", "recent", "current" to "latest"
   - Format fiscal years as FY2024, FY2023

5. **question_type**: The type of question being asked
   - Options: "lookup", "count", "list", "comparison", "calculation", "trend"

6. **confidence**: Your confidence in the extraction (0.0 to 1.0)
   - 0.9-1.0: Very clear, all entities explicitly stated
   - 0.7-0.9: Clear, minor ambiguity
   - 0.5-0.7: Some ambiguity, made reasonable inferences
   - <0.5: High ambiguity, low confidence

7. **reasoning**: Brief explanation of your extraction decisions (2-3 sentences)

IMPORTANT GUIDELINES:
- Return empty list [] if an entity type is not present
- Don't make up entities that aren't mentioned or strongly implied
- For ambiguous questions, make your best inference and note it in reasoning
- Use exact standardized names (APPLE INC, not Apple Inc or apple inc)

FEW-SHOT EXAMPLES:

Example 1:
Question: "What is Apple's CIK?"
{{
  "companies": ["APPLE INC"],
  "metrics": ["cik"],
  "sectors": [],
  "time_periods": [],
  "question_type": "lookup",
  "confidence": 0.95,
  "reasoning": "Clear company name (Apple → APPLE INC) and specific metric (CIK) requested. No ambiguity."
}}

Example 2:
Question: "How many companies are in the Technology sector?"
{{
  "companies": [],
  "metrics": [],
  "sectors": ["Information Technology"],
  "time_periods": [],
  "question_type": "count",
  "confidence": 0.9,
  "reasoning": "Sector count question. Technology normalized to official GICS name 'Information Technology'."
}}

Example 3:
Question: "What's AAPL's revenue in Q3 2024?"
{{
  "companies": ["APPLE INC"],
  "metrics": ["revenue"],
  "sectors": [],
  "time_periods": ["Q3", "2024"],
  "question_type": "lookup",
  "confidence": 0.95,
  "reasoning": "Ticker AAPL converted to APPLE INC. Revenue metric and specific time period (Q3 2024) clearly identified."
}}

Example 4:
Question: "Compare Apple and Microsoft's latest revenue"
{{
  "companies": ["APPLE INC", "MICROSOFT CORP"],
  "metrics": ["revenue"],
  "sectors": [],
  "time_periods": ["latest"],
  "question_type": "comparison",
  "confidence": 0.9,
  "reasoning": "Comparison question with two companies identified and converted to official names. 'Latest' indicates most recent period."
}}

Example 5:
Question: "What's MSFT's sales?"
{{
  "companies": ["MICROSOFT CORP"],
  "metrics": ["revenue"],
  "sectors": [],
  "time_periods": ["latest"],
  "question_type": "lookup",
  "confidence": 0.85,
  "reasoning": "Ticker MSFT → MICROSOFT CORP. 'Sales' synonym mapped to 'revenue'. 'Latest' implied since no time period specified."
}}

Example 6:
Question: "List companies in Energy with revenue over $50 billion"
{{
  "companies": [],
  "metrics": ["revenue"],
  "sectors": ["Energy"],
  "time_periods": [],
  "question_type": "list",
  "confidence": 0.9,
  "reasoning": "Sector-based list query with revenue threshold filter. Energy is valid GICS sector."
}}

Example 7:
Question: "Show me tech companies incorporated in Delaware"
{{
  "companies": [],
  "metrics": [],
  "sectors": ["Information Technology"],
  "time_periods": [],
  "question_type": "list",
  "confidence": 0.85,
  "reasoning": "'Tech' normalized to Information Technology. Geographic filter (Delaware) noted but not an entity we extract."
}}

Example 8:
Question: "What companies have improving profit margins?"
{{
  "companies": [],
  "metrics": ["profit_margin"],
  "sectors": [],
  "time_periods": [],
  "question_type": "trend",
  "confidence": 0.8,
  "reasoning": "Trend analysis question. 'Improving' implies time series comparison. Profit margins is the key metric."
}}

Example 9:
Question: "Apple's total assets"
{{
  "companies": ["APPLE INC"],
  "metrics": ["assets"],
  "sectors": [],
  "time_periods": ["latest"],
  "question_type": "lookup",
  "confidence": 0.9,
  "reasoning": "Simple lookup question. Apple → APPLE INC. 'Total assets' → 'assets'. Latest period implied."
}}

Example 10:
Question: "Companies in Healthcare with debt-to-equity over 2.0"
{{
  "companies": [],
  "metrics": ["debt_to_equity_ratio"],
  "sectors": ["Health Care"],
  "time_periods": [],
  "question_type": "list",
  "confidence": 0.85,
  "reasoning": "Sector filter + ratio filter query. Healthcare → Health Care (official GICS name). Debt-to-equity is a calculated ratio."
}}

RESPONSE FORMAT:
Return ONLY a valid JSON object with the exact structure shown above. Do not include any other text, explanation, or markdown formatting.

JSON Response:"""

    return prompt


# ==============================================================================
# COMMON COMPANY NAME MAPPINGS (for prompt context)
# ==============================================================================

COMMON_TICKER_TO_NAME = {
    "AAPL": "APPLE INC",
    "MSFT": "MICROSOFT CORP",
    "GOOGL": "ALPHABET INC",
    "GOOG": "ALPHABET INC",
    "AMZN": "AMAZON COM INC",
    "TSLA": "TESLA INC",
    "META": "META PLATFORMS INC",
    "NVDA": "NVIDIA CORP",
    "JPM": "JPMORGAN CHASE & CO",
    "V": "VISA INC",
    "WMT": "WALMART INC",
    "JNJ": "JOHNSON & JOHNSON",
    "PG": "PROCTER & GAMBLE CO",
    "MA": "MASTERCARD INC",
    "HD": "HOME DEPOT INC",
    "BAC": "BANK OF AMERICA CORP",
    "XOM": "EXXON MOBIL CORP",
    "DIS": "WALT DISNEY CO",
    "CSCO": "CISCO SYSTEMS INC",
    "PFE": "PFIZER INC",
}

# ==============================================================================
# COMMON METRIC SYNONYMS (for prompt context)
# ==============================================================================

METRIC_SYNONYMS = {
    "sales": "revenue",
    "turnover": "revenue",
    "top line": "revenue",
    "profit": "net_income",
    "earnings": "net_income",
    "net profit": "net_income",
    "bottom line": "net_income",
    "total assets": "assets",
    "total liabilities": "liabilities",
    "shareholders equity": "stockholders_equity",
    "stockholders equity": "stockholders_equity",
    "equity": "stockholders_equity",
    "book value": "stockholders_equity",
}

# ==============================================================================
# GICS SECTOR MAPPINGS (for prompt context)
# ==============================================================================

SECTOR_NORMALIZATIONS = {
    "tech": "Information Technology",
    "technology": "Information Technology",
    "it": "Information Technology",
    "healthcare": "Health Care",
    "health": "Health Care",
    "medical": "Health Care",
    "pharma": "Health Care",
    "financial": "Financials",
    "finance": "Financials",
    "banking": "Financials",
    "consumer discretionary": "Consumer Discretionary",
    "discretionary": "Consumer Discretionary",
    "consumer cyclical": "Consumer Discretionary",
    "consumer staples": "Consumer Staples",
    "staples": "Consumer Staples",
    "consumer defensive": "Consumer Staples",
    "industrial": "Industrials",
    "manufacturing": "Industrials",
    "communications": "Communication Services",
    "telecom": "Communication Services",
    "media": "Communication Services",
}

# Placeholder functions for future stages (will be implemented in respective tasks)


def get_template_selection_prompt(
    question: str, entities: Dict[str, Any], candidate_templates: List[Dict[str, Any]]
) -> str:
    """
    Generate prompt for LLM-assisted template selection (Stage 2).

    Args:
        question: User's natural language question
        entities: Extracted entities from Stage 1
        candidate_templates: List of candidate templates from deterministic matching

    Returns:
        Prompt for template selection
    """
    # Format candidate templates for the prompt
    templates_desc = []
    for i, template in enumerate(candidate_templates, 1):
        templates_desc.append(
            f"""
Template {i}: {template.get('template_id', 'unknown')}
- Name: {template.get('name', 'N/A')}
- Description: {template.get('description', 'N/A')}
- Parameters: {', '.join(template.get('parameters', []))}
- SQL: {template.get('sql_template', 'N/A')[:100]}...
"""
        )

    templates_text = (
        "\n".join(templates_desc) if templates_desc else "No candidate templates found"
    )

    prompt = f"""You are a financial data analyst assistant helping to select the best SQL template for a user's question.

USER QUESTION: "{question}"

EXTRACTED ENTITIES:
- Companies: {entities.get('companies', [])}
- Metrics: {entities.get('metrics', [])}
- Sectors: {entities.get('sectors', [])}
- Time Periods: {entities.get('time_periods', [])}
- Question Type: {entities.get('question_type', 'unknown')}

CANDIDATE TEMPLATES:
{templates_text}

Your task is to:
1. Review the user's question and extracted entities
2. Evaluate each candidate template's suitability
3. Select the BEST template that can answer the question, OR recommend custom SQL generation

SELECTION CRITERIA:
- Does the template match the question intent?
- Can all required parameters be filled from extracted entities?
- Is the template's output format appropriate for the question?
- Are there any missing capabilities that require custom SQL?

DECISION OPTIONS:
Option A: SELECT A TEMPLATE - Choose the best template and explain why
Option B: CUSTOM SQL NEEDED - If no template fits well, recommend custom SQL generation

IMPORTANT:
- If entities can fill template parameters → SELECT TEMPLATE
- If question is complex or unique → RECOMMEND CUSTOM SQL
- If unsure between templates → choose the more specific one
- If no templates provided → RECOMMEND CUSTOM SQL

FEW-SHOT EXAMPLES:

Example 1:
Question: "How many companies in Technology?"
Entities: sectors=["Information Technology"]
Candidates: [sector_company_count, sector_list]
Decision: SELECT sector_company_count (matches count intent exactly)

Example 2:
Question: "What is Apple's CIK?"
Entities: companies=["APPLE INC"], metrics=["cik"]
Candidates: [company_cik_lookup, company_info]
Decision: SELECT company_cik_lookup (specific to CIK lookup)

Example 3:
Question: "Companies with revenue over $50 billion"
Entities: metrics=["revenue"]
Candidates: [company_list, sector_companies]
Decision: CUSTOM SQL (needs threshold filter not in templates)

Example 4:
Question: "List Technology sector companies"
Entities: sectors=["Information Technology"]
Candidates: [sector_list, sector_company_count]
Decision: SELECT sector_list (list intent, not count)

Example 5:
Question: "Compare Apple and Microsoft profitability"
Entities: companies=["APPLE INC", "MICROSOFT CORP"]
Candidates: []
Decision: CUSTOM SQL (comparison query, no templates available)

RESPONSE FORMAT:
Return ONLY a valid JSON object:
{{
  "selected_template_id": "template_id or null",
  "confidence": 0.85,
  "reasoning": "Explanation of selection decision",
  "use_custom_sql": false,
  "parameter_mapping": {{"param1": "value1", "param2": "value2"}}
}}

Fields:
- selected_template_id: ID of chosen template, or null if custom SQL needed
- confidence: 0.0-1.0 confidence in this decision
- reasoning: 2-3 sentences explaining the decision
- use_custom_sql: true if custom SQL generation recommended, false otherwise
- parameter_mapping: How to fill template parameters from entities (empty if custom SQL)

JSON Response:"""

    return prompt


def get_sql_template_population_prompt(
    template: Dict[str, Any], entities: Dict[str, Any]
) -> str:
    """Generate prompt for Stage 3: SQL Generation (template-based) (TODO: Implement in Stage 3)."""
    raise NotImplementedError("Stage 3: SQL Generation - to be implemented")


def get_sql_custom_generation_prompt(
    question: str, entities: Dict[str, Any], schema: str
) -> str:
    """Generate prompt for Stage 3: SQL Generation (custom SQL) (TODO: Implement in Stage 3)."""
    raise NotImplementedError("Stage 3: SQL Generation - to be implemented")


def get_sql_syntax_validation_prompt(sql: str) -> str:
    """Generate prompt for Stage 4: SQL Validation Pass 1 (syntax) (TODO: Implement in Stage 4)."""
    raise NotImplementedError("Stage 4: SQL Validation - to be implemented")


def get_sql_semantic_validation_prompt(
    sql: str, question: str, entities: Dict[str, Any]
) -> str:
    """Generate prompt for Stage 4: SQL Validation Pass 2 (semantics) (TODO: Implement in Stage 4)."""
    raise NotImplementedError("Stage 4: SQL Validation - to be implemented")
