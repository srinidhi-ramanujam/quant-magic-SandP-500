"""
Session-level logging utilities for capturing question/answer pairs.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.models import ExtractedEntities, FormattedResponse, GeneratedSQL
from src.telemetry import RequestContext

_LOG_FILE = os.getenv("SESSION_LOG_FILE")
_LOCK = threading.Lock()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _serialize_entities(entities: Optional[ExtractedEntities]) -> Optional[dict]:
    if not entities:
        return None
    try:
        return entities.model_dump()
    except AttributeError:
        # Backward compatibility if old pydantic method is used
        return entities.dict()


def _serialize_response(response: FormattedResponse) -> dict:
    return {
        "answer": response.answer,
        "success": response.success,
        "error": response.error,
        "confidence": response.confidence,
        "metadata": response.metadata,
        "debug_info": response.debug_info,
        "sources": response.sources,
    }


def _serialize_generated_sql(
    generated_sql: Optional[GeneratedSQL],
) -> Optional[dict]:
    if not generated_sql:
        return None
    return {
        "sql": generated_sql.sql,
        "template_id": generated_sql.template_id,
        "generation_method": generated_sql.generation_method,
        "confidence": generated_sql.confidence,
        "parameters": generated_sql.parameters,
    }


def log_interaction(
    *,
    channel: str,
    question: str,
    response: FormattedResponse,
    context: RequestContext,
    entities: Optional[ExtractedEntities],
    generated_sql: Optional[GeneratedSQL],
    debug_mode: bool,
) -> None:
    """
    Append a structured log entry for a Q&A interaction.

    Args:
        channel: Source of the request ("cli", "api", etc.)
        question: Natural language question asked by the user
        response: FormattedResponse returned to the user
        context: RequestContext carrying timings/metadata
        entities: Extracted entities (if available)
        generated_sql: Generated SQL metadata (if available)
        debug_mode: Whether debug mode was enabled for the request
    """
    if not _LOG_FILE:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "question": question,
        "request_id": context.request_id,
        "debug_mode": debug_mode,
        "response": _serialize_response(response),
        "entities": _serialize_entities(entities),
        "generated_sql": _serialize_generated_sql(generated_sql),
        "component_timings": context.component_timings,
        "context_metadata": context.metadata,
    }

    path = Path(_LOG_FILE)
    _ensure_parent(path)

    json_line = json.dumps(record, default=str)

    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json_line + "\n")
