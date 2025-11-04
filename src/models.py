"""
Pydantic models for type-safe data contracts across all components.

These models ensure consistent data structures throughout the query pipeline.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator
import pandas as pd
import os


class QueryRequest(BaseModel):
    """User's natural language query request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    question: str = Field(
        ..., description="Natural language question from user", min_length=1
    )
    user_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context about the user (role, preferences, etc.)",
    )
    debug_mode: bool = Field(
        default=False, description="Whether to return debug information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the request was made"
    )


class ExtractedEntities(BaseModel):
    """Entities extracted from natural language question."""

    companies: List[str] = Field(
        default_factory=list, description="Company names or CIKs mentioned"
    )
    metrics: List[str] = Field(
        default_factory=list,
        description="Financial metrics requested (revenue, assets, CIK, etc.)",
    )
    sectors: List[str] = Field(
        default_factory=list, description="GICS sectors mentioned"
    )
    time_periods: List[str] = Field(
        default_factory=list,
        description="Time periods mentioned (Q1 2024, FY2023, etc.)",
    )
    question_type: Optional[str] = Field(
        default=None, description="Type of question (count, lookup, comparison, etc.)"
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence score 0-1 for extraction accuracy",
        ge=0.0,
        le=1.0,
    )


class QueryTemplate(BaseModel):
    """Template for query intelligence matching."""

    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Human-readable template name")
    pattern: str = Field(..., description="Pattern to match questions")
    sql_template: str = Field(..., description="SQL template with placeholders")
    parameters: List[str] = Field(
        default_factory=list, description="List of parameters needed"
    )
    description: Optional[str] = Field(
        default=None, description="Description of what this template does"
    )


class IntelligenceMatch(BaseModel):
    """Result of matching question to intelligence templates."""

    template: Optional[QueryTemplate] = Field(
        default=None, description="Matched template if found"
    )
    match_confidence: float = Field(
        default=0.0, description="Confidence in template match (0-1)", ge=0.0, le=1.0
    )
    matched_parameters: Dict[str, str] = Field(
        default_factory=dict, description="Parameters extracted for template"
    )
    fallback_to_llm: bool = Field(
        default=False, description="Whether to fallback to LLM generation"
    )


class GeneratedSQL(BaseModel):
    """Generated SQL query with metadata."""

    sql: str = Field(..., description="SQL query to execute", min_length=1)
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters used in SQL generation"
    )
    template_id: Optional[str] = Field(
        default=None, description="Template used for generation (if any)"
    )
    generation_method: str = Field(
        default="template", description="How SQL was generated (template, llm, hybrid)"
    )
    confidence: float = Field(
        default=1.0, description="Confidence in SQL correctness (0-1)", ge=0.0, le=1.0
    )


class QueryResult(BaseModel):
    """Raw results from query execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: Any = Field(..., description="Query results (DataFrame, dict, or list)")
    row_count: int = Field(..., description="Number of rows returned", ge=0)
    columns: List[str] = Field(default_factory=list, description="Column names")
    execution_time_seconds: float = Field(
        ..., description="Query execution time", ge=0.0
    )
    sql_executed: str = Field(..., description="SQL that was executed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary, handling DataFrame conversion."""
        if isinstance(self.data, pd.DataFrame):
            data_dict = self.data.to_dict(orient="records")
        elif isinstance(self.data, list):
            data_dict = self.data
        else:
            data_dict = {"result": self.data}

        return {
            "data": data_dict,
            "row_count": self.row_count,
            "columns": self.columns,
            "execution_time_seconds": round(self.execution_time_seconds, 4),
        }


class FormattedResponse(BaseModel):
    """Final formatted response to user."""

    answer: str = Field(..., description="Natural language answer", min_length=1)
    confidence: float = Field(
        default=1.0,
        description="Overall confidence in answer accuracy (0-1)",
        ge=0.0,
        le=1.0,
    )
    sources: List[str] = Field(default_factory=list, description="Data sources used")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (timing, debug info, etc.)",
    )
    success: bool = Field(default=True, description="Whether request was successful")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    # Debug information (only populated if debug_mode=True)
    debug_info: Optional[Dict[str, Any]] = Field(
        default=None, description="Debug information (entities, SQL, timings)"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "answer": self.answer,
            "confidence": round(self.confidence, 3),
            "sources": self.sources,
            "metadata": self.metadata,
            "success": self.success,
        }

        if self.error:
            result["error"] = self.error

        if self.debug_info:
            result["debug_info"] = self.debug_info

        return result


class TelemetryData(BaseModel):
    """Telemetry data for performance tracking."""

    request_id: str = Field(..., description="Unique request identifier")
    question: str = Field(..., description="Original question")
    total_time_seconds: float = Field(..., description="Total processing time", ge=0.0)
    component_timings: Dict[str, float] = Field(
        default_factory=dict, description="Timing breakdown by component"
    )
    success: bool = Field(..., description="Whether request succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    llm_calls: List[Dict[str, Any]] = Field(
        default_factory=list, description="Details of LLM API calls made"
    )
    cache_hit: bool = Field(default=False, description="Whether result was cached")

    def telemetry_overhead_pct(self) -> float:
        """Calculate telemetry overhead as percentage."""
        component_total = sum(self.component_timings.values())
        if self.total_time_seconds == 0:
            return 0.0
        overhead = self.total_time_seconds - component_total
        return max(0.0, (overhead / self.total_time_seconds) * 100)


# ============================================================================
# LLM-Specific Models for Azure OpenAI Integration
# ============================================================================


class QueryComplexity(str, Enum):
    """Query complexity levels for LLM routing."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    ADVANCED = "advanced"


class LLMConfig(BaseModel):
    """Azure OpenAI configuration with environment variable support."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    azure_endpoint: str = Field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_ENDPOINT", "https://your-resource.openai.azure.com/"
        ),
        description="Azure OpenAI endpoint URL",
    )
    api_key: str = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""),
        description="Azure OpenAI API key",
    )
    api_version: str = Field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
        ),
        description="Azure OpenAI API version",
    )
    deployment_name: str = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5"),
        description="Azure OpenAI deployment name for Responses API",
    )
    embeddings_deployment: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"),
        description="Azure OpenAI embeddings deployment name",
    )

    # LLM parameters
    max_tokens: int = Field(
        default=4000, description="Maximum tokens for LLM response", gt=0
    )
    temperature: float = Field(
        default=0.1,
        description="Temperature for deterministic responses",
        ge=0.0,
        le=2.0,
    )
    timeout: int = Field(default=30, description="Request timeout in seconds", gt=0)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key is not empty or placeholder."""
        if not v or v == "your-api-key-here":
            raise ValueError("Valid Azure OpenAI API key required")
        return v


class LLMRequest(BaseModel):
    """Request for LLM-powered SQL generation."""

    query: str = Field(..., min_length=1, description="Natural language query")
    complexity: Optional[QueryComplexity] = Field(
        None, description="Detected query complexity"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context for generation"
    )

    # Query routing metadata
    similar_queries: List[Dict[str, Any]] = Field(
        default_factory=list, description="Vector similarity results"
    )
    template_attempts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Failed template attempts"
    )

    # Configuration overrides
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "What was Apple's revenue in 2024?",
                "complexity": "simple",
                "context": {"company_symbol": "AAPL", "year": 2024},
            }
        }
    )


class LLMResponse(BaseModel):
    """Response from LLM SQL generation."""

    success: bool = Field(..., description="Whether query was processed successfully")
    generated_sql: Optional[str] = Field(None, description="Generated SQL query")
    explanation: str = Field(
        ..., description="Human-readable explanation of the approach"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score in generation"
    )

    # Execution metadata
    processing_time_ms: int = Field(
        ..., description="LLM processing time in milliseconds", ge=0
    )
    token_usage: Dict[str, Any] = Field(
        default_factory=dict,
        description="Token usage with reasoning breakdown (GPT-5 feature)",
    )
    model_version: str = Field(..., description="LLM model version used")

    # Error handling
    errors: List[str] = Field(default_factory=list, description="Processing errors")
    warnings: List[str] = Field(default_factory=list, description="Processing warnings")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "generated_sql": "SELECT value FROM num WHERE tag = 'Revenues' AND cik = '320193'",
                "explanation": "Generated SQL to retrieve Apple's revenue",
                "confidence": 0.95,
                "processing_time_ms": 1250,
                "token_usage": {
                    "prompt_tokens": 850,
                    "completion_tokens": 120,
                    "reasoning_tokens": 95,
                },
                "model_version": "gpt-5",
            }
        }
    )


class LLMAnalysisRequest(BaseModel):
    """Request for LLM-powered analysis of query patterns."""

    failed_query: str = Field(
        ..., description="Query that failed template/vector routing"
    )
    failure_context: Dict[str, Any] = Field(
        ..., description="Context about the failure"
    )
    available_templates: List[str] = Field(
        ..., description="Available template categories"
    )
    schema_info: Dict[str, Any] = Field(..., description="Database schema information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "failed_query": "Which companies have the highest profit margins?",
                "failure_context": {
                    "template_attempts": ["revenue_template", "ratio_template"],
                    "vector_similarity": 0.65,
                },
                "available_templates": ["financial_ratios", "company_comparison"],
                "schema_info": {"tables": ["num", "companies"]},
            }
        }
    )


class LLMAnalysisResponse(BaseModel):
    """Response from LLM analysis service."""

    analysis_success: bool = Field(..., description="Whether analysis was completed")
    recommended_approach: str = Field(..., description="Recommended query approach")
    suggested_sql: Optional[str] = Field(None, description="Suggested SQL implementation")
    reasoning: str = Field(..., description="Detailed reasoning for the approach")

    # Classification results
    identified_complexity: QueryComplexity = Field(
        ..., description="Identified query complexity"
    )
    required_tables: List[str] = Field(..., description="Database tables needed")
    required_calculations: List[str] = Field(
        default_factory=list, description="Required calculations"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "analysis_success": True,
                "recommended_approach": "Calculate profit margin using revenue and net income",
                "reasoning": "Profit margin requires revenue and net income data",
                "identified_complexity": "medium",
                "required_tables": ["num", "companies"],
            }
        }
    )


class EmbeddingRequest(BaseModel):
    """Request for embeddings generation."""

    text: str = Field(..., min_length=1, description="Text to embed")
    model: Optional[str] = Field(None, description="Embedding model/deployment name")
    dimensions: Optional[int] = Field(
        None, gt=0, description="Target embedding dimensions"
    )


class EmbeddingResponse(BaseModel):
    """Response from embeddings generation."""

    success: bool = Field(..., description="Whether embedding was generated")
    embedding: Optional[List[float]] = Field(None, description="Embedding vector")
    dimensions: int = Field(default=0, ge=0, description="Vector dimensions")
    token_usage: int = Field(default=0, ge=0, description="Tokens used")
    processing_time_ms: int = Field(
        default=0, ge=0, description="Processing time in milliseconds"
    )
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# Stage 1: Entity Extraction Models
# ============================================================================


class LLMEntityRequest(BaseModel):
    """Request for LLM-assisted entity extraction."""

    question: str = Field(..., min_length=1, description="Natural language question")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional context for extraction"
    )

    # Configuration overrides
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What is Apple's revenue in Q3 2024?",
                "context": {},
            }
        }
    )


class LLMEntityResponse(BaseModel):
    """Response from LLM entity extraction."""

    companies: List[str] = Field(
        default_factory=list, description="Extracted company names (standardized)"
    )
    metrics: List[str] = Field(
        default_factory=list, description="Extracted financial metrics (normalized)"
    )
    sectors: List[str] = Field(
        default_factory=list, description="Extracted GICS sectors (official names)"
    )
    time_periods: List[str] = Field(
        default_factory=list,
        description="Extracted time periods (years, quarters, 'latest')",
    )
    question_type: str = Field(
        ...,
        description="Type of question: lookup, count, list, comparison, calculation, trend",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM's confidence in extraction quality (0-1)",
    )
    reasoning: str = Field(
        ..., description="LLM's reasoning for extraction decisions"
    )

    # Processing metadata
    processing_time_ms: int = Field(
        default=0, ge=0, description="LLM processing time in milliseconds"
    )
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token usage breakdown (prompt_tokens, completion_tokens)",
    )

    # Validation
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: str) -> str:
        """Validate question type is one of allowed values."""
        allowed_types = ["lookup", "count", "list", "comparison", "calculation", "trend"]
        if v.lower() not in allowed_types:
            raise ValueError(
                f"Question type must be one of: {', '.join(allowed_types)}"
            )
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "companies": ["APPLE INC"],
                "metrics": ["revenue"],
                "sectors": [],
                "time_periods": ["Q3", "2024"],
                "question_type": "lookup",
                "confidence": 0.95,
                "reasoning": "Ticker AAPL converted to APPLE INC. Revenue metric and Q3 2024 period clearly identified.",
                "processing_time_ms": 1200,
                "token_usage": {"prompt_tokens": 120, "completion_tokens": 36},
            }
        }
    )


# ============================================================================
# Stage 2: Template Selection Models
# ============================================================================


class LLMTemplateSelectionRequest(BaseModel):
    """Request for LLM-assisted template selection."""

    question: str = Field(..., min_length=1, description="Natural language question")
    entities: Dict[str, Any] = Field(
        ..., description="Extracted entities from Stage 1"
    )
    candidate_templates: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of candidate templates from deterministic matching",
    )

    # Configuration overrides
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "How many companies in Technology?",
                "entities": {
                    "companies": [],
                    "metrics": [],
                    "sectors": ["Information Technology"],
                    "time_periods": [],
                    "question_type": "count",
                },
                "candidate_templates": [
                    {
                        "template_id": "sector_company_count",
                        "name": "Count companies by sector",
                        "parameters": ["sector"],
                    }
                ],
            }
        }
    )


class LLMTemplateSelectionResponse(BaseModel):
    """Response from LLM template selection."""

    selected_template_id: Optional[str] = Field(
        None, description="ID of selected template, or null if custom SQL needed"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in template selection (0-1)"
    )
    reasoning: str = Field(..., description="Explanation of selection decision")
    use_custom_sql: bool = Field(
        ..., description="Whether custom SQL generation is recommended"
    )
    parameter_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of template parameters to entity values",
    )

    # Processing metadata
    processing_time_ms: int = Field(
        default=0, ge=0, description="LLM processing time in milliseconds"
    )
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token usage breakdown (prompt_tokens, completion_tokens)",
    )

    # Validation
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "selected_template_id": "sector_company_count",
                "confidence": 0.92,
                "reasoning": "Question asks for count by sector, template matches exactly.",
                "use_custom_sql": False,
                "parameter_mapping": {"sector": "Information Technology"},
                "processing_time_ms": 800,
                "token_usage": {"prompt_tokens": 89, "completion_tokens": 42},
            }
        }
    )
