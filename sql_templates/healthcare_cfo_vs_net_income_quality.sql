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
        MAX(CASE WHEN n.tag = 'NetCashProvidedByUsedInOperatingActivities' THEN n.value END) AS cfo,
        MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) AS net_income
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'NetIncomeLoss'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.cfo,
        av.net_income,
        CASE
            WHEN av.net_income IS NULL OR av.net_income = 0 THEN NULL
            WHEN av.cfo IS NULL THEN NULL
            ELSE av.cfo / av.net_income
        END AS cfo_to_net_income
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
        cfo_to_net_income
    FROM ratios
    WHERE cfo_to_net_income IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(cfo_to_net_income) AS avg_ratio,
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
    ROUND(pre_ratio, 2) AS pre_cfo_to_net_income,
    ROUND(post_ratio, 2) AS post_cfo_to_net_income,
    ROUND(post_ratio - pre_ratio, 2) AS ratio_change,
    pre_years,
    post_years
FROM pivoted
WHERE pre_years IS NOT NULL AND post_years IS NOT NULL
ORDER BY ratio_change DESC, name
LIMIT {limit};
