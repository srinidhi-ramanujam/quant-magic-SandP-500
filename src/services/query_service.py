"""Reusable service layer that runs the Quant Magic query pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.config import Config, get_config
from src.entity_extractor import EntityExtractor
from src.models import (
    ExtractedEntities,
    FormattedResponse,
    GeneratedSQL,
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
    ) -> None:
        """Initialise the service and its dependencies."""

        setup_logging()
        self.logger = get_logger()

        self.config = config or get_config()
        self.entity_extractor = entity_extractor or EntityExtractor(config=self.config)
        self.sql_generator = sql_generator or SQLGenerator()
        self.response_formatter = get_response_formatter()

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
    ) -> QueryServiceResult:
        """Process a natural language question end-to-end."""

        context = context or create_request_context(question)
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

            generate_telemetry_report(context, success=True)
            return QueryServiceResult(
                response=response,
                context=context,
                entities=entities,
                generated_sql=generated_sql,
                query_result=query_result,
                success=True,
            )

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
