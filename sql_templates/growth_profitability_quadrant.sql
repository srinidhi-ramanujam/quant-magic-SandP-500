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
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue,
        MAX(CASE WHEN n.tag = 'OperatingIncomeLoss' THEN n.value END) AS operating_income
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',
        'OperatingIncomeLoss'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
cohort AS (
    SELECT
        sc.canonical_name,
        ANY_VALUE(sc.name) AS company,
        MAX(CASE WHEN av.fiscal_year = {start_year} THEN av.revenue END) AS revenue_start,
        MAX(CASE WHEN av.fiscal_year = {end_year} THEN av.revenue END) AS revenue_end,
        MAX(
            CASE
                WHEN av.fiscal_year = {end_year}
                THEN CASE
                    WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
                    ELSE av.operating_income / av.revenue
                END
            END
        ) AS latest_margin
    FROM annual_values av
    JOIN combined_companies sc USING (cik)
    GROUP BY sc.canonical_name
)
SELECT
    company AS name,
    ROUND(
        CASE
            WHEN revenue_start IS NULL OR revenue_start = 0 OR revenue_end IS NULL
                 OR {end_year} = {start_year}
            THEN NULL
            ELSE (POWER(revenue_end / revenue_start, 1.0 / ({end_year} - {start_year})) - 1) * 100
        END,
        2
    ) AS revenue_cagr_pct,
    ROUND(latest_margin * 100, 2) AS operating_margin_latest_pct,
    ROUND(revenue_end / 1000000000.0, 2) AS revenue_latest_billions
FROM cohort
WHERE revenue_start IS NOT NULL
  AND revenue_end IS NOT NULL
  AND revenue_end >= {min_revenue}
  AND (
        (POWER(revenue_end / revenue_start, 1.0 / ({end_year} - {start_year})) - 1) * 100
      ) >= {growth_threshold_pct}
  AND latest_margin IS NOT NULL
  AND latest_margin * 100 >= {margin_threshold_pct}
ORDER BY revenue_cagr_pct DESC, operating_margin_latest_pct DESC
LIMIT {limit};
