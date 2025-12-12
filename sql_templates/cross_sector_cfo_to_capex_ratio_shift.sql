WITH sector_companies AS (
    SELECT
        cik,
        name AS display_name,
        UPPER(gics_sector) AS sector
    FROM companies
    WHERE UPPER(gics_sector) IN (UPPER('{sector_a}'), UPPER('{sector_b}'), UPPER('{sector_c}'))
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
    JOIN sector_companies sc USING (cik)
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
        ) AS capex
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PurchaseOfPropertyPlantAndEquipment',
        'PaymentsToAcquireProductiveAssets'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        sc.sector,
        av.fiscal_year,
        CASE
            WHEN av.cfo IS NULL OR av.capex IS NULL THEN NULL
            WHEN ABS(av.capex) < {min_capex_abs} THEN NULL
            WHEN av.cfo < {min_cfo} THEN NULL
            ELSE av.cfo / NULLIF(av.capex, 0)
        END AS cfo_to_capex
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
),
bucketed AS (
    SELECT
        sector,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'pre'
            WHEN fiscal_year BETWEEN {post_start_year} AND {post_end_year} THEN 'post'
            ELSE 'other'
        END AS bucket,
        cfo_to_capex
    FROM ratios
    WHERE cfo_to_capex IS NOT NULL
),
aggregated AS (
    SELECT
        sector,
        bucket,
        AVG(cfo_to_capex) AS avg_ratio,
        COUNT(*) AS company_years
    FROM bucketed
    WHERE bucket IN ('pre','post')
    GROUP BY sector, bucket
),
pivoted AS (
    SELECT
        sector,
        MAX(CASE WHEN bucket = 'pre' THEN avg_ratio END) AS pre_ratio,
        MAX(CASE WHEN bucket = 'pre' THEN company_years END) AS pre_company_years,
        MAX(CASE WHEN bucket = 'post' THEN avg_ratio END) AS post_ratio,
        MAX(CASE WHEN bucket = 'post' THEN company_years END) AS post_company_years
    FROM aggregated
    GROUP BY sector
)
SELECT
    sector,
    ROUND(pre_ratio, 2) AS pre_ratio,
    ROUND(post_ratio, 2) AS post_ratio,
    ROUND(post_ratio - pre_ratio, 2) AS ratio_change,
    pre_company_years,
    post_company_years
FROM pivoted
WHERE pre_ratio IS NOT NULL AND post_ratio IS NOT NULL
ORDER BY ratio_change DESC, sector
LIMIT {limit};
