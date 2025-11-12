WITH provided_companies AS (
    SELECT *
    FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT
        c.cik,
        pc.company_name AS requested_name,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name,
        c.name AS dataset_name
    FROM companies c
    JOIN provided_companies pc
      ON UPPER(c.name) = UPPER(pc.company_name)
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (
            PARTITION BY s.cik, s.fy
            ORDER BY s.filed DESC
        ) AS filing_rank
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-K', '10-K/A', '20-F')
      AND CAST(s.fy AS INTEGER) BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT *
    FROM annual_filings
    WHERE filing_rank = 1
),
annual_metrics AS (
    SELECT
        cd.requested_name AS company,
        cd.canonical_name,
        CAST(l.fiscal_year AS INTEGER) AS fiscal_year,
        COALESCE(
            MAX(
                CASE
                    WHEN n.tag = 'NetIncomeLoss'
                    THEN n.value
                END
            ),
            MAX(
                CASE
                    WHEN n.tag = 'ProfitLoss'
                    THEN n.value
                END
            ),
            MAX(
                CASE
                    WHEN n.tag = 'NetIncomeLossAvailableToCommonStockholdersBasic'
                    THEN n.value
                END
            )
        ) AS net_income,
        COALESCE(
            MAX(
                CASE
                    WHEN n.tag = 'StockholdersEquity'
                    THEN n.value
                END
            ),
            MAX(
                CASE
                    WHEN n.tag = 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                    THEN n.value
                END
            )
        ) AS equity
    FROM latest_filings l
    JOIN num n ON n.adsh = l.adsh
    JOIN company_dim cd USING (cik)
    WHERE n.tag IN (
        'NetIncomeLoss',
        'ProfitLoss',
        'NetIncomeLossAvailableToCommonStockholdersBasic',
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
      AND COALESCE(n.qtrs, 0) IN (0, 4)
      AND (
          n.ddate IS NULL
          OR EXTRACT(YEAR FROM n.ddate) = CAST(l.fiscal_year AS INTEGER)
      )
    GROUP BY
        cd.requested_name,
        cd.canonical_name,
        l.cik,
        l.fiscal_year
),
coverage AS (
    SELECT
        canonical_name,
        COUNT(DISTINCT fiscal_year) AS year_count
    FROM annual_metrics
    GROUP BY canonical_name
    HAVING COUNT(DISTINCT fiscal_year) >= {min_years}
),
final_series AS (
    SELECT
        am.company,
        am.fiscal_year,
        ROUND(am.net_income / 1e6, 2) AS net_income_millions,
        ROUND(am.equity / 1e6, 2) AS equity_millions,
        ROUND(
            100 * am.net_income
            / NULLIF(am.equity, 0),
            2
        ) AS roe_pct
    FROM annual_metrics am
    JOIN coverage c USING (canonical_name)
    WHERE am.net_income IS NOT NULL
      AND am.equity IS NOT NULL
      AND am.fiscal_year BETWEEN {start_year} AND {end_year}
      AND ABS(
          100 * am.net_income
          / NULLIF(am.equity, 0)
      ) <= {max_abs_roe}
)
SELECT
    company,
    fiscal_year,
    net_income_millions,
    equity_millions,
    roe_pct
FROM final_series
ORDER BY company, fiscal_year
LIMIT {result_limit};
