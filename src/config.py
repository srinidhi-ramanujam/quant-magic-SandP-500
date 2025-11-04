"""
Configuration management for the financial analysis system.

Keep this simple - just paths and basic settings.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file (always prefer repo .env)
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)


class Config(BaseModel):
    """Application configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    data_dir: Optional[Path] = Field(default=None)
    parquet_dir: Optional[Path] = Field(default=None)
    evaluation_dir: Optional[Path] = Field(default=None)

    # Database settings
    duckdb_memory_limit: str = Field(
        default_factory=lambda: os.getenv("DUCKDB_MEMORY_LIMIT", "4GB")
    )
    duckdb_threads: int = Field(
        default_factory=lambda: int(os.getenv("DUCKDB_THREADS", "4"))
    )

    # Query settings
    default_limit: int = 100
    query_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
    )

    # Azure OpenAI settings
    azure_openai_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    azure_openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY")
    )
    azure_openai_deployment_name: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5")
    )
    azure_openai_api_version: str = Field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
        )
    )

    # Stage 1: Entity Extraction Settings
    entity_extraction_model: str = Field(
        default_factory=lambda: os.getenv("ENTITY_EXTRACTION_MODEL", "gpt-5"),
        description="Model to use for entity extraction (uses azure_openai_deployment_name)",
    )
    entity_extraction_temperature: float = Field(
        default=0.0,
        description="Temperature for entity extraction (0.0 for deterministic)",
    )
    entity_extraction_max_retries: int = Field(
        default=2, description="Maximum retry attempts for entity extraction"
    )
    entity_extraction_timeout: int = Field(
        default=30, description="Timeout for entity extraction in seconds"
    )

    # Stage 2: Template Selection Settings
    template_selection_fast_path_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for fast path (skip LLM)",
    )
    template_selection_llm_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to consider deterministic candidates",
    )
    template_selection_temperature: float = Field(
        default=0.0,
        description="Temperature for template selection (0.0 for deterministic)",
    )
    template_selection_max_retries: int = Field(
        default=3, ge=1, description="Max retries for LLM template selection"
    )
    template_selection_timeout: int = Field(
        default=10, ge=1, description="Timeout for LLM template selection (seconds)"
    )

    # Application settings
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    enable_telemetry: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_TELEMETRY", "true").lower() == "true"
    )
    cache_enabled: bool = Field(
        default_factory=lambda: os.getenv("CACHE_ENABLED", "false").lower() == "true"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Set up paths relative to project root
        if self.data_dir is None:
            self.data_dir = self.project_root / "data"
        if self.parquet_dir is None:
            self.parquet_dir = self.data_dir / "parquet"
        if self.evaluation_dir is None:
            self.evaluation_dir = self.project_root / "evaluation"


# Global config instance
_config = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


# Convenience function for common paths
def get_parquet_path(filename: str) -> Path:
    """Get full path to a parquet file."""
    return get_config().parquet_dir / filename
