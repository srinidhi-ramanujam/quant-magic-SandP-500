"""
SQL validation utilities providing static and semantic checks.

The validator executes two passes:
1. Static analysis to catch dangerous patterns before execution.
2. Optional semantic validation via Azure OpenAI to ensure the SQL matches
   the user's intent. Results are recorded in the request telemetry.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple, Any, List

from src.prompts import get_sql_semantic_validation_prompt
from src.schema_docs import schema_for_prompt
from src.models import (
    SQLValidationRequest,
    SQLValidationVerdict,
)
from src.telemetry import get_logger, RequestContext


class SQLValidator:
    """Perform static and semantic validation for generated SQL queries."""

    _ALLOWED_TABLES = {"COMPANIES", "SUB", "NUM", "TAG", "PRE"}
    _DANGEROUS_KEYWORDS = {
        "DROP",
        "DELETE",
        "INSERT",
        "UPDATE",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "MERGE",
    }

    def __init__(self, use_llm: bool = True):
        self.logger = get_logger()
        self.use_llm = bool(use_llm)
        self.azure_client = None

        if self.use_llm:
            try:
                from src.azure_client import AzureOpenAIClient

                client = AzureOpenAIClient()
                if client.is_available():
                    self.azure_client = client
                    self.logger.info(
                        "SQLValidator initialized with LLM semantic checks"
                    )
                else:
                    self.logger.warning(
                        "Azure OpenAI client unavailable – semantic validation disabled"
                    )
                    self.use_llm = False
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    f"Failed to initialize Azure client for validator: {exc}"
                )
                self.use_llm = False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def validate_static(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Run static validation checks."""
        if not sql or not sql.strip():
            return False, "SQL is empty"

        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()

        for keyword in self._DANGEROUS_KEYWORDS:
            if keyword in sql_upper:
                return False, f"Disallowed keyword detected: {keyword}"

        normalized_start = sql_upper.lstrip()
        if not (
            normalized_start.startswith("SELECT") or normalized_start.startswith("WITH")
        ):
            return False, "SQL must start with SELECT or WITH"

        # Ensure a SELECT statement either begins with SELECT directly or the first
        # non-CTE block does.
        if normalized_start.startswith("WITH"):
            if "SELECT" not in normalized_start:
                return False, "WITH queries must include a SELECT statement"
        elif not normalized_start.startswith("SELECT"):
            return False, "SQL must start with SELECT or WITH"

        if "FROM" not in sql_upper:
            return False, "SQL must include a FROM clause"

        semicolons = [idx for idx, char in enumerate(sql_stripped) if char == ";"]
        if len(semicolons) > 1:
            return False, "Multiple SQL statements detected"
        if semicolons:
            trailing = sql_stripped[semicolons[-1] + 1 :].strip()
            if trailing:
                return False, "Additional content found after semicolon"

        # Collect CTE names to avoid misclassifying them as unknown tables.
        cte_names = set(
            re.findall(r"\bWITH\s+([A-Z_][A-Z0-9_]*)\s+AS", sql_upper)
            + re.findall(r",\s*([A-Z_][A-Z0-9_]*)\s+AS", sql_upper)
        )

        table_matches = re.finditer(r"\b(FROM|JOIN)\s+([A-Z0-9_\"\.]+)", sql_upper)
        referenced_tables: List[str] = []
        for match in table_matches:
            table_token = match.group(2)
            # Remove quoting and alias suffixes (e.g., COMPANIES C).
            table_primary = table_token.replace('"', "").split()[0]
            table_primary = table_primary.split(".")[-1]
            referenced_tables.append(table_primary)

        unknown_tables = {
            table
            for table in referenced_tables
            if table not in self._ALLOWED_TABLES and table not in cte_names
        }
        if unknown_tables:
            return (
                False,
                f"Unknown tables referenced: {', '.join(sorted(unknown_tables))}",
            )

        if "NUM" in referenced_tables and "SUB" not in referenced_tables:
            return False, "Queries referencing NUM must join through SUB"

        if "COMPANIES_WITH_SECTORS" in sql_upper:
            return False, "Use the COMPANIES view instead of companies_with_sectors"

        if " NUM.CIK" in sql_upper:
            return (
                False,
                "NUM table does not expose CIK; join through SUB for issuer details",
            )

        return True, None

    def validate(
        self,
        sql: str,
        question: str,
        entities: Optional[Dict[str, Any]] = None,
        context: Optional[RequestContext] = None,
    ) -> Tuple[bool, Optional[str], float]:
        """
        Execute static and semantic validation.

        Returns:
            Tuple of (is_valid, failure_reason, confidence)
        """
        entities = entities or {}
        validation_records = []

        if context:
            validation_records = context.metadata.setdefault("sql_validation", [])

        static_success, static_reason = self.validate_static(sql)
        validation_records.append(
            {
                "stage": "static",
                "success": static_success,
                "reason": static_reason,
            }
        )

        if not static_success:
            self.logger.warning(f"Static SQL validation failed: {static_reason}")
            return False, static_reason, 0.0

        if not self.use_llm or not self.azure_client:
            validation_records.append(
                {
                    "stage": "semantic",
                    "success": False,
                    "reason": "Semantic validation skipped (LLM unavailable)",
                    "skipped": True,
                }
            )
            return True, None, 0.0

        request = SQLValidationRequest(
            question=question,
            sql=sql,
            entities=entities,
            schema_markdown=schema_for_prompt(),
            max_tokens=(
                getattr(self.azure_client.config, "max_tokens", None)
                if self.azure_client
                else None
            ),
        )

        verdict = self._semantic_validate(request)

        validation_records.append(
            {
                "stage": "semantic",
                "success": verdict.success and verdict.is_valid,
                "reason": verdict.reason,
                "confidence": verdict.confidence,
                "warnings": verdict.warnings,
            }
        )

        if context and verdict.token_usage:
            llm_calls = context.metadata.setdefault("llm_calls", [])
            llm_calls.append(
                {
                    "stage": "sql_validation",
                    "tokens": verdict.token_usage,
                    "latency_ms": verdict.processing_time_ms,
                    "success": verdict.success and verdict.is_valid,
                }
            )

        if not verdict.success:
            reason = verdict.reason or "Semantic validation failed"
            self.logger.warning(f"Semantic SQL validation error: {reason}")
            return False, reason, verdict.confidence

        if not verdict.is_valid:
            reason = verdict.reason or "Semantic validator rejected the SQL"
            self.logger.info(f"Semantic validator rejected SQL: {reason}")
            return False, reason, verdict.confidence

        return True, None, verdict.confidence

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _semantic_validate(self, request: SQLValidationRequest) -> SQLValidationVerdict:
        """Call Azure OpenAI to perform semantic validation."""
        if not self.azure_client:
            return SQLValidationVerdict(
                success=False,
                is_valid=False,
                reason="Azure client unavailable",
                confidence=0.0,
                processing_time_ms=0,
            )

        try:
            prompt_payload = get_sql_semantic_validation_prompt(
                sql=request.sql,
                question=request.question,
                entities=request.entities,
                schema_markdown=request.schema_markdown,
            )

            verdict = self.azure_client.validate_sql_semantic(
                request,
                prompt_payload["instructions"],
                prompt_payload["input"],
            )

            return verdict
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"Semantic validation exception: {exc}")
            return SQLValidationVerdict(
                success=False,
                is_valid=False,
                reason=str(exc),
                confidence=0.0,
                processing_time_ms=0,
                errors=[str(exc)],
            )


__all__ = ["SQLValidator"]
