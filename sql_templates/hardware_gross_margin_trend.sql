WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT
        c.cik,
        pc.provided_name AS requested_name,
        c.name AS dataset_name
    FROM companies c
    JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') = pc.canonical_name
      OR UPPER(c.name) LIKE '%' || UPPER(pc.provided_name) || '%'
),
ranked_filings AS (
    SELECT
        s.adsh,
        s.cik,
        s.period AS period_end,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.fp,
        s.filed,
        ROW_NUMBER() OVER (
            PARTITION BY s.cik, s.period
            ORDER BY s.filed DESC
        ) AS period_rank
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-Q', '10-Q/A')
      AND s.period >= DATE '{min_period}'
),
latest_quarters AS (
    SELECT
        rf.adsh,
        rf.cik,
        rf.period_end,
        rf.fiscal_year,
        rf.fp,
        ROW_NUMBER() OVER (
            PARTITION BY rf.cik
            ORDER BY rf.period_end DESC
        ) AS seq
    FROM ranked_filings rf
    WHERE rf.period_rank = 1
),
filtered_quarters AS (
    SELECT *
    FROM latest_quarters
    WHERE seq <= {quarter_count}
),
quarterly_values AS (
    SELECT
        fq.cik,
        fq.period_end,
        fq.fiscal_year,
        fq.fp,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                )
                AND COALESCE(n.qtrs, 0) = 1
                THEN n.value
            END
        ) AS revenue,
        MAX(
            CASE
                WHEN n.tag IN (
                    'CostOfRevenue',
                    'CostOfGoodsSold',
                    'CostOfGoodsAndServicesSold'
                )
                AND COALESCE(n.qtrs, 0) = 1
                THEN n.value
            END
        ) AS cogs
    FROM filtered_quarters fq
    JOIN num n
      ON n.adsh = fq.adsh
     AND n.ddate = fq.period_end
    WHERE n.tag IN (
        'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet',
        'CostOfRevenue','CostOfGoodsSold','CostOfGoodsAndServicesSold'
    )
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY fq.cik, fq.period_end, fq.fiscal_year, fq.fp
),
metrics AS (
    SELECT
        cd.requested_name AS company,
        CAST(qv.period_end AS DATE) AS period_end,
        qv.fiscal_year,
        qv.fp,
        qv.revenue,
        qv.cogs,
        CASE
            WHEN qv.revenue IS NULL OR qv.revenue = 0 THEN NULL
            ELSE (qv.revenue - qv.cogs) / qv.revenue
        END AS gross_margin
    FROM quarterly_values qv
    JOIN company_dim cd USING (cik)
)
SELECT
    company,
    period_end,
    fiscal_year,
    fp AS fiscal_period,
    ROUND(revenue / 1000000.0, 2) AS revenue_millions,
    ROUND(cogs / 1000000.0, 2) AS cogs_millions,
    ROUND(gross_margin * 100, 2) AS gross_margin_pct
FROM metrics
WHERE revenue IS NOT NULL
  AND cogs IS NOT NULL
  AND gross_margin IS NOT NULL
ORDER BY company, period_end DESC;

