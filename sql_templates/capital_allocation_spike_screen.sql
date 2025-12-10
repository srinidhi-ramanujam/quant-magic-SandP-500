WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
sector_companies AS (
    SELECT
        cik,
        name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE ('{sector}' = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
list_companies AS (
    SELECT
        c.cik,
        c.name,
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
    SELECT *
    FROM annual_filings
    WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag = 'PaymentsToAcquireBusinessesNetOfCashAcquired' THEN ABS(n.value)
            END
        ) AS acquisition_spend,
        MAX(
            CASE
                WHEN n.tag IN (
                    'PaymentsToAcquirePropertyPlantAndEquipment',
                    'PaymentsToAcquireProductiveAssets',
                    'CapitalExpendituresIncurredButNotYetPaid'
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
        'PaymentsToAcquireBusinessesNetOfCashAcquired',
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PaymentsToAcquireProductiveAssets',
        'CapitalExpendituresIncurredButNotYetPaid',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
scored AS (
    SELECT
        sc.canonical_name,
        sc.name AS company,
        SUM(COALESCE(av.acquisition_spend, 0)) AS total_acquisition_spend,
        MAX(CASE WHEN av.fiscal_year = {end_year} THEN av.revenue END) AS latest_revenue,
        MAX(
            CASE
                WHEN av.fiscal_year = {end_year}
                THEN CASE
                    WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
                    ELSE COALESCE(av.capex, 0) / av.revenue
                END
            END
        ) AS capex_to_revenue_latest,
        MAX(
            CASE
                WHEN av.fiscal_year BETWEEN {start_year} AND {end_year}
                THEN CASE
                    WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
                    ELSE COALESCE(av.capex, 0) / av.revenue
                END
            END
        ) AS max_capex_to_revenue
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
    GROUP BY sc.canonical_name
)
SELECT
    company AS name,
    ROUND(total_acquisition_spend / 1000000000.0, 2) AS acquisition_spend_billions,
    ROUND(capex_to_revenue_latest * 100, 2) AS capex_to_revenue_latest_pct,
    ROUND(max_capex_to_revenue * 100, 2) AS max_capex_to_revenue_pct,
    ROUND(latest_revenue / 1000000000.0, 2) AS revenue_latest_billions
FROM scored
WHERE (total_acquisition_spend >= {acquisition_threshold})
   OR (capex_to_revenue_latest IS NOT NULL AND capex_to_revenue_latest >= {capex_to_revenue_threshold})
   OR (max_capex_to_revenue IS NOT NULL AND max_capex_to_revenue >= {capex_to_revenue_threshold})
ORDER BY
    total_acquisition_spend DESC,
    capex_to_revenue_latest DESC NULLS LAST,
    company
LIMIT {limit};
