WITH provided_companies AS (
    SELECT * FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT c.cik, pc.company_name AS display_name
    FROM companies c
    JOIN provided_companies pc ON UPPER(c.name) = UPPER(pc.company_name)
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
    JOIN company_dim cd USING (cik)
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
        ) AS cogs,
        MAX(CASE WHEN n.tag = 'InventoryNet' THEN n.value END) AS inventory
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet',
        'CostOfRevenue','CostOfGoodsSold','CostOfGoodsAndServicesSold',
        'InventoryNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
with_turnover AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.revenue,
        av.cogs,
        av.inventory,
        AVG(av.inventory) OVER (PARTITION BY cd.cik ORDER BY av.fiscal_year ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS avg_inventory
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
metrics AS (
    SELECT
        name,
        fiscal_year,
        revenue,
        CASE
            WHEN avg_inventory IS NULL OR cogs IS NULL OR cogs = 0 THEN NULL
            ELSE cogs / NULLIF(avg_inventory, 0)
        END AS inventory_turnover
    FROM with_turnover
),
growth AS (
    SELECT
        name,
        MIN(CASE WHEN fiscal_year = {start_year} THEN revenue END) AS start_rev,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue END) AS end_rev
    FROM metrics
    GROUP BY name
),
joined AS (
    SELECT
        m.name,
        m.fiscal_year,
        m.inventory_turnover,
        g.start_rev,
        g.end_rev
    FROM metrics m
    JOIN growth g USING (name)
),
agg AS (
    SELECT
        name,
        ROUND(
            CASE
                WHEN start_rev IS NULL OR start_rev <= 0 OR end_rev IS NULL THEN NULL
                ELSE (POWER(end_rev / start_rev, 1.0 / NULLIF({end_year} - {start_year}, 0)) - 1) * 100
            END,
            2
        ) AS revenue_cagr_pct,
        ROUND(AVG(inventory_turnover), 2) AS avg_inventory_turnover,
        COUNT(*) AS years_reported
    FROM joined
    WHERE inventory_turnover IS NOT NULL
    GROUP BY name, start_rev, end_rev
)
SELECT
    name,
    revenue_cagr_pct,
    avg_inventory_turnover,
    years_reported
FROM agg
WHERE years_reported >= {min_years}
ORDER BY revenue_cagr_pct DESC, avg_inventory_turnover DESC, name
LIMIT {limit};
