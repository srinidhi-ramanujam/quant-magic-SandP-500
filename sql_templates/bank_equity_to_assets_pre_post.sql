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
      AND s.fy BETWEEN {pre_start_year} AND {post_end_year}
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
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                )
                THEN n.value
            END
        ) AS equity,
        MAX(CASE WHEN n.tag = 'Assets' THEN n.value END) AS assets
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
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
            WHEN av.equity IS NULL OR ABS(av.equity) < {min_equity} THEN NULL
            ELSE av.equity / av.assets
        END AS equity_to_assets
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
bucketed AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'pre'
            WHEN fiscal_year BETWEEN {post_start_year} AND {post_end_year} THEN 'post'
            ELSE 'other'
        END AS bucket,
        equity_to_assets
    FROM ratios
    WHERE equity_to_assets IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(equity_to_assets) AS avg_ratio,
        COUNT(*) AS year_count
    FROM bucketed
    WHERE bucket IN ('pre','post')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'pre' THEN avg_ratio END) AS pre_ratio,
        MAX(CASE WHEN bucket = 'pre' THEN year_count END) AS pre_years,
        MAX(CASE WHEN bucket = 'post' THEN avg_ratio END) AS post_ratio,
        MAX(CASE WHEN bucket = 'post' THEN year_count END) AS post_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(pre_ratio * 100, 2) AS pre_ratio_pct,
    ROUND(post_ratio * 100, 2) AS post_ratio_pct,
    ROUND((post_ratio - pre_ratio) * 100, 2) AS change_pp,
    pre_years,
    post_years
FROM pivoted
WHERE pre_years IS NOT NULL AND post_years IS NOT NULL
ORDER BY change_pp DESC, name
LIMIT {limit};
