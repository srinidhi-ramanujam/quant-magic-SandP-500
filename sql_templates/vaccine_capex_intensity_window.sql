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
      AND s.fy BETWEEN {pre_start_year} AND {vaccine_end_year}
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
        cd.display_name AS name,
        av.fiscal_year,
        av.cfo,
        av.capex,
        CASE
            WHEN av.cfo IS NULL OR av.cfo = 0 THEN NULL
            WHEN av.capex IS NULL THEN NULL
            ELSE ABS(av.capex) / av.cfo
        END AS capex_intensity
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
bucketed AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'pre'
            WHEN fiscal_year BETWEEN {vaccine_start_year} AND {vaccine_end_year} THEN 'vaccine'
            ELSE 'other'
        END AS bucket,
        capex_intensity
    FROM ratios
    WHERE capex_intensity IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(capex_intensity) AS avg_intensity,
        COUNT(*) AS year_count
    FROM bucketed
    WHERE bucket IN ('pre','vaccine')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'pre' THEN avg_intensity END) AS pre_intensity,
        MAX(CASE WHEN bucket = 'pre' THEN year_count END) AS pre_years,
        MAX(CASE WHEN bucket = 'vaccine' THEN avg_intensity END) AS vaccine_intensity,
        MAX(CASE WHEN bucket = 'vaccine' THEN year_count END) AS vaccine_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(pre_intensity, 2) AS pre_capex_intensity,
    ROUND(vaccine_intensity, 2) AS vaccine_capex_intensity,
    ROUND(vaccine_intensity - pre_intensity, 2) AS intensity_delta,
    pre_years,
    vaccine_years
FROM pivoted
WHERE pre_years IS NOT NULL AND vaccine_years IS NOT NULL
ORDER BY intensity_delta DESC, name
LIMIT {limit};
