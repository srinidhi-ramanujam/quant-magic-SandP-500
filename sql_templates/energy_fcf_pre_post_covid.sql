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
        MAX(
            CASE
                WHEN n.tag IN (
                    'PaymentsToAcquirePropertyPlantAndEquipment',
                    'PurchaseOfPropertyPlantAndEquipment',
                    'PaymentsToAcquireProductiveAssets'
                ) THEN n.value
            END
        ) AS capex,
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
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PurchaseOfPropertyPlantAndEquipment',
        'PaymentsToAcquireProductiveAssets',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
fcf_series AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.cfo,
        av.capex,
        av.revenue,
        CASE
            WHEN av.cfo IS NULL OR av.capex IS NULL THEN NULL
            WHEN av.revenue IS NULL OR av.revenue < {min_revenue} THEN NULL
            ELSE av.cfo - ABS(av.capex)
        END AS free_cash_flow
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
        free_cash_flow
    FROM fcf_series
    WHERE free_cash_flow IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(free_cash_flow) AS avg_fcf,
        COUNT(*) AS year_count
    FROM bucketed
    WHERE bucket IN ('pre','post')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'pre' THEN avg_fcf END) AS pre_fcf,
        MAX(CASE WHEN bucket = 'pre' THEN year_count END) AS pre_years,
        MAX(CASE WHEN bucket = 'post' THEN avg_fcf END) AS post_fcf,
        MAX(CASE WHEN bucket = 'post' THEN year_count END) AS post_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(pre_fcf / 1000000000.0, 2) AS pre_fcf_billions,
    ROUND(post_fcf / 1000000000.0, 2) AS post_fcf_billions,
    ROUND((post_fcf - pre_fcf) / 1000000000.0, 2) AS delta_billions,
    pre_years,
    post_years
FROM pivoted
WHERE pre_years IS NOT NULL AND post_years IS NOT NULL
ORDER BY delta_billions DESC, name
LIMIT {limit};
