"""
Utilities for enforcing Azure OpenAI availability across the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.azure_client import AzureOpenAIClient


@dataclass(frozen=True)
class LLMAvailabilityError(RuntimeError):
    """Raised when the Azure OpenAI client cannot be initialized or is offline."""

    message: str

    def __str__(self) -> str:  # pragma: no cover - dataclass convenience
        return self.message


def ensure_llm_available(context: str) -> None:
    """
    Validate Azure OpenAI availability; raise if the client cannot be used.

    Args:
        context: Human-readable description of why the check is being performed.

    Raises:
        LLMAvailabilityError: If the client is missing configuration or unavailable.
    """
    try:
        client = AzureOpenAIClient()
    except Exception as exc:  # noqa: BLE001 - surface raw initialization issue
        raise LLMAvailabilityError(
            f"{context}: failed to initialize Azure OpenAI client ({exc})"
        ) from exc

    if not client.is_available():
        raise LLMAvailabilityError(
            f"{context}: Azure OpenAI client is not available. "
            "Ensure endpoint, API key, and network access are configured."
        )
