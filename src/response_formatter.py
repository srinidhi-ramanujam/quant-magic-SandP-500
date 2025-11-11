"""
Response Formatter - Convert query results to natural language responses.

For Phase 0, handles:
1. Count queries (sector company counts)
2. Lookup queries (CIK, sector)
3. Error responses
"""

from datetime import datetime
from typing import Callable, Dict, Optional

import pandas as pd

from src.models import QueryResult, ExtractedEntities, FormattedResponse
from src.telemetry import get_logger, RequestContext, log_component_timing


class ResponseFormatter:
    """Format query results into natural language responses."""

    def __init__(self):
        """Initialize response formatter."""
        self.logger = get_logger()
        self.logger.info("ResponseFormatter initialized")
        self.template_formatters: Dict[str, Callable[[QueryResult], Optional[str]]] = {
            "debt_reduction_progression": self._format_debt_reduction_progression,
            "profit_margin_consistency_trend": (
                self._format_profit_margin_consistency_trend
            ),
            "current_ratio_trend": self._format_current_ratio_trend,
            "operating_margin_delta": self._format_operating_margin_delta,
            "roe_revenue_divergence": self._format_roe_revenue_divergence,
        }

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

        template_id = (
            context.metadata.get("template_id")
            if context and context.metadata
            else None
        )

        specialized_answer = self._format_template_specific(template_id, query_result)

        if specialized_answer:
            answer = specialized_answer
        else:
            # Determine response type based on question type
            if entities.question_type == "count":
                answer = self._format_count_response(query_result, entities)
            elif entities.question_type == "lookup":
                answer = self._format_lookup_response(query_result, entities)
            else:
                answer = self._format_generic_response(query_result, entities, context)

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

            row = data.iloc[0]
            numeric_columns = [
                col for col in row.index if pd.api.types.is_numeric_dtype(data[col])
            ]

            if numeric_columns:
                count_value = row[numeric_columns[0]]
            else:
                count_value = row.iloc[0]

            try:
                count = int(count_value)
            except (ValueError, TypeError):
                try:
                    count = int(float(count_value))
                except (ValueError, TypeError):
                    count = 0

            # Include category/label context when available
            label_value = None
            for label_col in row.index:
                if label_col not in numeric_columns:
                    label_candidate = row[label_col]
                    if isinstance(label_candidate, str) and label_candidate.strip():
                        label_value = label_candidate.strip()
                        break
        elif isinstance(data, list) and data:
            count = data[0].get("count", 0) if isinstance(data[0], dict) else 0
        else:
            count = 0

        # Build natural language response
        if entities.sectors:
            sector = entities.sectors[0]
            return f"There are {count} companies in the {sector} sector."
        if label_value:
            return f"{label_value} has {count} matching records."
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

    def _format_template_specific(
        self, template_id: Optional[str], query_result: QueryResult
    ) -> Optional[str]:
        """Format known template responses."""
        if not template_id:
            return None
        formatter = self.template_formatters.get(template_id)
        if formatter:
            return formatter(query_result)
        return None

    def _format_debt_reduction_progression(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No debt reductions found for the requested period."
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        rows = data.head(5)
        bullets = []
        for idx, row in rows.iterrows():
            name = row.get("name", "Unknown company")
            sector = row.get("gics_sector", "Unknown sector")
            start_debt = self._format_billions(
                self._get_first_value(row, ["debt_2021_billions", "debt_2021"])
            )
            end_debt = self._format_billions(
                self._get_first_value(row, ["debt_2023_billions", "debt_2023"])
            )
            delta = self._format_billions(
                -abs(
                    self._get_first_value(
                        row, ["debt_reduction_billions", "debt_reduction"]
                    )
                    or 0
                ),
                signed=True,
            )
            bullets.append(
                f"{len(bullets)+1}) {name} ({sector}) cut debt from {start_debt} to {end_debt} ({delta})."
            )

        return "Top FY2021-FY2023 deleveragers:\n" + "\n".join(bullets)

    def _format_profit_margin_consistency_trend(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No profitability improvements were found for the requested period."
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        rows = data.head(5)
        bullets = []
        for idx, row in rows.iterrows():
            name = row.get("name", "Unknown company")
            start_margin = self._format_percentage(
                self._get_first_value(row, ["margin_2019_pct"]), signed=False
            )
            end_margin = self._format_percentage(
                self._get_first_value(row, ["margin_2023_pct"]), signed=False
            )
            improvement = self._format_percentage(
                self._get_first_value(row, ["improvement_pct"]), signed=True
            )
            consistency = row.get("consistency_steps", "0")
            bullets.append(
                f"{len(bullets)+1}) {name}: {start_margin} (2019) → {end_margin} (2023) {improvement} | Consistency steps: {consistency}"
            )

        return "Top Technology profit margin improvers (FY2019-FY2023):\n" + "\n".join(
            bullets
        )

    def _format_current_ratio_trend(self, query_result: QueryResult) -> Optional[str]:
        if query_result.row_count == 0:
            return "No companies met the five-year current-ratio coverage requirement."
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        rows = data.head(5)
        bullets = []
        for idx, row in rows.iterrows():
            name = row.get("name", "Unknown company")
            ratio_2019 = self._format_ratio(self._get_first_value(row, ["ratio_2019"]))
            ratio_2023 = self._format_ratio(self._get_first_value(row, ["ratio_2023"]))
            improvement = self._format_ratio(
                self._get_first_value(row, ["improvement"]), signed=True
            )
            bullets.append(
                f"{len(bullets)+1}) {name}: {ratio_2019} (2019) → {ratio_2023} (2023) {improvement}"
            )

        return "Top Healthcare liquidity improvers (FY2019-FY2023):\n" + "\n".join(
            bullets
        )

    def _format_operating_margin_delta(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No operating margin improvements found for the requested period."
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        rows = data.head(5)
        bullets = []
        for idx, row in rows.iterrows():
            name = row.get("name", "Unknown company")
            cols = sorted(
                [
                    col
                    for col in row.index
                    if col.startswith("margin_") and col.endswith("_pct")
                ]
            )
            if len(cols) < 2:
                continue
            start_label, end_label = cols[0], cols[-1]
            start_year = start_label.split("_")[1]
            end_year = end_label.split("_")[1]
            start_margin = self._format_percentage(row[start_label], signed=False)
            end_margin = self._format_percentage(row[end_label], signed=False)
            improvement = self._format_percentage(
                self._get_first_value(row, ["improvement_pp"]), signed=True
            )
            revenue = self._get_first_value(
                row, [f"revenue_{end_year}_billions", "revenue_end"]
            )
            revenue_str = (
                f"${revenue:,.2f}B" if revenue is not None else "revenue data n/a"
            )
            bullets.append(
                f"{len(bullets)+1}) {name}: {start_margin} ({start_year}) → {end_margin} ({end_year}) {improvement} on {revenue_str}."
            )

        return "Largest FY operating margin rebounds:\n" + "\n".join(bullets)

    def _format_roe_revenue_divergence(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No ROE declines were detected with revenue growth over the requested window."
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        rows = data.head(5)
        bullets = []
        for idx, row in rows.iterrows():
            name = row.get("name", "Unknown company")
            cols = sorted(
                [
                    col
                    for col in row.index
                    if col.startswith("roe_") and col.endswith("_pct")
                ]
            )
            if len(cols) < 2:
                continue
            start_label, end_label = cols[0], cols[-1]
            start_year = start_label.split("_")[1]
            end_year = end_label.split("_")[1]
            start_roe = self._format_percentage(row[start_label], signed=False)
            end_roe = self._format_percentage(row[end_label], signed=False)
            change = self._format_percentage(
                self._get_first_value(row, ["roe_change_pp"]), signed=True
            )
            revenue_growth = self._format_percentage(
                self._get_first_value(row, ["revenue_growth_pct"]), signed=True
            )
            bullets.append(
                f"{len(bullets)+1}) {name}: ROE {start_roe} ({start_year}) → {end_roe} ({end_year}) {change} while revenue grew {revenue_growth}."
            )

        return "ROE compression despite revenue growth:\n" + "\n".join(bullets)

    @staticmethod
    def _get_first_value(row, keys) -> Optional[float]:
        for key in keys:
            if key in row and row[key] is not None:
                return row[key]
        return None

    @staticmethod
    def _format_millions(value, signed: bool = False) -> str:
        if value is None:
            return "n/a"
        if signed:
            return f"{value:+,.0f}M"
        return f"${value:,.0f}M"

    @staticmethod
    def _format_billions(value, signed: bool = False) -> str:
        if value is None:
            return "n/a"
        if signed:
            return f"{value:+.2f}B"
        return f"${value:.2f}B"

    @staticmethod
    def _format_percentage(value, signed: bool = False) -> str:
        if value is None:
            return "n/a"
        if signed:
            return f"{value:+.2f}%"
        return f"{value:.2f}%"

    @staticmethod
    def _format_ratio(value, signed: bool = False) -> str:
        if value is None:
            return "n/a"
        if signed:
            return f"{value:+.2f}x"
        return f"{value:.2f}x"

    def _format_generic_response(
        self,
        query_result: QueryResult,
        entities: ExtractedEntities,
        context: RequestContext | None = None,
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
                # Multiple rows - show count and first few entries
                preview = data.head(5)
                summary = preview.to_dict(orient="records")
                return f"Found {query_result.row_count} results. Sample: {summary}"

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
