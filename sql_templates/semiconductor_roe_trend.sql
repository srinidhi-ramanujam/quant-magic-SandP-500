WITH provided_companies AS (
    -- Optional explicit cohort
    SELECT * FROM (VALUES {company_values}) AS t(company_name)
),
sector_companies AS (
    -- Sector fallback when no explicit list is supplied or when broadening beyond semiconductors
    SELECT
        c.cik,
        c.name AS company_name,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies c
    WHERE {use_sector_filter} = 1
      AND (UPPER('{sector}') = 'ALL' OR LOWER(c.gics_sector) LIKE LOWER('%{sector}%'))
),
cohort AS (
    SELECT DISTINCT
        c.cik,
        COALESCE(pc.company_name, c.company_name) AS company_name,
        COALESCE(pc.company_name, c.company_name) AS requested_name,
        COALESCE(
            REGEXP_REPLACE(UPPER(TRIM(pc.company_name)), '[^A-Z0-9]', '', 'g'),
            c.canonical_name
        ) AS canonical_name
    FROM sector_companies c
    FULL OUTER JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.company_name)), '[^A-Z0-9]', '', 'g') =
         REGEXP_REPLACE(UPPER(TRIM(pc.company_name)), '[^A-Z0-9]', '', 'g')
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
    JOIN cohort c USING (cik)
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
        c.requested_name AS company,
        c.canonical_name,
        CAST(l.fiscal_year AS INTEGER) AS fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'NetIncomeLoss',
                    'NetIncomeLossAvailableToCommonStockholdersBasic',
                    'NetIncomeLossAvailableToCommonStockholdersDiluted',
                    'ProfitLoss'
                )
                THEN n.value
            END
        ) AS net_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                )
                THEN n.value
            END
        ) AS equity
    FROM latest_filings l
    JOIN num n ON n.adsh = l.adsh AND n.ddate = l.period
    JOIN cohort c USING (cik)
    WHERE n.tag IN (
        'NetIncomeLoss',
        'NetIncomeLossAvailableToCommonStockholdersBasic',
        'NetIncomeLossAvailableToCommonStockholdersDiluted',
        'ProfitLoss',
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
      AND COALESCE(n.qtrs, 0) IN (0, 4)
    GROUP BY
        c.requested_name,
        c.canonical_name,
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
roe_series AS (
    SELECT
        am.company,
        am.fiscal_year,
        CASE
            WHEN am.equity IS NULL OR ABS(am.equity) < {min_equity} THEN NULL
            WHEN am.net_income IS NULL THEN NULL
            ELSE 100 * am.net_income / NULLIF(am.equity, 0)
        END AS roe_pct_raw
    FROM annual_metrics am
    JOIN coverage c USING (canonical_name)
    WHERE am.fiscal_year BETWEEN {start_year} AND {end_year}
),
capped AS (
    SELECT
        company,
        fiscal_year,
        CASE
            WHEN roe_pct_raw IS NULL THEN NULL
            WHEN ABS(roe_pct_raw) > {max_abs_roe} THEN NULL
            ELSE roe_pct_raw
        END AS roe_pct
    FROM roe_series
),
final_series AS (
    SELECT
        company,
        fiscal_year,
        roe_pct
    FROM capped
    WHERE roe_pct IS NOT NULL
)
SELECT
    company,
    fiscal_year,
    ROUND(roe_pct, 2) AS roe_pct
FROM final_series
ORDER BY company, fiscal_year
LIMIT {result_limit};
