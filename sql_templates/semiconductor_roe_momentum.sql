WITH provided_companies AS (
    -- Optional explicit cohort
    SELECT * FROM (VALUES {company_values}) AS t(company_name)
),
sector_companies AS (
    -- Sector fallback for momentum comparisons
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
        COALESCE(
            REGEXP_REPLACE(UPPER(TRIM(pc.company_name)), '[^A-Z0-9]', '', 'g'),
            c.canonical_name
        ) AS canonical_name
    FROM sector_companies c
    FULL OUTER JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.company_name)), '[^A-Z0-9]', '', 'g') =
         REGEXP_REPLACE(UPPER(TRIM(pc.company_name)), '[^A-Z0-9]', '', 'g')
),
ranked_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN cohort c USING (cik)
    WHERE s.form IN ('10-K','10-K/A','20-F')
      AND s.fy BETWEEN {baseline_start_year} AND {boom_end_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
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
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
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
    GROUP BY lf.cik, lf.fiscal_year
),
roe_series AS (
    SELECT
        c.company_name AS name,
        av.fiscal_year,
        CASE
            WHEN av.equity IS NULL OR ABS(av.equity) < {min_equity} THEN NULL
            WHEN av.net_income IS NULL THEN NULL
            ELSE av.net_income / NULLIF(av.equity, 0)
        END AS roe
    FROM annual_values av
    JOIN cohort c USING (cik)
),
filtered AS (
    SELECT
        name,
        fiscal_year,
        CASE
            WHEN roe IS NULL THEN NULL
            WHEN ABS(roe * 100) > {max_abs_roe_pct} THEN NULL
            ELSE roe
        END AS roe
    FROM roe_series
),
bucketed AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {baseline_start_year} AND {baseline_end_year} THEN 'baseline'
            WHEN fiscal_year BETWEEN {boom_start_year} AND {boom_end_year} THEN 'boom'
            ELSE 'other'
        END AS bucket,
        roe
    FROM filtered
    WHERE roe IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(roe) AS avg_roe,
        COUNT(*) AS year_count
    FROM bucketed
    WHERE bucket IN ('baseline','boom')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'baseline' THEN avg_roe END) AS baseline_roe,
        MAX(CASE WHEN bucket = 'baseline' THEN year_count END) AS baseline_years,
        MAX(CASE WHEN bucket = 'boom' THEN avg_roe END) AS boom_roe,
        MAX(CASE WHEN bucket = 'boom' THEN year_count END) AS boom_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(baseline_roe * 100, 2) AS baseline_roe_pct,
    ROUND(boom_roe * 100, 2) AS boom_roe_pct,
    ROUND((boom_roe - baseline_roe) * 100, 2) AS roe_delta_pp,
    baseline_years,
    boom_years
FROM pivoted
WHERE baseline_years IS NOT NULL AND boom_years IS NOT NULL
ORDER BY roe_delta_pp DESC, name
LIMIT {limit};
