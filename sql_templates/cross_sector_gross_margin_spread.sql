WITH sector_companies AS (
    SELECT
        cik,
        name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name,
        gics_sector
    FROM companies
    WHERE UPPER(gics_sector) IN (UPPER('{sector_a}'), UPPER('{sector_b}'))
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
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue,
        MAX(
            CASE
                WHEN n.tag IN (
                    'CostOfRevenue',
                    'CostOfGoodsSold',
                    'CostOfGoodsAndServicesSold'
                ) THEN n.value
            END
        ) AS cogs
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet',
        'CostOfRevenue','CostOfGoodsSold','CostOfGoodsAndServicesSold'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
margins AS (
    SELECT
        sc.gics_sector,
        sc.display_name,
        av.fiscal_year,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            WHEN av.cogs IS NULL THEN NULL
            ELSE (av.revenue - av.cogs) / av.revenue
        END AS gross_margin
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
),
sector_avg AS (
    SELECT
        gics_sector,
        fiscal_year,
        AVG(gross_margin) AS avg_gross_margin,
        COUNT(*) AS company_count
    FROM margins
    WHERE gross_margin IS NOT NULL
    GROUP BY gics_sector, fiscal_year
),
paired AS (
    SELECT
        a.fiscal_year,
        a.avg_gross_margin AS sector_a_margin,
        a.company_count AS sector_a_companies,
        b.avg_gross_margin AS sector_b_margin,
        b.company_count AS sector_b_companies,
        a.avg_gross_margin - b.avg_gross_margin AS margin_spread
    FROM sector_avg a
    JOIN sector_avg b
      ON a.fiscal_year = b.fiscal_year
     AND UPPER(a.gics_sector) = UPPER('{sector_a}')
     AND UPPER(b.gics_sector) = UPPER('{sector_b}')
)
SELECT
    fiscal_year,
    ROUND(sector_a_margin * 100, 2) AS sector_a_margin_pct,
    ROUND(sector_b_margin * 100, 2) AS sector_b_margin_pct,
    ROUND(margin_spread * 100, 2) AS spread_pct_points,
    sector_a_companies,
    sector_b_companies
FROM paired
ORDER BY fiscal_year, spread_pct_points DESC
LIMIT {limit};
