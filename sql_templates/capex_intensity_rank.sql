WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
sector_companies AS (
    SELECT
        cik,
        name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE ('{sector}' = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
      AND (
        {sic_filter_enabled} = 0
        OR (
            sic IS NOT NULL
            AND CAST(sic AS INTEGER) BETWEEN {sic_min} AND {sic_max}
        )
      )
),
list_companies AS (
    SELECT
        c.cik,
        c.name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies c
    JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') = pc.canonical_name
),
combined_companies AS (
    SELECT * FROM list_companies
    UNION ALL
    SELECT * FROM sector_companies
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN combined_companies sc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'PaymentsToAcquirePropertyPlantAndEquipment',
                    'CapitalExpendituresIncurredButNotYetPaid',
                    'PaymentsToAcquireProductiveAssets'
                ) THEN ABS(n.value)
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
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'CapitalExpendituresIncurredButNotYetPaid',
        'PaymentsToAcquireProductiveAssets',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        sc.canonical_name,
        sc.display_name AS company,
        av.fiscal_year,
        av.revenue,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            ELSE av.capex / av.revenue
        END AS capex_intensity
    FROM annual_values av
    JOIN combined_companies sc USING (cik)
),
aggregated AS (
    SELECT
        company,
        canonical_name,
        COUNT(DISTINCT CASE WHEN capex_intensity IS NOT NULL THEN fiscal_year END) AS years_available,
        AVG(capex_intensity) AS avg_capex_intensity,
        MAX(capex_intensity) AS max_capex_intensity,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue END) AS latest_revenue
    FROM ratios
    GROUP BY company, canonical_name
)
SELECT
    company AS name,
    ROUND(avg_capex_intensity * 100, 2) AS avg_capex_intensity_pct,
    ROUND(max_capex_intensity * 100, 2) AS peak_capex_intensity_pct,
    ROUND(latest_revenue / 1000000000.0, 2) AS revenue_latest_billions,
    years_available
FROM aggregated
WHERE years_available >= 1
  AND latest_revenue IS NOT NULL
  AND latest_revenue >= {min_revenue}
ORDER BY avg_capex_intensity DESC NULLS LAST, peak_capex_intensity_pct DESC NULLS LAST, name
LIMIT {limit};
