"""
Response Formatter - Convert query results to natural language responses.

For Phase 0, handles:
1. Count queries (sector company counts)
2. Lookup queries (CIK, sector)
3. Error responses
"""

from datetime import datetime
from typing import Any, Callable, Dict, Optional
import math
import re

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
            "gross_margin_trend_sector": self._format_gross_margin_trend_sector,
            "inventory_turnover_trend": self._format_inventory_turnover_trend,
            "roe_revenue_divergence": self._format_roe_revenue_divergence,
            "working_capital_cash_cycle_trend": (
                self._format_working_capital_cash_cycle_trend
            ),
            "net_debt_to_ebitda_trend": self._format_net_debt_to_ebitda_trend,
            "asset_turnover_trend": self._format_asset_turnover_trend,
            "cfo_to_net_income_trend": self._format_cfo_to_net_income_trend,
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
        data = self._as_dataframe(query_result.data)
        if data is None or data.empty:
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
        data = self._as_dataframe(query_result.data)
        if data is None or data.empty:
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

    def _format_gross_margin_trend_sector(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No gross margin movements were detected for the requested cohort."
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        rows = data.head(6)
        bullets = []
        for idx, row in rows.iterrows():
            name = row.get("name", "Unknown company")
            margin_cols = sorted(
                [
                    col
                    for col in row.index
                    if col.startswith("margin_") and col.endswith("_pct")
                ]
            )
            if len(margin_cols) < 2:
                continue
            start_label, end_label = margin_cols[0], margin_cols[-1]
            start_year = start_label.split("_")[1]
            end_year = end_label.split("_")[1]
            start_margin = self._format_percentage(row[start_label], signed=False)
            end_margin = self._format_percentage(row[end_label], signed=False)
            change_raw = self._get_first_value(row, ["change_pp"])
            change_str = self._format_percentage(change_raw, signed=True)
            resilience = self._describe_margin_resilience(change_raw)

            revenue_cols = sorted(
                [
                    col
                    for col in row.index
                    if col.startswith("revenue_") and col.endswith("_billions")
                ]
            )
            revenue_val = (
                self._get_first_value(row, [revenue_cols[-1]]) if revenue_cols else None
            )
            revenue_str = self._format_billions(revenue_val) if revenue_val else "n/a"

            bullets.append(
                f"{len(bullets)+1}) {name}: {start_margin} ({start_year}) → {end_margin} ({end_year}) {change_str} — {resilience} on FY{end_year} revenue of {revenue_str}."
            )

        return "Sector gross margin shifts:\n" + "\n".join(bullets)

    def _format_inventory_turnover_trend(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return (
                "No inventory turnover data was available for the requested companies."
            )
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        bullets = []
        for idx, (_, row) in enumerate(data.iterrows(), start=1):
            company = row.get("company", "Company")
            latest_period = self._format_period_label(row.get("latest_period_end"))
            baseline_period = self._format_period_label(
                row.get("baseline_period_end") or row.get("baseline_period")
            )
            latest_turnover = self._format_ratio(row.get("latest_turnover"))
            baseline_turnover = self._format_ratio(
                row.get("baseline_turnover") or row.get("start_turnover")
            )
            turnover_change = self._format_ratio(
                self._clean_numeric(row.get("turnover_change")), signed=True
            )
            dio_change = self._format_days(
                self._clean_numeric(row.get("dio_change")), signed=True
            )
            latest_dio = self._format_days(row.get("latest_dio"))
            baseline_dio = self._format_days(
                row.get("baseline_dio") or row.get("start_dio")
            )

            bullets.append(
                f"{idx}) {company}: {baseline_turnover} ({baseline_period}) → "
                f"{latest_turnover} ({latest_period}) {turnover_change}; "
                f"DIO {baseline_dio} → {latest_dio} ({dio_change})"
            )

        return "Inventory turnover trend (last 6 quarters):\n" + "\n".join(bullets)

    def _format_net_debt_to_ebitda_trend(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No leverage data was available for the requested airlines."

        data = query_result.data
        if isinstance(data, list):
            data = pd.DataFrame(data)
        if not isinstance(data, pd.DataFrame):
            return None
        if data.empty:
            return "No leverage data was available for the requested airlines."

        def _ratio_label(value: Any) -> str:
            cleaned = self._clean_numeric(value)
            return "NM" if cleaned is None else self._format_ratio(cleaned)

        bullets: list[str] = []
        df = data.sort_values(["company", "fiscal_year"])
        for idx, (company, group) in enumerate(df.groupby("company", dropna=False), 1):
            if group.empty:
                continue

            group = group.sort_values("fiscal_year")
            start_year = int(group["fiscal_year"].min())
            end_year = int(group["fiscal_year"].max())

            start_ratio = _ratio_label(
                group.loc[
                    group["fiscal_year"] == start_year, "net_debt_to_ebitda"
                ].iloc[0]
            )
            end_ratio = _ratio_label(
                group.loc[group["fiscal_year"] == end_year, "net_debt_to_ebitda"].iloc[
                    0
                ]
            )

            valid = group.dropna(subset=["net_debt_to_ebitda"])
            if valid.empty:
                peak_text = "leverage undefined (EBITDA <= 0 each year)"
            else:
                peak_row = valid.loc[valid["net_debt_to_ebitda"].idxmax()]
                peak_value = self._clean_numeric(peak_row["net_debt_to_ebitda"])
                peak_year = int(peak_row["fiscal_year"])
                peak_text = (
                    "remained in net cash territory"
                    if peak_value is not None and peak_value <= 0
                    else f"peak {self._format_ratio(peak_value)} in {peak_year}"
                )

            latest_row = group.loc[group["fiscal_year"] == end_year].iloc[-1]
            net_debt = self._format_billions(
                self._clean_numeric(latest_row.get("net_debt_billions"))
            )
            ebitda = self._format_billions(
                self._clean_numeric(latest_row.get("ebitda_billions"))
            )

            bullets.append(
                f"{idx}) {company}: {start_ratio} ({start_year}) → {end_ratio} ({end_year}); "
                f"{peak_text}. FY{end_year} net debt {net_debt}, EBITDA {ebitda}."
            )

        return "Airline net debt-to-EBITDA progression (FY2019-FY2023):\n" + "\n".join(
            bullets
        )

    def _format_asset_turnover_trend(self, query_result: QueryResult) -> Optional[str]:
        if query_result.row_count == 0:
            return "No asset-turnover coverage was found for the requested companies."

        data = query_result.data
        if isinstance(data, list):
            data = pd.DataFrame(data)
        if not isinstance(data, pd.DataFrame) or data.empty:
            return None

        turnover_cols = sorted(
            [
                col
                for col in data.columns
                if re.match(r"turnover_(\d{4})$", col, re.IGNORECASE)
            ],
            key=lambda c: int(re.findall(r"(\d{4})", c)[0]),
        )
        if not turnover_cols:
            return None

        start_year = re.findall(r"(\d{4})", turnover_cols[0])[0]
        end_year = re.findall(r"(\d{4})", turnover_cols[-1])[0]

        rows = data.head(6)
        bullets: list[str] = []
        for idx, (_, row) in enumerate(rows.iterrows(), start=1):
            name = row.get("name", "Company")
            change_raw = self._clean_numeric(row.get("change_since_start"))
            change_str = self._format_ratio(change_raw, signed=True)
            trend_word = "improved" if change_raw and change_raw > 0 else "declined"
            start_val = row.get(f"turnover_{start_year}") or row.get("turnover_start")
            end_val = row.get(f"turnover_{end_year}") or row.get("turnover_end")
            start_label = self._format_ratio(self._clean_numeric(start_val))
            end_label = self._format_ratio(self._clean_numeric(end_val))
            coverage = int(row.get("years_available", 0) or 0)

            bullets.append(
                f"{idx}) {name}: {start_label} ({start_year}) → {end_label} ({end_year}) "
                f"{change_str} ({trend_word}); coverage {coverage} yrs."
            )

        heading = f"Technology hardware asset-turnover trend ({start_year}-{end_year}):"
        return heading + "\n" + "\n".join(bullets)

    def _format_cfo_to_net_income_trend(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No CFO-to-net income coverage was found for the requested cohort."

        data = query_result.data
        if isinstance(data, list):
            data = pd.DataFrame(data)
        if not isinstance(data, pd.DataFrame) or data.empty:
            return None

        ratio_cols = sorted(
            [
                col
                for col in data.columns
                if col.startswith("ratio_") and col.split("_")[-1].isdigit()
            ],
            key=lambda c: int(c.split("_")[-1]),
        )
        if not ratio_cols:
            return None

        start_year = ratio_cols[0].split("_")[-1]
        end_year = ratio_cols[-1].split("_")[-1]

        bullets: list[str] = []
        for idx, (_, row) in enumerate(data.head(6).iterrows(), start=1):
            name = row.get("name", "Company")
            start_ratio = self._format_ratio(
                self._clean_numeric(row.get(f"ratio_{start_year}"))
            )
            end_ratio = self._format_ratio(
                self._clean_numeric(row.get(f"ratio_{end_year}"))
            )
            avg_ratio = self._format_ratio(self._clean_numeric(row.get("avg_ratio")))
            change = self._format_ratio(
                self._clean_numeric(row.get("change_since_start")), signed=True
            )
            coverage = int(self._clean_numeric(row.get("years_available")) or 0)
            bullets.append(
                f"{idx}) {name}: {start_ratio} ({start_year}) → {end_ratio} ({end_year}) {change}; "
                f"avg {avg_ratio} CFO/NI over {coverage} yrs."
            )

        heading = f"Healthcare CFO-to-net income trend ({start_year}-{end_year}):"
        return heading + "\n" + "\n".join(bullets)

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

    def _format_working_capital_cash_cycle_trend(
        self, query_result: QueryResult
    ) -> Optional[str]:
        if query_result.row_count == 0:
            return "No working-capital improvements found for the requested period."
        data = query_result.data
        if not isinstance(data, pd.DataFrame):
            return None

        wc_cols = sorted(
            [
                col
                for col in data.columns
                if col.startswith("wc_")
                and col.endswith("_days")
                and col.split("_")[1].isdigit()
            ]
        )
        if len(wc_cols) < 2:
            return None
        start_col, end_col = wc_cols[0], wc_cols[-1]
        start_year = start_col.split("_")[1]
        end_year = end_col.split("_")[1]

        ccc_cols = sorted(
            [
                col
                for col in data.columns
                if col.startswith("ccc_")
                and col.endswith("_days")
                and col.split("_")[1].isdigit()
            ]
        )

        bullets = []
        for idx, (_, row) in enumerate(data.head(5).iterrows(), start=1):
            name = row.get("name", "Unknown company")
            start_wc = self._format_days(self._clean_numeric(row.get(start_col)))
            end_wc = self._format_days(self._clean_numeric(row.get(end_col)))
            change_wc = self._format_days(
                self._clean_numeric(row.get("wc_change_days")), signed=True
            )

            ccc_summary = ""
            if len(ccc_cols) >= 2:
                ccc_start_col, ccc_end_col = ccc_cols[0], ccc_cols[-1]
                ccc_start = self._clean_numeric(row.get(ccc_start_col))
                ccc_end = self._clean_numeric(row.get(ccc_end_col))
                ccc_change = self._clean_numeric(row.get("ccc_change_days"))
                if ccc_start is not None and ccc_end is not None:
                    ccc_summary = (
                        f" | CCC {self._format_days(ccc_start)} ({ccc_start_col.split('_')[1]}) → "
                        f"{self._format_days(ccc_end)} ({ccc_end_col.split('_')[1]}) "
                        f"{self._format_days(ccc_change, signed=True)}"
                    )

            bullets.append(
                f"{idx}) {name}: working capital days {start_wc} ({start_year}) → "
                f"{end_wc} ({end_year}) {change_wc}{ccc_summary or ' | CCC data n/a'}"
            )

        return "Working capital leaders (days):\n" + "\n".join(bullets)

    @staticmethod
    def _as_dataframe(data):
        if isinstance(data, pd.DataFrame):
            return data
        if isinstance(data, list):
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data)
        return None

    @staticmethod
    def _get_first_value(row, keys) -> Optional[float]:
        for key in keys:
            if key in row and row[key] is not None:
                return row[key]
        return None

    @staticmethod
    def _describe_margin_resilience(change: Optional[float]) -> str:
        if change is None:
            return "mixed pricing power"
        if change >= 1.0:
            return "pricing power strengthened"
        if change >= 0.2:
            return "margins held steady"
        if change <= -2:
            return "material compression"
        if change <= -0.5:
            return "moderate pressure"
        return "slight pullback"

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

    @staticmethod
    def _format_days(value, signed: bool = False) -> str:
        if value is None:
            return "n/a"
        return f"{value:+.2f} days" if signed else f"{value:.2f} days"

    @staticmethod
    def _format_period_label(value) -> str:
        if value is None:
            return "Unknown period"
        try:
            import pandas as pd

            ts = pd.to_datetime(value)
            return ts.strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            return str(value)

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

    @staticmethod
    def _clean_numeric(value):
        if value is None:
            return None
        try:
            import math

            if isinstance(value, float) and math.isnan(value):
                return None
        except (ValueError, TypeError):
            return value
        return value

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
