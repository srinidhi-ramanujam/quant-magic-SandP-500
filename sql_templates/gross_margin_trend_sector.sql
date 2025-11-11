WITH sector_companies AS (
    SELECT
        cik,
        name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
ranked_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K','10-K/A','20-F')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
annual_filings AS (
    SELECT adsh, cik, fiscal_year, period
    FROM ranked_filings
    WHERE rn = 1
),
values AS (
    SELECT
        f.cik,
        f.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet',
                    'NetSalesRevenue',
                    'NetSales'
                ) THEN n.value
            END
        ) AS revenue,
        MAX(
            CASE
                WHEN n.tag IN (
                    'CostOfRevenue',
                    'CostOfGoodsAndServicesSold',
                    'CostOfGoodsSold'
                ) THEN n.value
            END
        ) AS cost_of_revenue,
        MAX(CASE WHEN n.tag = 'GrossProfit' THEN n.value END) AS gross_profit
    FROM annual_filings f
    JOIN num n ON n.adsh = f.adsh AND n.ddate = f.period
    WHERE n.tag IN (
        'GrossProfit',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',
        'NetSalesRevenue',
        'NetSales',
        'CostOfRevenue',
        'CostOfGoodsAndServicesSold',
        'CostOfGoodsSold'
    )
    GROUP BY f.cik, f.fiscal_year
),
margins AS (
    SELECT
        sc.canonical_name,
        sc.name AS display_name,
        v.fiscal_year,
        ROUND(
            100 * COALESCE(v.gross_profit, v.revenue - v.cost_of_revenue)
            / NULLIF(v.revenue, 0),
            1
        ) AS gross_margin_pct,
        v.revenue
    FROM values v
    JOIN sector_companies sc USING (cik)
    WHERE v.revenue IS NOT NULL
      AND v.cost_of_revenue IS NOT NULL
),
pivoted AS (
    SELECT
        canonical_name,
        ANY_VALUE(display_name) AS name,
        MAX(CASE WHEN fiscal_year = {start_year} THEN gross_margin_pct END) AS margin_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN gross_margin_pct END) AS margin_end,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue END) AS revenue_end
    FROM margins
    GROUP BY canonical_name
    HAVING COUNT(DISTINCT CASE WHEN fiscal_year IN ({start_year}, {end_year}) THEN fiscal_year END) = 2
)
SELECT
    name,
    ROUND(margin_start, 1) AS margin_{start_year}_pct,
    ROUND(margin_end, 1) AS margin_{end_year}_pct,
    ROUND(margin_end - margin_start, 1) AS change_pp,
    ROUND(revenue_end / 1000000000.0, 2) AS revenue_{end_year}_billions
FROM pivoted
WHERE revenue_end >= {min_revenue}
ORDER BY change_pp DESC, name
LIMIT {limit};
