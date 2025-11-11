WITH sector_companies AS (
    SELECT
        cik,
        name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
base_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN 2019 AND 2023
),
filings AS (
    SELECT adsh, cik, fiscal_year, period
    FROM base_filings
    WHERE rn = 1
),
values AS (
    SELECT
        f.cik,
        f.fiscal_year,
        MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) AS net_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue
    FROM filings f
    JOIN num n ON n.adsh = f.adsh AND n.ddate = f.period
    WHERE n.tag IN (
        'NetIncomeLoss',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
    GROUP BY f.cik, f.fiscal_year
),
margins AS (
    SELECT
        sc.canonical_name,
        sc.name AS display_name,
        v.fiscal_year,
        v.net_income / NULLIF(v.revenue, 0) AS profit_margin
    FROM values v
    JOIN sector_companies sc USING (cik)
    WHERE v.net_income IS NOT NULL
      AND v.revenue IS NOT NULL
),
ordered AS (
    SELECT
        m.*,
        LEAD(m.profit_margin) OVER (PARTITION BY m.canonical_name ORDER BY m.fiscal_year) AS next_margin,
        LEAD(m.fiscal_year) OVER (PARTITION BY m.canonical_name ORDER BY m.fiscal_year) AS next_year
    FROM margins m
)
SELECT
    display_name AS name,
    ROUND(MAX(CASE WHEN fiscal_year = 2019 THEN profit_margin END) * 100, 2) AS margin_2019_pct,
    ROUND(MAX(CASE WHEN fiscal_year = 2020 THEN profit_margin END) * 100, 2) AS margin_2020_pct,
    ROUND(MAX(CASE WHEN fiscal_year = 2021 THEN profit_margin END) * 100, 2) AS margin_2021_pct,
    ROUND(MAX(CASE WHEN fiscal_year = 2022 THEN profit_margin END) * 100, 2) AS margin_2022_pct,
    ROUND(MAX(CASE WHEN fiscal_year = 2023 THEN profit_margin END) * 100, 2) AS margin_2023_pct,
    ROUND(
        (MAX(CASE WHEN fiscal_year = 2023 THEN profit_margin END) - MIN(CASE WHEN fiscal_year = 2019 THEN profit_margin END))
        * 100,
        2
    ) AS improvement_pct,
    SUM(
        CASE
            WHEN next_year = fiscal_year + 1
             AND next_margin IS NOT NULL
             AND next_margin >= profit_margin THEN 1
            ELSE 0
        END
    ) AS consistency_steps
FROM ordered
GROUP BY display_name
HAVING COUNT(DISTINCT fiscal_year) = 5
ORDER BY consistency_steps DESC, improvement_pct DESC, display_name
LIMIT 5;
