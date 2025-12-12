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
        MAX(CASE WHEN n.tag = 'InventoryNet' THEN n.value END) AS inventory,
        MAX(CASE WHEN n.tag = 'AccountsReceivableNetCurrent' THEN n.value END) AS receivables,
        MAX(CASE WHEN n.tag = 'AccountsPayableCurrent' THEN n.value END) AS payables
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet',
        'CostOfRevenue','CostOfGoodsSold','CostOfGoodsAndServicesSold',
        'InventoryNet','AccountsReceivableNetCurrent','AccountsPayableCurrent'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
with_turns AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.revenue,
        av.cogs,
        av.inventory,
        av.receivables,
        av.payables,
        AVG(av.inventory) OVER (PARTITION BY cd.cik ORDER BY av.fiscal_year ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS avg_inventory,
        AVG(av.receivables) OVER (PARTITION BY cd.cik ORDER BY av.fiscal_year ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS avg_receivables,
        AVG(av.payables) OVER (PARTITION BY cd.cik ORDER BY av.fiscal_year ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS avg_payables
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
metrics AS (
    SELECT
        name,
        fiscal_year,
        CASE WHEN avg_inventory IS NULL OR cogs IS NULL OR cogs = 0 THEN NULL ELSE cogs / NULLIF(avg_inventory, 0) END AS inventory_turnover,
        CASE WHEN avg_inventory IS NULL OR cogs IS NULL OR cogs = 0 THEN NULL ELSE (avg_inventory / NULLIF(cogs, 0)) * 365 END AS days_inventory,
        CASE WHEN avg_receivables IS NULL OR revenue IS NULL OR revenue = 0 THEN NULL ELSE (avg_receivables / NULLIF(revenue, 0)) * 365 END AS days_sales,
        CASE WHEN avg_payables IS NULL OR cogs IS NULL OR cogs = 0 THEN NULL ELSE (avg_payables / NULLIF(cogs, 0)) * 365 END AS days_payable
    FROM with_turns
    WHERE revenue IS NOT NULL AND cogs IS NOT NULL
),
ccc AS (
    SELECT
        name,
        fiscal_year,
        inventory_turnover,
        days_inventory,
        days_sales,
        days_payable,
        CASE
            WHEN days_inventory IS NULL OR days_sales IS NULL OR days_payable IS NULL THEN NULL
            ELSE days_inventory + days_sales - days_payable
        END AS cash_conversion_cycle
    FROM metrics
),
bucketed AS (
    SELECT
        name,
        fiscal_year,
        inventory_turnover,
        cash_conversion_cycle,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'pre'
            WHEN fiscal_year BETWEEN {lockdown_start_year} AND {lockdown_end_year} THEN 'lockdown'
            WHEN fiscal_year BETWEEN {recovery_start_year} AND {recovery_end_year} THEN 'recovery'
            ELSE 'other'
        END AS bucket
    FROM ccc
    WHERE cash_conversion_cycle IS NOT NULL
)
SELECT
    name,
    bucket,
    ROUND(AVG(inventory_turnover), 2) AS avg_inventory_turnover,
    ROUND(AVG(cash_conversion_cycle), 2) AS avg_cash_conversion_cycle_days,
    COUNT(*) AS periods
FROM bucketed
WHERE bucket IN ('pre','lockdown','recovery')
GROUP BY name, bucket
HAVING COUNT(*) >= {min_periods_per_bucket}
ORDER BY name, bucket;
