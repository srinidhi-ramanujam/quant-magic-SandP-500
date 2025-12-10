WITH provided_companies AS (
    SELECT * FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT c.cik, pc.company_name AS display_name
    FROM companies c
    JOIN provided_companies pc ON UPPER(c.name) = UPPER(pc.company_name)
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
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {pre_start_year} AND {build_end_year}
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
                    'CashAndCashEquivalentsAtCarryingValue',
                    'CashCashEquivalentsAndShortTermInvestments'
                ) THEN n.value
            END
        ) AS cash_and_sti,
        MAX(CASE WHEN n.tag = 'Assets' THEN n.value END) AS assets
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'CashAndCashEquivalentsAtCarryingValue',
        'CashCashEquivalentsAndShortTermInvestments',
        'Assets'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        CASE
            WHEN av.assets IS NULL OR av.assets = 0 THEN NULL
            WHEN av.cash_and_sti IS NULL THEN NULL
            ELSE av.cash_and_sti / av.assets
        END AS cash_to_assets
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
bucketed AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'pre'
            WHEN fiscal_year BETWEEN {build_start_year} AND {build_end_year} THEN 'build'
            ELSE 'other'
        END AS bucket,
        cash_to_assets
    FROM ratios
    WHERE cash_to_assets IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(cash_to_assets) AS avg_ratio,
        COUNT(*) AS year_count
    FROM bucketed
    WHERE bucket IN ('pre','build')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'pre' THEN avg_ratio END) AS pre_ratio,
        MAX(CASE WHEN bucket = 'pre' THEN year_count END) AS pre_years,
        MAX(CASE WHEN bucket = 'build' THEN avg_ratio END) AS build_ratio,
        MAX(CASE WHEN bucket = 'build' THEN year_count END) AS build_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(pre_ratio * 100, 2) AS pre_ratio_pct,
    ROUND(build_ratio * 100, 2) AS build_ratio_pct,
    ROUND((build_ratio - pre_ratio) * 100, 2) AS change_pp,
    pre_years,
    build_years
FROM pivoted
WHERE pre_years IS NOT NULL AND build_years IS NOT NULL
ORDER BY change_pp DESC, name
LIMIT {limit};
