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
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'NetCashProvidedByUsedInOperatingActivities' THEN n.value END) AS cfo,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
metrics AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.cfo,
        av.revenue,
        CASE
            WHEN av.revenue IS NULL OR av.revenue < {min_revenue} THEN NULL
            ELSE av.cfo
        END AS cfo_filtered
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN fiscal_year = {baseline_year} THEN cfo_filtered END) AS baseline_cfo,
        MAX(CASE WHEN fiscal_year = {recovery_year_1} THEN cfo_filtered END) AS recovery_cfo_1,
        MAX(CASE WHEN fiscal_year = {recovery_year_2} THEN cfo_filtered END) AS recovery_cfo_2
    FROM metrics
    GROUP BY name
)
SELECT
    name,
    ROUND(baseline_cfo / 1000000000.0, 2) AS baseline_cfo_billions,
    ROUND(recovery_cfo_1 / 1000000000.0, 2) AS recovery_cfo_1_billions,
    ROUND(recovery_cfo_2 / 1000000000.0, 2) AS recovery_cfo_2_billions,
    ROUND((recovery_cfo_2 - baseline_cfo) / 1000000000.0, 2) AS delta_vs_baseline_billions
FROM pivoted
WHERE baseline_cfo IS NOT NULL AND recovery_cfo_1 IS NOT NULL AND recovery_cfo_2 IS NOT NULL
ORDER BY delta_vs_baseline_billions DESC, name
LIMIT {limit};
