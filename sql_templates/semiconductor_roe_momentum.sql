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
      AND s.fy BETWEEN {baseline_start_year} AND {boom_end_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) AS net_income,
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
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
roe_series AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        CASE
            WHEN av.equity IS NULL OR av.equity = 0 THEN NULL
            WHEN av.net_income IS NULL THEN NULL
            WHEN ABS(av.net_income / av.equity * 100) > {max_abs_roe_pct} THEN NULL
            ELSE av.net_income / av.equity
        END AS roe
    FROM annual_values av
    JOIN company_dim cd USING (cik)
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
    FROM roe_series
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
