"""
LLM-powered answer formatting for polished business-ready narratives.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from src.azure_client import AzureOpenAIClient
from src.config import Config, get_config
from src.models import (
    ConversationTurn,
    ExtractedEntities,
    PresentationPayload,
    PresentationTable,
    QueryResult,
)
from src.prompts import get_answer_formatter_prompt
from src.telemetry import RequestContext, get_logger


@dataclass
class FormatterOutcome:
    """Structured result returned by the AnswerFormatter."""

    presentation: Optional[PresentationPayload] = None
    latency_ms: Optional[int] = None
    token_usage: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[str] = None
    prompt_preview: Optional[str] = None


class AnswerFormatter:
    """Optional LLM pass that polishes deterministic answers."""

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        azure_client: Optional[AzureOpenAIClient] = None,
    ) -> None:
        self.logger = get_logger()
        self.config = config or get_config()
        self.max_rows = int(getattr(self.config, "formatter_max_rows", 5))
        self.history_limit = int(getattr(self.config, "formatter_history_limit", 3))
        self.temperature = float(getattr(self.config, "formatter_temperature", 0.2))
        self.max_tokens = int(getattr(self.config, "formatter_max_tokens", 900))
        self.enabled = bool(getattr(self.config, "formatter_enabled", True))

        self.azure_client = azure_client

        if not self.enabled:
            self.logger.info("AnswerFormatter disabled via configuration flag.")
            return

        if self.azure_client is None:
            try:
                self.azure_client = AzureOpenAIClient()
            except Exception as exc:  # noqa: BLE001 - propagate as availability error
                self.enabled = False
                self.logger.warning(
                    "AnswerFormatter disabled: unable to initialize Azure client (%s)",
                    exc,
                )

        if self.azure_client and not self.azure_client.is_available():
            self.logger.warning("AnswerFormatter disabled: Azure client unavailable.")
            self.enabled = False

    def is_available(self) -> bool:
        """Return True when the formatter can make LLM calls."""
        return self.enabled and self.azure_client is not None

    def format_answer(
        self,
        *,
        question: str,
        base_answer: str,
        query_result: Optional[QueryResult],
        entities: Optional[ExtractedEntities],
        template_id: Optional[str],
        context: RequestContext,
        history: Optional[Sequence[ConversationTurn]] = None,
    ) -> FormatterOutcome:
        """
        Generate a polished presentation payload using Azure Responses API.
        """
        request_id = context.request_id if context else "n/a"
        if not self.is_available():
            return FormatterOutcome(
                error="formatter_unavailable",
                warnings=["LLM formatter disabled - returning base answer"],
            )

        if not query_result:
            return FormatterOutcome(
                error="no_query_result",
                warnings=["Formatter skipped because no query result was available."],
            )

        rows_payload, truncated = self._prepare_rows(query_result)
        if not rows_payload:
            return FormatterOutcome(
                error="empty_rows",
                warnings=["Formatter skipped due to empty dataset."],
            )

        history_payload = self._prepare_history(history)

        template_hint = template_id
        if entities and entities.question_type:
            template_hint = (
                f"{template_id or 'unspecified'} · {entities.question_type} query"
            )

        prompt = get_answer_formatter_prompt(
            question=question,
            base_answer=base_answer,
            result_rows=rows_payload,
            template_hint=template_hint,
            history=history_payload,
        )

        model_name = self.azure_client.config.deployment_name
        start_time = time.time()

        prompt_preview = prompt[:2000]

        try:
            response = self.azure_client.client.responses.create(
                model=model_name,
                input=prompt,
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except Exception as exc:  # noqa: BLE001 - convert to availability error
            self.logger.warning("AnswerFormatter failed [%s]: %s", request_id, exc)
            return FormatterOutcome(
                error=str(exc),
                warnings=["Formatter call failed; falling back to template answer."],
                prompt_preview=prompt_preview,
            )

        latency_ms = int((time.time() - start_time) * 1000)
        token_usage = self.azure_client._extract_token_usage(response)
        content = self.azure_client._parse_api_response(response)

        try:
            payload_dict = json.loads(content)
            presentation = PresentationPayload(**payload_dict)
        except Exception as exc:  # noqa: BLE001 - JSON parse/validation failure
            self.logger.warning(
                "AnswerFormatter returned invalid payload [%s]: %s | content=%s",
                request_id,
                exc,
                content,
            )
            return FormatterOutcome(
                error="invalid_payload",
                warnings=["Formatter output invalid JSON; showing fallback answer."],
                raw_response=content,
                prompt_preview=prompt_preview,
            )

        if presentation.table and truncated:
            presentation.table.truncated = True
        elif presentation.table is None and rows_payload:
            # Provide a minimal table if LLM omitted it but we truncated rows.
            table = PresentationTable(
                columns=list(rows_payload[0].keys()),
                rows=rows_payload,
                truncated=truncated,
            )
            presentation.table = table

        warnings = list(presentation.warnings or [])
        if truncated and "Formatter skipped due to empty dataset." not in warnings:
            warnings.append("Displayed rows truncated to fit formatter budget.")
        presentation.warnings = warnings

        return FormatterOutcome(
            presentation=presentation,
            latency_ms=latency_ms,
            token_usage=token_usage,
            warnings=warnings,
            raw_response=content,
            prompt_preview=prompt_preview,
        )

    def _prepare_history(
        self, history: Optional[Sequence[ConversationTurn]]
    ) -> List[Dict[str, str]]:
        """Convert ConversationTurn objects into dictionaries for the prompt."""
        if not history:
            return []

        trimmed = list(history)[-self.history_limit :]
        payload: List[Dict[str, str]] = []
        for turn in trimmed:
            payload.append({"role": turn.role, "content": turn.content})
        return payload

    def _prepare_rows(self, query_result: QueryResult) -> tuple[List[Dict[str, Any]], bool]:
        """Normalize query results into JSON-friendly rows."""
        if query_result.row_count == 0:
            return [], False

        data = query_result.data
        truncated = False
        rows: List[Dict[str, Any]] = []

        if isinstance(data, pd.DataFrame):
            truncated = len(data) > self.max_rows
            snapshot = data.head(self.max_rows).copy()
            rows = self._sanitize_records(snapshot.to_dict(orient="records"))
        elif isinstance(data, list):
            truncated = len(data) > self.max_rows
            rows = self._sanitize_records(data[: self.max_rows])
        elif isinstance(data, dict):
            rows = [self._sanitize_record(data)]
        else:
            rows = [{"value": str(data)}]

        return rows, truncated

    def _sanitize_records(self, records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert numpy/pandas/numeric values to JSON-friendly scalars."""
        return [self._sanitize_record(record) for record in records]

    @staticmethod
    def _sanitize_record(record: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for key, value in record.items():
            if hasattr(value, "item"):
                try:
                    value = value.item()
                except Exception:  # noqa: BLE001 - fallback to raw value
                    value = str(value)

            if isinstance(value, float):
                if pd.isna(value):
                    sanitized[key] = None
                else:
                    sanitized[key] = float(value)
            elif isinstance(value, (int, str, bool)) or value is None:
                sanitized[key] = value
            else:
                sanitized[key] = str(value)
        return sanitized
