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
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue,
        MAX(CASE WHEN n.tag IN ('OperatingIncomeLoss') THEN n.value END) AS operating_income
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet',
        'OperatingIncomeLoss'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
margins AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.revenue,
        av.operating_income,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            WHEN av.operating_income IS NULL THEN NULL
            WHEN av.revenue < {min_revenue} THEN NULL
            ELSE av.operating_income / av.revenue
        END AS operating_margin
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
periods AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'pre'
            WHEN fiscal_year BETWEEN {post_start_year} AND {post_end_year} THEN 'post'
            ELSE 'other'
        END AS period_bucket,
        fiscal_year,
        operating_margin
    FROM margins
    WHERE operating_margin IS NOT NULL
      AND fiscal_year BETWEEN {pre_start_year} AND {post_end_year}
),
aggregated AS (
    SELECT
        name,
        period_bucket,
        AVG(operating_margin) AS avg_margin,
        COUNT(*) AS year_count
    FROM periods
    WHERE period_bucket IN ('pre', 'post')
    GROUP BY name, period_bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN period_bucket = 'pre' THEN avg_margin END) AS pre_margin,
        MAX(CASE WHEN period_bucket = 'pre' THEN year_count END) AS pre_years,
        MAX(CASE WHEN period_bucket = 'post' THEN avg_margin END) AS post_margin,
        MAX(CASE WHEN period_bucket = 'post' THEN year_count END) AS post_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(pre_margin * 100, 2) AS pre_margin_pct,
    ROUND(post_margin * 100, 2) AS post_margin_pct,
    ROUND((post_margin - pre_margin) * 100, 2) AS margin_delta_pp,
    pre_years,
    post_years
FROM pivoted
WHERE pre_years IS NOT NULL AND post_years IS NOT NULL
ORDER BY margin_delta_pp DESC, name
LIMIT {limit};
