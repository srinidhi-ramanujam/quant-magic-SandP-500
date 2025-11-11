"""Reusable service layer that runs the Quant Magic query pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.answer_formatter import AnswerFormatter
from src.config import Config, get_config
from src.entity_extractor import EntityExtractor
from src.models import (
    ConversationTurn,
    ExtractedEntities,
    FormattedResponse,
    GeneratedSQL,
    PresentationPayload,
    ReasoningTrace,
    QueryResult,
)
from src.query_engine import QueryEngine
from src.response_formatter import get_response_formatter
from src.sql_generator import SQLGenerator
from src.telemetry import (
    RequestContext,
    create_request_context,
    generate_telemetry_report,
    get_logger,
    log_component_timing,
    log_error,
    setup_logging,
)
from src.llm_guard import LLMAvailabilityError


@dataclass
class QueryServiceResult:
    """Result returned by the query service."""

    response: FormattedResponse
    context: RequestContext
    entities: Optional[ExtractedEntities]
    generated_sql: Optional[GeneratedSQL]
    query_result: Optional[QueryResult]
    success: bool
    error: Optional[str] = None


class QueryService:
    """High-level orchestrator for processing natural language questions."""

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        entity_extractor: Optional[EntityExtractor] = None,
        sql_generator: Optional[SQLGenerator] = None,
        query_engine: Optional[QueryEngine] = None,
        use_llm: bool = True,
    ) -> None:
        """Initialise the service and its dependencies."""

        setup_logging()
        self.logger = get_logger()

        self.config = config or get_config()
        self.use_llm = use_llm
        self.entity_extractor = entity_extractor or EntityExtractor(
            config=self.config, use_llm=use_llm
        )
        self.sql_generator = sql_generator or SQLGenerator(use_llm=use_llm)
        self.response_formatter = get_response_formatter()
        self.answer_formatter = AnswerFormatter(config=self.config) if use_llm else None

        if query_engine:
            self.query_engine = query_engine
            self._owns_query_engine = False
        else:
            self.query_engine = QueryEngine()
            self._owns_query_engine = True

        if not self.entity_extractor.use_llm:
            self.logger.warning(
                "LLM entity extraction disabled; operating in deterministic mode"
            )
        if not self.sql_generator.use_llm:
            self.logger.warning(
                "LLM template selection disabled; operating in deterministic mode"
            )

        self.logger.info("QueryService initialised successfully")

    def run(
        self,
        question: str,
        *,
        debug_mode: bool = False,
        context: Optional[RequestContext] = None,
        history: Optional[List[ConversationTurn]] = None,
        include_presentation: bool = True,
    ) -> QueryServiceResult:
        """Process a natural language question end-to-end."""

        context = context or create_request_context(question)
        history = history or []
        entities: Optional[ExtractedEntities] = None
        generated_sql: Optional[GeneratedSQL] = None
        query_result: Optional[QueryResult] = None

        try:
            entities = self.entity_extractor.extract(question, context)
            self.logger.info(
                "[%s] Extracted entities: companies=%s sectors=%s metrics=%s",
                context.request_id,
                entities.companies,
                entities.sectors,
                entities.metrics,
            )

            generated_sql = self.sql_generator.generate(entities, question, context)
            if not generated_sql:
                raise ValueError("Could not generate SQL query for the question")

            self.logger.info(
                "[%s] Generated SQL: %s...",
                context.request_id,
                generated_sql.sql[:200],
            )

            context.add_metadata("template_id", generated_sql.template_id)
            context.add_metadata("generation_method", generated_sql.generation_method)
            context.add_metadata("generated_sql", generated_sql.sql)

            with log_component_timing(context, "query_execution"):
                result_df = self.query_engine.execute(generated_sql.sql)
                query_result = QueryResult(
                    data=result_df,
                    row_count=len(result_df),
                    columns=list(result_df.columns),
                    execution_time_seconds=context.component_timings.get(
                        "query_execution", 0.0
                    ),
                    sql_executed=generated_sql.sql,
                )

            response = self.response_formatter.format(
                query_result, entities, context, debug_mode=debug_mode
            )

            response.reasoning_trace = self._build_reasoning_trace(
                generated_sql, query_result, context
            )

            if include_presentation and self.answer_formatter:
                presentation = self._invoke_answer_formatter(
                    question=question,
                    base_response=response,
                    entities=entities,
                    query_result=query_result,
                    template_id=generated_sql.template_id,
                    context=context,
                    history=history,
                )
                if presentation:
                    response.presentation = presentation
            elif not include_presentation:
                context.add_metadata("formatter_skipped", True)

            generate_telemetry_report(context, success=True)
            return QueryServiceResult(
                response=response,
                context=context,
                entities=entities,
                generated_sql=generated_sql,
                query_result=query_result,
                success=True,
            )

        except LLMAvailabilityError as error:
            log_error(context, error)
            generate_telemetry_report(context, success=False, error=str(error))
            raise
        except Exception as error:  # pragma: no cover - exercised via tests
            log_error(context, error)
            formatted_error = self.response_formatter.format_error(
                error, context, debug_mode=debug_mode
            )
            generate_telemetry_report(context, success=False, error=str(error))
            return QueryServiceResult(
                response=formatted_error,
                context=context,
                entities=entities,
                generated_sql=generated_sql,
                query_result=query_result,
                success=False,
                error=str(error),
            )

    def close(self) -> None:
        """Close underlying resources."""
        if self._owns_query_engine and self.query_engine:
            self.query_engine.close()
            self.logger.info("QueryService closed query engine connection")

    def _invoke_answer_formatter(
        self,
        *,
        question: str,
        base_response: FormattedResponse,
        entities: Optional[ExtractedEntities],
        query_result: Optional[QueryResult],
        template_id: Optional[str],
        context: RequestContext,
        history: List[ConversationTurn],
    ) -> Optional[PresentationPayload]:
        if not self.answer_formatter or not self.answer_formatter.is_available():
            return None

        try:
            with log_component_timing(context, "answer_formatter"):
                outcome = self.answer_formatter.format_answer(
                    question=question,
                    base_answer=base_response.answer,
                    query_result=query_result,
                    entities=entities,
                    template_id=template_id,
                    context=context,
                    history=history,
                )
        except Exception as exc:  # noqa: BLE001 - defensive guard
            self.logger.warning("Answer formatter crashed: %s", exc)
            context.add_metadata("formatter_error", str(exc))
            return None

        if outcome.latency_ms is not None:
            context.add_metadata("formatter_latency_ms", outcome.latency_ms)
        if outcome.token_usage:
            context.add_metadata("formatter_token_usage", outcome.token_usage)
        if outcome.prompt_preview:
            context.add_metadata("formatter_prompt", outcome.prompt_preview[:1000])
        if outcome.raw_response:
            context.add_metadata("formatter_raw", outcome.raw_response[:1000])
        if outcome.error:
            context.add_metadata("formatter_error", outcome.error)
        if outcome.warnings:
            context.add_metadata("formatter_warnings", outcome.warnings)

        return outcome.presentation

    def _build_reasoning_trace(
        self,
        generated_sql: Optional[GeneratedSQL],
        query_result: Optional[QueryResult],
        context: RequestContext,
    ) -> Optional[ReasoningTrace]:
        if not generated_sql:
            return None

        summary_parts = []
        if generated_sql.template_id:
            summary_parts.append(f"template `{generated_sql.template_id}`")
        if generated_sql.generation_method:
            summary_parts.append(generated_sql.generation_method)
        if query_result:
            summary_parts.append(f"{query_result.row_count} rows")

        warnings: List[str] = []
        formatter_warnings = context.metadata.get("formatter_warnings")
        if isinstance(formatter_warnings, list):
            warnings.extend(str(item) for item in formatter_warnings)
        elif isinstance(formatter_warnings, str):
            warnings.append(formatter_warnings)

        return ReasoningTrace(
            template_id=generated_sql.template_id,
            generation_method=generated_sql.generation_method,
            row_count=query_result.row_count if query_result else None,
            elapsed_seconds=context.elapsed(),
            summary=" · ".join(summary_parts) if summary_parts else None,
            warnings=warnings,
        )
