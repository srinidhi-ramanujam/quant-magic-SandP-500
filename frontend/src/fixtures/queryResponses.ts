import type { QueryResponse } from "../types";

export const simpleResponse: QueryResponse = {
  answer: "There are 78 companies in the Technology sector.",
  success: true,
  sql: "SELECT sector, COUNT(*) AS company_count FROM sp500_companies WHERE sector = 'Technology';",
  metadata: {
    request_id: "req-simple-001",
    total_time_seconds: 1.234,
    component_timings: {
      entity_extraction: 0.12,
      sql_generation: 0.32,
      query_execution: 0.51,
    },
    row_count: 1,
  },
  presentation: {
    narrative: "There are 78 S&P 500 companies classified under the Technology sector.",
    highlights: [
      "78 companies are currently labeled as Technology.",
      "Count is based on the latest sector assignments in the dataset.",
    ],
    table: {
      columns: ["sector", "company_count"],
      rows: [{ sector: "Technology", company_count: 78 }],
      truncated: false,
    },
    warnings: [],
  },
  reasoning_trace: {
    template_id: "sector_count",
    generation_method: "template",
    row_count: 1,
    summary: "template `sector_count` · 1 rows",
    warnings: [],
  },
  sql_collapsible_hint: "template `sector_count` · 1 rows",
};

export const timeSeriesResponse: QueryResponse = {
  answer: "Apple’s revenue grew steadily from FY2021 through FY2023.",
  success: true,
  sql: "SELECT fiscal_year, SUM(revenue) AS revenue FROM fundamentals WHERE cik = '0000320193' AND fiscal_year BETWEEN 2021 AND 2023 GROUP BY fiscal_year ORDER BY fiscal_year;",
  metadata: {
    request_id: "req-ts-001",
    total_time_seconds: 2.987,
    component_timings: {
      entity_extraction: 0.18,
      sql_generation: 0.46,
      query_execution: 1.7,
      answer_formatter: 0.45,
    },
    row_count: 3,
  },
  presentation: {
    narrative:
      "Apple’s revenue expanded over FY2021–FY2023, reflecting sustained demand and pricing power.",
    highlights: [
      "FY2021 revenue: $365.8B",
      "FY2022 revenue: $394.3B",
      "FY2023 revenue: $383.3B",
    ],
    table: {
      columns: ["fiscal_year", "revenue"],
      rows: [
        { fiscal_year: 2021, revenue: "$365.8B" },
        { fiscal_year: 2022, revenue: "$394.3B" },
        { fiscal_year: 2023, revenue: "$383.3B" },
      ],
      truncated: false,
    },
    warnings: ["Formatter rounded revenue to billions."],
  },
  reasoning_trace: {
    template_id: "time_series_revenue",
    generation_method: "template",
    row_count: 3,
    summary: "template `time_series_revenue` · 3 rows",
    warnings: [],
  },
  sql_collapsible_hint: "template `time_series_revenue` · 3 rows",
};

export const mediumResponse: QueryResponse = {
  answer: "High-margin software leaders combine double-digit growth with resilient profitability.",
  success: true,
  sql: "SELECT company, revenue_growth, operating_margin FROM metrics WHERE sector = 'Technology' AND revenue > 10000000000 ORDER BY revenue_growth DESC LIMIT 5;",
  metadata: {
    request_id: "req-medium-001",
    total_time_seconds: 4.215,
    component_timings: {
      entity_extraction: 0.25,
      sql_generation: 0.62,
      query_execution: 1.85,
      answer_formatter: 0.98,
    },
    row_count: 5,
  },
  presentation: {
    narrative:
      "Among large Technology names, the top performers pair strong double-digit revenue growth with operating margins above 25%.",
    highlights: [
      "Leaders: Microsoft, Adobe, and ServiceNow combine scale with >25% margins.",
      "Growth tail: Snowflake and CrowdStrike deliver the fastest growth but slightly lower margins.",
    ],
    table: {
      columns: ["company", "revenue_growth", "operating_margin"],
      rows: [
        { company: "Snowflake", revenue_growth: "37%", operating_margin: "16%" },
        { company: "CrowdStrike", revenue_growth: "35%", operating_margin: "12%" },
        { company: "ServiceNow", revenue_growth: "23%", operating_margin: "26%" },
        { company: "Adobe", revenue_growth: "11%", operating_margin: "34%" },
        { company: "Microsoft", revenue_growth: "10%", operating_margin: "42%" },
      ],
      truncated: true,
    },
    warnings: [
      "Table truncated to top 5 rows.",
      "Margins rounded to nearest percentage point.",
    ],
  },
  reasoning_trace: {
    template_id: "growth_profitability_quadrant",
    generation_method: "template",
    row_count: 5,
    summary: "template `growth_profitability_quadrant` · 5 rows",
    warnings: ["Rows limited to top 5 by growth"],
  },
  sql_collapsible_hint: "template `growth_profitability_quadrant` · 5 rows",
};

export const sampleResponses = {
  simple: simpleResponse,
  timeSeries: timeSeriesResponse,
  medium: mediumResponse,
};
