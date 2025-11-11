WITH sector_companies AS (
    SELECT
        cik,
        name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy IN ({start_year}, {end_year})
),
latest AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'OperatingIncomeLoss' THEN n.value END) AS operating_income,
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
        'OperatingIncomeLoss',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
    GROUP BY lf.cik, lf.fiscal_year
),
agg AS (
    SELECT
        sc.canonical_name,
        ANY_VALUE(sc.name) AS display_name,
        MAX(CASE WHEN v.fiscal_year = {start_year} THEN v.operating_income / NULLIF(v.revenue, 0) END) AS margin_start,
        MAX(CASE WHEN v.fiscal_year = {end_year} THEN v.operating_income / NULLIF(v.revenue, 0) END) AS margin_end,
        MAX(CASE WHEN v.fiscal_year = {end_year} THEN v.revenue END) AS revenue_end
    FROM values v
    JOIN sector_companies sc USING (cik)
    GROUP BY sc.canonical_name
    HAVING COUNT(DISTINCT v.fiscal_year) = 2
)
SELECT
    display_name AS name,
    ROUND(margin_start * 100, 2) AS margin_{start_year}_pct,
    ROUND(margin_end * 100, 2) AS margin_{end_year}_pct,
    ROUND((margin_end - margin_start) * 100, 2) AS improvement_pp,
    ROUND(revenue_end / 1000000000, 2) AS revenue_{end_year}_billions
FROM agg
WHERE revenue_end >= {min_revenue}
  AND margin_end IS NOT NULL
  AND margin_start IS NOT NULL
ORDER BY improvement_pp DESC
LIMIT {limit};
