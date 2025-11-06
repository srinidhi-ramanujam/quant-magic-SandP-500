"""
Response Formatter - Convert query results to natural language responses.

For Phase 0, handles:
1. Count queries (sector company counts)
2. Lookup queries (CIK, sector)
3. Error responses
"""

from datetime import datetime
import pandas as pd

from src.models import QueryResult, ExtractedEntities, FormattedResponse
from src.telemetry import get_logger, RequestContext, log_component_timing


class ResponseFormatter:
    """Format query results into natural language responses."""

    def __init__(self):
        """Initialize response formatter."""
        self.logger = get_logger()
        self.logger.info("ResponseFormatter initialized")

    def format(
        self,
        query_result: QueryResult,
        entities: ExtractedEntities,
        context: RequestContext,
        debug_mode: bool = False,
    ) -> FormattedResponse:
        """
        Format query result into natural language response.

        Args:
            query_result: Raw query results from database
            entities: Extracted entities
            context: Request context
            debug_mode: Whether to include debug information

        Returns:
            FormattedResponse with natural language answer
        """
        with log_component_timing(context, "response_formatting"):
            return self._format_response(query_result, entities, context, debug_mode)

    def _format_response(
        self,
        query_result: QueryResult,
        entities: ExtractedEntities,
        context: RequestContext,
        debug_mode: bool,
    ) -> FormattedResponse:
        """Internal formatting logic."""

        # Determine response type based on question type
        if entities.question_type == "count":
            answer = self._format_count_response(query_result, entities)
        elif entities.question_type == "lookup":
            answer = self._format_lookup_response(query_result, entities)
        else:
            answer = self._format_generic_response(query_result, entities)

        # Build metadata
        metadata = {
            "request_id": context.request_id,
            "total_time_seconds": round(context.elapsed(), 4),
            "row_count": query_result.row_count,
            "timestamp": datetime.now().isoformat(),
        }
        if context.metadata:
            metadata.update(context.metadata)

        # Build debug info if requested
        debug_info = None
        if debug_mode:
            debug_info = {
                "entities": {
                    "companies": entities.companies,
                    "metrics": entities.metrics,
                    "sectors": entities.sectors,
                    "time_periods": entities.time_periods,
                    "question_type": entities.question_type,
                    "confidence": entities.confidence,
                },
                "sql_executed": query_result.sql_executed,
                "execution_time": query_result.execution_time_seconds,
                "component_timings": context.component_timings,
            }
            if context.metadata:
                debug_info["metadata"] = context.metadata

        response = FormattedResponse(
            answer=answer,
            confidence=entities.confidence,
            sources=["companies_with_sectors.parquet"],
            metadata=metadata,
            success=True,
            debug_info=debug_info,
        )

        self.logger.info(f"Formatted response: {answer[:100]}...")
        return response

    def _format_count_response(
        self, query_result: QueryResult, entities: ExtractedEntities
    ) -> str:
        """Format response for count queries."""
        # Extract count from result
        data = query_result.data

        if isinstance(data, pd.DataFrame):
            if data.empty:
                return "No results found."
            count = int(data.iloc[0].iloc[0])  # First row, first column
        elif isinstance(data, list) and data:
            count = data[0].get("count", 0) if isinstance(data[0], dict) else 0
        else:
            count = 0

        # Build natural language response
        if entities.sectors:
            sector = entities.sectors[0]
            return f"There are {count} companies in the {sector} sector."
        else:
            return f"Count: {count}"

    def _format_lookup_response(
        self, query_result: QueryResult, entities: ExtractedEntities
    ) -> str:
        """Format response for lookup queries."""
        data = query_result.data

        if isinstance(data, pd.DataFrame):
            if data.empty:
                if entities.companies:
                    return f"Could not find information for {entities.companies[0]}."
                return "No results found."

            row = data.iloc[0]

            # Check what was requested
            if "CIK" in entities.metrics or "cik" in query_result.columns:
                company_name = row.get(
                    "name", entities.companies[0] if entities.companies else "Company"
                )
                cik = row.get("cik", "unknown")
                return f"{company_name}'s CIK is {cik}."

            elif "Sector" in entities.metrics or "gics_sector" in query_result.columns:
                company_name = row.get(
                    "name", entities.companies[0] if entities.companies else "Company"
                )
                sector = row.get("gics_sector", "unknown")
                return f"{company_name} is in the {sector} sector."

            else:
                # Generic response - just show the data
                return self._format_generic_response(query_result, entities)

        elif isinstance(data, list) and data:
            row = data[0]

            if "cik" in row:
                company = row.get(
                    "name", entities.companies[0] if entities.companies else "Company"
                )
                cik = row["cik"]
                return f"{company}'s CIK is {cik}."

            elif "gics_sector" in row:
                company = row.get(
                    "name", entities.companies[0] if entities.companies else "Company"
                )
                sector = row["gics_sector"]
                return f"{company} is in the {sector} sector."

        return "Result found but unable to format."

    def _format_generic_response(
        self, query_result: QueryResult, entities: ExtractedEntities
    ) -> str:
        """Format a generic response when specific formatting not available."""
        if query_result.row_count == 0:
            return "No results found."

        # Simple tabular format
        data = query_result.data

        if isinstance(data, pd.DataFrame):
            if query_result.row_count == 1:
                # Single row - format as key: value
                row = data.iloc[0]
                parts = [f"{col}: {row[col]}" for col in data.columns]
                return " | ".join(parts)
            else:
                # Multiple rows - just report count
                return f"Found {query_result.row_count} results."

        return f"Query returned {query_result.row_count} rows."

    def format_error(
        self, error: Exception, context: RequestContext, debug_mode: bool = False
    ) -> FormattedResponse:
        """
        Format an error response.

        Args:
            error: Exception that occurred
            context: Request context
            debug_mode: Whether to include debug information

        Returns:
            FormattedResponse with error message
        """
        error_message = str(error)
        error_type = type(error).__name__

        # User-friendly error message
        if "template" in error_message.lower() or "match" in error_message.lower():
            answer = "I couldn't understand your question. Please try rephrasing it or asking about company sectors, CIKs, or sector counts."
        elif "sql" in error_message.lower() or "database" in error_message.lower():
            answer = "There was an error querying the database. Please try again or rephrase your question."
        else:
            answer = (
                f"An error occurred while processing your question: {error_message}"
            )

        metadata = {
            "request_id": context.request_id,
            "total_time_seconds": round(context.elapsed(), 4),
            "error_type": error_type,
            "timestamp": datetime.now().isoformat(),
        }

        debug_info = None
        if debug_mode:
            debug_info = {
                "error_type": error_type,
                "error_message": error_message,
                "component_timings": context.component_timings,
            }

        return FormattedResponse(
            answer=answer,
            confidence=0.0,
            sources=[],
            metadata=metadata,
            success=False,
            error=error_message,
            debug_info=debug_info,
        )


# Global instance
_formatter: ResponseFormatter = None


def get_response_formatter() -> ResponseFormatter:
    """Get the global response formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = ResponseFormatter()
    return _formatter
