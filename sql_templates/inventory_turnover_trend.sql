WITH provided_companies AS (
    SELECT *
    FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT
        c.cik,
        pc.company_name AS requested_name,
        c.name AS dataset_name
    FROM companies c
    JOIN provided_companies pc
      ON UPPER(c.name) = UPPER(pc.company_name)
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
latest_filings AS (
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
filtered_filings AS (
    SELECT *
    FROM latest_filings
    WHERE seq <= {quarter_count}
),
quarter_values AS (
    SELECT
        f.cik,
        f.period_end,
        f.fiscal_year,
        f.fp,
        MAX(
            CASE
                WHEN n.tag IN ('InventoryNet', 'Inventory', 'InventoryCurrent')
                     AND COALESCE(n.qtrs, 0) = 0
                THEN n.value
            END
        ) AS inventory,
        MAX(
            CASE
                WHEN n.tag IN ('CostOfRevenue', 'CostOfGoodsSold', 'CostOfGoodsAndServicesSold')
                     AND COALESCE(n.qtrs, 0) = 1
                THEN n.value
            END
        ) AS cost_of_revenue
    FROM filtered_filings f
    JOIN num n
      ON n.adsh = f.adsh
     AND n.ddate = f.period_end
    WHERE n.tag IN (
        'InventoryNet',
        'Inventory',
        'InventoryCurrent',
        'CostOfRevenue',
        'CostOfGoodsSold',
        'CostOfGoodsAndServicesSold'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY f.cik, f.period_end, f.fiscal_year, f.fp
),
metrics AS (
    SELECT
        cd.requested_name AS company,
        CAST(q.period_end AS DATE) AS period_end,
        q.fiscal_year,
        q.fp,
        q.inventory,
        q.cost_of_revenue,
        ROUND((q.cost_of_revenue * 4) / NULLIF(q.inventory, 0), 2) AS inventory_turnover,
        ROUND((q.inventory / NULLIF(q.cost_of_revenue, 0)) * 365, 0) AS days_inventory_outstanding,
        ROW_NUMBER() OVER (
            PARTITION BY cd.requested_name
            ORDER BY q.period_end DESC
        ) AS seq
    FROM quarter_values q
    JOIN company_dim cd USING (cik)
    WHERE q.inventory IS NOT NULL
      AND q.cost_of_revenue IS NOT NULL
),
summary AS (
    SELECT
        company,
        MAX(CASE WHEN seq = 1 THEN inventory_turnover END) AS latest_turnover,
        MAX(CASE WHEN seq = 1 THEN days_inventory_outstanding END) AS latest_dio,
        MAX(CASE WHEN seq = 1 THEN period_end END) AS latest_period,
        MAX(CASE WHEN seq = {quarter_count} THEN inventory_turnover END) AS start_turnover,
        MAX(CASE WHEN seq = {quarter_count} THEN days_inventory_outstanding END) AS start_dio,
        MAX(CASE WHEN seq = {quarter_count} THEN period_end END) AS start_period
    FROM metrics
    GROUP BY company
)
SELECT
    company,
    latest_period AS latest_period_end,
    start_period AS baseline_period_end,
    latest_turnover,
    start_turnover,
    ROUND(latest_turnover - start_turnover, 2) AS turnover_change,
    latest_dio,
    start_dio,
    ROUND(latest_dio - start_dio, 0) AS dio_change
FROM summary
ORDER BY turnover_change DESC, company;
