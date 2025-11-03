"""
Configuration management for the financial analysis system.

Keep this simple - just paths and basic settings.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


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
        default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
    )
    azure_openai_api_version: str = Field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
        )
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
