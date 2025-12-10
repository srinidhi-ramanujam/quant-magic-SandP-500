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
      AND s.fy BETWEEN {pre_start_year} AND {post_end_year}
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
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
margins AS (
    SELECT
        sc.canonical_name,
        sc.name AS company,
        av.fiscal_year,
        av.revenue,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            ELSE av.operating_income / av.revenue
        END AS operating_margin
    FROM annual_values av
    JOIN combined_companies sc USING (cik)
),
windowed AS (
    SELECT
        company,
        canonical_name,
        AVG(
            CASE
                WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN operating_margin
            END
        ) AS pre_margin,
        AVG(
            CASE
                WHEN fiscal_year BETWEEN {post_start_year} AND {post_end_year} THEN operating_margin
            END
        ) AS post_margin,
        COUNT(
            DISTINCT CASE
                WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year}
                     AND operating_margin IS NOT NULL
                THEN fiscal_year
            END
        ) AS pre_years,
        COUNT(
            DISTINCT CASE
                WHEN fiscal_year BETWEEN {post_start_year} AND {post_end_year}
                     AND operating_margin IS NOT NULL
                THEN fiscal_year
            END
        ) AS post_years,
        MAX(
            CASE
                WHEN fiscal_year BETWEEN {post_start_year} AND {post_end_year} THEN revenue
            END
        ) AS post_revenue
    FROM margins
    GROUP BY company, canonical_name
)
SELECT
    company AS name,
    ROUND(pre_margin * 100, 2) AS avg_margin_pre_pct,
    ROUND(post_margin * 100, 2) AS avg_margin_post_pct,
    ROUND((post_margin - pre_margin) * 100, 2) AS rebound_pp,
    ROUND(post_revenue / 1000000000.0, 2) AS revenue_post_billions
FROM windowed
WHERE pre_margin IS NOT NULL
  AND post_margin IS NOT NULL
  AND pre_years >= 1
  AND post_years >= 1
  AND post_revenue >= {min_revenue}
  AND (post_margin - pre_margin) * 100 >= {min_improvement_pp}
ORDER BY rebound_pp DESC, revenue_post_billions DESC
LIMIT {limit};
