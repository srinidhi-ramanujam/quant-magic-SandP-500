WITH target_company AS (
    SELECT cik, name AS company_name
    FROM companies
    WHERE UPPER(name) LIKE UPPER('%{company}%')
    ORDER BY LENGTH(name)
    LIMIT 1
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN target_company tc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'NetCashProvidedByUsedInOperatingActivities',
                    'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
                ) THEN n.value
            END
        ) AS cfo,
        MAX(
            CASE
                WHEN n.tag IN (
                    'PaymentsToAcquirePropertyPlantAndEquipment',
                    'PurchaseOfPropertyPlantAndEquipment',
                    'PaymentsToAcquireProductiveAssets',
                    'PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets'
                ) THEN n.value
            END
        ) AS capex
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PurchaseOfPropertyPlantAndEquipment',
        'PaymentsToAcquireProductiveAssets',
        'PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
fcf_series AS (
    SELECT
        tc.company_name AS company,
        av.fiscal_year,
        av.cfo,
        av.capex,
        CASE
            WHEN av.cfo IS NULL OR av.capex IS NULL THEN NULL
            ELSE av.cfo - ABS(av.capex)
        END AS free_cash_flow
    FROM annual_values av
    JOIN target_company tc USING (cik)
),
aggregated AS (
    SELECT
        company,
        COUNT(*) AS year_count,
        AVG(free_cash_flow) AS avg_fcf,
        STDDEV_SAMP(free_cash_flow) AS fcf_volatility
    FROM fcf_series
    WHERE free_cash_flow IS NOT NULL
    GROUP BY company
),
scored AS (
    SELECT
        company,
        year_count,
        avg_fcf,
        fcf_volatility,
        CASE
            WHEN avg_fcf = 0 THEN NULL
            ELSE fcf_volatility / NULLIF(avg_fcf, 0)
        END AS coefficient_of_variation
    FROM aggregated
)
SELECT
    company,
    year_count,
    ROUND(avg_fcf / 1000000000.0, 2) AS avg_fcf_billions,
    ROUND(fcf_volatility / 1000000000.0, 2) AS fcf_volatility_billions,
    ROUND(coefficient_of_variation, 3) AS fcf_volatility_ratio
FROM scored
WHERE coefficient_of_variation IS NOT NULL
ORDER BY coefficient_of_variation ASC;

