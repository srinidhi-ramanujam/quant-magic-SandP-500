"""
Azure OpenAI Client Wrapper with Pydantic Validation

This module provides a production-ready wrapper around Azure OpenAI's Responses API
with comprehensive error handling, retry logic, and token tracking.

Based on proven patterns from quant-magic-v2/llm/services/llm_service.py
"""

import json
import logging
import os
import re
import time
from typing import Optional, Dict, Any, Tuple, List
from functools import wraps

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from src.prompts import get_sql_custom_generation_prompt
from .models import (
    LLMConfig,
    LLMRequest,
    LLMResponse,
    LLMAnalysisRequest,
    LLMAnalysisResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    QueryComplexity,
    SQLValidationRequest,
    SQLValidationVerdict,
)

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles with each retry)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Don't retry on validation errors or missing credentials
                    if "validation" in str(e).lower() or "credential" in str(e).lower():
                        raise

                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed: {e}")

            raise last_exception

        return wrapper

    return decorator


class AzureOpenAIClient:
    """
    Production-ready Azure OpenAI client with Pydantic validation.

    Features:
    - Responses API integration (Azure OpenAI "responses" API per user preference)
    - Embeddings API support
    - Automatic retry with exponential backoff
    - Token usage tracking with reasoning breakdown (GPT-5 feature)
    - Cost estimation
    - Comprehensive error handling
    - Telemetry integration
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize Azure OpenAI client.

        Args:
            config: LLMConfig instance. If None, loads from environment variables.
        """
        self.config = config or LLMConfig()
        self.client: Optional[OpenAI] = None
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5

        # Initialize client
        self._initialize_client()

    def _initialize_client(self) -> bool:
        """
        Initialize OpenAI client with Azure endpoint workaround.

        Uses the proven pattern from quant-magic-v2 for Responses API compatibility.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if not OpenAI:
                logger.error(
                    "OpenAI library not installed. Install with: pip install openai>=2.0.0"
                )
                return False

            # Validate configuration
            if not self.config.azure_endpoint or not self.config.api_key:
                logger.error(
                    "Azure OpenAI configuration incomplete. Check environment variables."
                )
                return False

            # Check for mock/placeholder configuration
            if (
                "mock" in self.config.azure_endpoint.lower()
                or "your-api-key" in self.config.api_key
            ):
                logger.warning("Mock/placeholder Azure OpenAI configuration detected.")
                return False

            # Convert Azure endpoint to OpenAI-compatible base URL
            # This is the workaround for using OpenAI client with Azure endpoint
            base_url = self.config.azure_endpoint.rstrip("/") + "/openai/v1/"

            # Initialize OpenAI client with Azure endpoint
            # Set api-version as environment variable for Responses API
            os.environ["OPENAI_API_VERSION"] = "preview"

            self.client = OpenAI(api_key=self.config.api_key, base_url=base_url)

            logger.info(
                f"Azure OpenAI client initialized successfully. "
                f"Deployment: {self.config.deployment_name}, "
                f"API Version: {self.config.api_version}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            return False

    def is_available(self) -> bool:
        """
        Check if Azure OpenAI client is available and ready.

        Returns:
            bool: True if client is initialized and ready
        """
        return (
            self.client is not None
            and self._circuit_breaker_failures < self._circuit_breaker_threshold
        )

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def generate_sql(self, request: LLMRequest) -> LLMResponse:
        """
        Generate SQL query from natural language using Azure OpenAI Responses API.

        Args:
            request: LLMRequest with query and context

        Returns:
            LLMResponse with generated SQL, confidence, and metadata

        Raises:
            ValueError: If client not available or request validation fails
            Exception: For API errors after all retries exhausted
        """
        start_time = time.time()

        try:
            if not self.is_available():
                return LLMResponse(
                    success=False,
                    explanation="Azure OpenAI client not available - check configuration",
                    confidence=0.0,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    model_version="unavailable",
                    errors=["Client not configured or circuit breaker triggered"],
                )

            # Prepare SQL generation context
            schema_context = self._prepare_schema_context()
            constraints = self._prepare_constraints()

            # Build instructions for Responses API
            prompt_parts = get_sql_custom_generation_prompt(
                question=request.query,
                entities=request.context.get("entities", {}),
                schema=schema_context,
                constraints=constraints,
                domain_hints=request.context.get("domain_hints"),
                similar_queries=request.similar_queries,
                template_attempts=request.template_attempts,
            )

            instructions = prompt_parts["instructions"]
            input_prompt = prompt_parts["input"]

            # Call Azure OpenAI Responses API
            logger.info(f"Calling Responses API for query: {request.query[:100]}...")

            response = self.client.responses.create(
                model=self.config.deployment_name,
                instructions=instructions,
                input=input_prompt,
                max_output_tokens=request.max_tokens or self.config.max_tokens,
            )

            # Parse response
            generated_content = self._parse_api_response(response)

            # Extract SQL and explanation
            sql_query, explanation = self._extract_sql_and_explanation(
                generated_content
            )

            # Calculate confidence
            confidence = self._calculate_confidence(
                sql_query, explanation, request.query
            )

            # Extract token usage with reasoning breakdown
            token_usage = self._extract_token_usage(response)

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Reset circuit breaker on success
            self._circuit_breaker_failures = 0

            logger.info(
                f"SQL generation successful. Tokens: {token_usage.get('total_tokens', 0)}, "
                f"Time: {processing_time_ms}ms, Confidence: {confidence:.2f}"
            )

            return LLMResponse(
                success=True,
                generated_sql=sql_query,
                explanation=explanation,
                confidence=confidence,
                processing_time_ms=processing_time_ms,
                token_usage=token_usage,
                model_version=self.config.deployment_name,
                errors=[],
                warnings=[],
            )

        except Exception as e:
            self._circuit_breaker_failures += 1
            processing_time_ms = int((time.time() - start_time) * 1000)

            logger.error(f"Error generating SQL: {e}")

            return LLMResponse(
                success=False,
                explanation=f"Error generating SQL: {str(e)}",
                confidence=0.0,
                processing_time_ms=processing_time_ms,
                model_version=self.config.deployment_name,
                errors=[str(e)],
            )

    def validate_sql_semantic(
        self,
        request: SQLValidationRequest,
        instructions: str,
        input_prompt: str,
    ) -> SQLValidationVerdict:
        """Run semantic validation via the Responses API."""
        start_time = time.time()

        if not self.is_available():
            return SQLValidationVerdict(
                success=False,
                is_valid=False,
                reason="Azure OpenAI client not available",
                confidence=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                errors=["Client not configured or circuit breaker triggered"],
            )

        try:
            response = self.client.responses.create(
                model=self.config.deployment_name,
                instructions=instructions,
                input=input_prompt,
                max_output_tokens=request.max_tokens or self.config.max_tokens,
            )

            content = self._parse_api_response(response)
            payload = self._extract_json_object(content)

            verdict = SQLValidationVerdict(
                success=True,
                is_valid=bool(payload.get("is_valid", False)),
                reason=payload.get("reason"),
                confidence=float(payload.get("confidence", 0.0)),
                warnings=payload.get("warnings", []) or [],
                token_usage=self._extract_token_usage(response),
                processing_time_ms=int((time.time() - start_time) * 1000),
                raw_response=payload,
            )

            self._circuit_breaker_failures = 0
            return verdict

        except Exception as exc:  # noqa: BLE001
            self._circuit_breaker_failures += 1
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Semantic validation failed: {exc}")
            return SQLValidationVerdict(
                success=False,
                is_valid=False,
                reason=str(exc),
                confidence=0.0,
                processing_time_ms=processing_time_ms,
                errors=[str(exc)],
            )

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def analyze_query(self, request: LLMAnalysisRequest) -> LLMAnalysisResponse:
        """
        Analyze a failed query and provide recommendations.

        Args:
            request: LLMAnalysisRequest with failed query and context

        Returns:
            LLMAnalysisResponse with analysis and recommendations
        """
        try:
            if not self.is_available():
                return LLMAnalysisResponse(
                    analysis_success=False,
                    recommended_approach="Client not available",
                    reasoning="Azure OpenAI client not configured",
                    identified_complexity=QueryComplexity.SIMPLE,
                    required_tables=[],
                )

            # Build analysis prompt
            instructions = (
                "You are an expert at analyzing financial queries and SQL requirements. "
                "Analyze why a query failed and provide specific recommendations."
            )

            input_prompt = f"""
Analyze this failed query and provide recommendations:

Query: {request.failed_query}

Failure Context:
{request.failure_context}

Available Templates:
{', '.join(request.available_templates)}

Database Schema:
{request.schema_info}

Please provide:
1. Recommended approach to handle this query
2. Suggested SQL implementation (if applicable)
3. Detailed reasoning
4. Query complexity level (simple/medium/complex/advanced)
5. Required database tables
6. Required calculations
"""

            # Call Responses API
            response = self.client.responses.create(
                model=self.config.deployment_name,
                instructions=instructions,
                input=input_prompt,
                max_output_tokens=2000,
            )

            # Parse response
            content = self._parse_api_response(response)

            # Extract structured information
            recommended_approach = self._extract_recommendation(content)
            suggested_sql, _ = self._extract_sql_and_explanation(content)
            complexity = self._identify_complexity(content)
            required_tables = self._extract_required_tables(content)
            required_calculations = self._extract_calculations(content)

            return LLMAnalysisResponse(
                analysis_success=True,
                recommended_approach=recommended_approach,
                suggested_sql=suggested_sql,
                reasoning=content[:500],  # First 500 chars as reasoning
                identified_complexity=complexity,
                required_tables=required_tables,
                required_calculations=required_calculations,
            )

        except Exception as e:
            logger.error(f"Error analyzing query: {e}")

            return LLMAnalysisResponse(
                analysis_success=False,
                recommended_approach=f"Analysis failed: {str(e)}",
                reasoning=str(e),
                identified_complexity=QueryComplexity.SIMPLE,
                required_tables=[],
            )

    def generate_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        Generate embeddings for text (if embeddings deployment is available).

        Args:
            request: EmbeddingRequest with text to embed

        Returns:
            EmbeddingResponse with embedding vector or error
        """
        start_time = time.time()

        try:
            if not self.is_available():
                return EmbeddingResponse(success=False, error="Client not available")

            if not self.config.embeddings_deployment:
                return EmbeddingResponse(
                    success=False, error="Embeddings deployment not configured"
                )

            # Call embeddings API
            response = self.client.embeddings.create(
                input=request.text,
                model=request.model or self.config.embeddings_deployment,
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Extract embedding
            if response.data and len(response.data) > 0:
                embedding = response.data[0].embedding

                return EmbeddingResponse(
                    success=True,
                    embedding=embedding,
                    dimensions=len(embedding),
                    token_usage=(
                        response.usage.total_tokens if hasattr(response, "usage") else 0
                    ),
                    processing_time_ms=processing_time_ms,
                )
            else:
                return EmbeddingResponse(
                    success=False, error="No embedding data returned"
                )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Error generating embeddings: {e}")

            return EmbeddingResponse(
                success=False, processing_time_ms=processing_time_ms, error=str(e)
            )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _parse_api_response(self, response: Any) -> str:
        """
        Parse Azure OpenAI Responses API output using proven pattern.

        Args:
            response: Raw API response object

        Returns:
            str: Extracted text content
        """
        try:
            # Method 1: output_text attribute (simplest)
            if hasattr(response, "output_text"):
                return response.output_text

            # Method 2: Structured output parsing (GPT-5 format)
            if hasattr(response, "output"):
                output = response.output
                if isinstance(output, list) and len(output) > 0:
                    content_items = output[0].get("content", [])
                    for item in content_items:
                        if item.get("type") == "text":
                            text_value = item.get("text", {}).get("value", "")
                            if text_value:
                                return text_value

            # Fallback: convert to string
            return str(response)

        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            return ""

    def _extract_sql_and_explanation(self, content: str) -> Tuple[Optional[str], str]:
        """
        Extract SQL query and explanation from LLM response.

        Args:
            content: Raw LLM response text

        Returns:
            Tuple of (sql_query, explanation)
        """
        sql_query = None
        explanation = content

        try:
            # Look for SQL in code blocks (```sql ... ```)
            if "```sql" in content.lower():
                parts = content.lower().split("```sql")
                if len(parts) > 1:
                    sql_part = parts[1].split("```")[0]
                    sql_query = sql_part.strip()

            # Try generic code blocks
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    potential_sql = parts[1].strip()
                    # Check if it looks like SQL
                    if (
                        "SELECT" in potential_sql.upper()
                        or "FROM" in potential_sql.upper()
                    ):
                        sql_query = potential_sql

            # Look for SELECT statements without code blocks
            if not sql_query and "SELECT" in content.upper():
                lines = content.split("\n")
                sql_lines = []
                in_sql = False

                for line in lines:
                    if "SELECT" in line.upper() or in_sql:
                        in_sql = True
                        sql_lines.append(line)
                        if line.strip().endswith(";"):
                            break

                if sql_lines:
                    sql_query = "\n".join(sql_lines).strip()

            return sql_query, explanation

        except Exception as e:
            logger.error(f"Error extracting SQL: {e}")
            return None, f"Error parsing response: {str(e)}"

    def _extract_json_object(self, content: str) -> Dict[str, Any]:
        """Extract JSON object from the LLM response content."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        if "```" in content:
            start = content.find("```")
            end = content.find("```", start + 3)
            if end > start:
                snippet = content[start + 3 : end].strip()
                # Handle potential language hint like ```json
                if snippet.lower().startswith("json"):
                    snippet = snippet[4:].strip()
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    pass

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            snippet = json_match.group()
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass

        raise ValueError("Unable to extract JSON payload from validator response")

    def _extract_token_usage(self, response: Any) -> Dict[str, Any]:
        """
        Extract token usage with reasoning breakdown (GPT-5 feature).

        Args:
            response: API response object

        Returns:
            Dict with token usage statistics
        """
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        try:
            if hasattr(response, "usage") and response.usage:
                token_usage["prompt_tokens"] = getattr(
                    response.usage, "input_tokens", 0
                )
                token_usage["completion_tokens"] = getattr(
                    response.usage, "output_tokens", 0
                )
                token_usage["total_tokens"] = getattr(response.usage, "total_tokens", 0)

                # Extract reasoning tokens (GPT-5 specific)
                if hasattr(response.usage, "output_tokens_details"):
                    details = response.usage.output_tokens_details
                    if hasattr(details, "reasoning_tokens"):
                        reasoning_tokens = details.reasoning_tokens
                        regular_tokens = (
                            token_usage["completion_tokens"] - reasoning_tokens
                        )

                        token_usage.update(
                            {
                                "reasoning_tokens": reasoning_tokens,
                                "regular_output_tokens": regular_tokens,
                                "reasoning_percentage": (
                                    (
                                        reasoning_tokens
                                        / token_usage["completion_tokens"]
                                        * 100
                                    )
                                    if token_usage["completion_tokens"] > 0
                                    else 0
                                ),
                            }
                        )

        except Exception as e:
            logger.warning(f"Error extracting token usage: {e}")

        return token_usage

    def _calculate_confidence(
        self, sql_query: Optional[str], explanation: str, original_query: str
    ) -> float:
        """
        Calculate confidence score for generated SQL.

        Args:
            sql_query: Generated SQL query
            explanation: LLM explanation
            original_query: Original natural language query

        Returns:
            float: Confidence score 0.0-1.0
        """
        confidence = 0.5  # Base confidence

        # SQL quality checks
        if sql_query:
            confidence += 0.3
            sql_upper = sql_query.upper()

            if "SELECT" in sql_upper:
                confidence += 0.05
            if "FROM" in sql_upper:
                confidence += 0.05
            if "JOIN" in sql_upper or "WHERE" in sql_upper:
                confidence += 0.05
            if ";" in sql_query:  # Proper termination
                confidence += 0.02

        # Explanation quality
        if len(explanation) > 50:
            confidence += 0.03

        return min(confidence, 1.0)

    def _prepare_schema_context(self) -> str:
        """Prepare database schema context for SQL generation."""
        from src.schema_docs import schema_for_prompt

        return schema_for_prompt()

    def _prepare_constraints(self) -> str:
        """Prepare SQL generation constraints."""
        return """
- Only use registered DuckDB views: companies, sub, num, tag, pre
- Handle NULL values explicitly (COALESCE or filters) when comparing metrics
- Join num through sub (num.adsh = sub.adsh) before joining to companies
- CIK fields are 10-character strings, zero-padded on the left
- Prefer COUNT(DISTINCT ...) for company counts
- Keep answer sets small with LIMIT when returning ordered lists
- Avoid cross joins or cartesian products unless absolutely required
"""

    def _extract_recommendation(self, content: str) -> str:
        """Extract recommendation from analysis content."""
        lines = content.split("\n")
        for line in lines:
            if "recommend" in line.lower() or "approach" in line.lower():
                return line.strip()
        return "See full analysis for recommendations"

    def _identify_complexity(self, content: str) -> QueryComplexity:
        """Identify query complexity from analysis."""
        content_lower = content.lower()
        if "advanced" in content_lower:
            return QueryComplexity.ADVANCED
        elif "complex" in content_lower:
            return QueryComplexity.COMPLEX
        elif "medium" in content_lower:
            return QueryComplexity.MEDIUM
        else:
            return QueryComplexity.SIMPLE

    def _extract_required_tables(self, content: str) -> List[str]:
        """Extract required tables from analysis."""
        tables = []
        content_lower = content.lower()

        for table in [
            "num",
            "companies_with_sectors",
            "companies",
            "sub",
            "tag",
            "pre",
        ]:
            if table in content_lower:
                tables.append(table)

        return list(set(tables))  # Remove duplicates

    def _extract_calculations(self, content: str) -> List[str]:
        """Extract required calculations from analysis."""
        calculations = []
        content_lower = content.lower()

        calc_keywords = [
            "ratio",
            "percentage",
            "margin",
            "growth",
            "average",
            "sum",
            "total",
            "roe",
            "roa",
        ]
        for keyword in calc_keywords:
            if keyword in content_lower:
                calculations.append(keyword)

        return list(set(calculations))  # Remove duplicates


def get_azure_client(config: Optional[LLMConfig] = None) -> AzureOpenAIClient:
    """
    Factory function to get Azure OpenAI client instance.

    Args:
        config: Optional LLMConfig. If None, loads from environment.

    Returns:
        AzureOpenAIClient instance
    """
    return AzureOpenAIClient(config=config)
