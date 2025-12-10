WITH sector_companies AS (
    SELECT
        cik,
        name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
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
        sc.display_name AS name,
        sc.canonical_name,
        av.fiscal_year,
        av.cfo,
        av.capex,
        CASE
            WHEN av.cfo IS NULL OR av.capex IS NULL THEN NULL
            WHEN ABS(av.capex) < {min_capex_abs} THEN NULL
            WHEN av.cfo < {min_cfo} THEN NULL
            ELSE av.cfo / NULLIF(av.capex, 0)
        END AS cfo_to_capex
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
),
filtered AS (
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY canonical_name) AS reported_years
    FROM ratios
    WHERE cfo_to_capex IS NOT NULL
)
SELECT
    name,
    fiscal_year,
    ROUND(cfo / 1000000000.0, 2) AS cfo_billions,
    ROUND(capex / 1000000000.0, 2) AS capex_billions,
    ROUND(cfo_to_capex, 2) AS cfo_to_capex_ratio,
    reported_years
FROM filtered
WHERE reported_years >= {min_years}
ORDER BY name, fiscal_year
LIMIT {limit};
