WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
sector_a_companies AS (
    SELECT
        cik,
        name,
        gics_sector
    FROM companies
    WHERE LOWER(gics_sector) LIKE LOWER('%{sector_a}%')
),
sector_b_companies AS (
    SELECT
        cik,
        name,
        gics_sector
    FROM companies
    WHERE LOWER(gics_sector) LIKE LOWER('%{sector_b}%')
),
list_companies AS (
    SELECT
        c.cik,
        c.name,
        c.gics_sector,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies c
    JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') = pc.canonical_name
),
company_dim AS (
    SELECT * FROM list_companies
    UNION ALL
    SELECT cik, name, gics_sector, REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name FROM sector_a_companies
    UNION ALL
    SELECT cik, name, gics_sector, REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name FROM sector_b_companies
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_dim cd USING (cik)
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
        MAX(CASE WHEN n.tag IN ('GrossProfit', 'GrossProfit') THEN n.value END) AS gross_profit,
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
        'GrossProfit',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
margins AS (
    SELECT
        av.fiscal_year,
        CASE WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL ELSE av.gross_profit / av.revenue END AS gross_margin,
        CASE
            WHEN LOWER(cd.gics_sector) LIKE LOWER('%{sector_a}%') THEN 'A'
            WHEN LOWER(cd.gics_sector) LIKE LOWER('%{sector_b}%') THEN 'B'
            ELSE 'Provided'
        END AS sector_group
    FROM annual_values av
    JOIN company_dim cd USING (cik)
)
SELECT
    fiscal_year,
    ROUND(AVG(CASE WHEN sector_group = 'A' THEN gross_margin END) * 100, 2) AS sector_a_margin_pct,
    ROUND(AVG(CASE WHEN sector_group = 'B' THEN gross_margin END) * 100, 2) AS sector_b_margin_pct,
    ROUND(
        (AVG(CASE WHEN sector_group = 'A' THEN gross_margin END)
        - AVG(CASE WHEN sector_group = 'B' THEN gross_margin END)) * 100,
        2
    ) AS margin_spread_pp
FROM margins
WHERE gross_margin IS NOT NULL
GROUP BY fiscal_year
HAVING fiscal_year BETWEEN {start_year} AND {end_year}
ORDER BY fiscal_year;
