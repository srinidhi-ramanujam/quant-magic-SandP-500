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
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest AS (
    SELECT *
    FROM annual_filings
    WHERE rn = 1
),
vals AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'AssetsCurrent' THEN n.value END) AS assets_current,
        MAX(CASE WHEN n.tag = 'LiabilitiesCurrent' THEN n.value END) AS liabilities_current,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                )
                THEN n.value
            END
        ) AS revenue,
        MAX(CASE WHEN n.tag IN ('InventoryNet', 'Inventory') THEN n.value END) AS inventory,
        MAX(
            CASE
                WHEN n.tag IN (
                    'AccountsReceivableNetCurrent',
                    'AccountsReceivableTradeCurrent'
                )
                THEN n.value
            END
        ) AS ar,
        MAX(
            CASE
                WHEN n.tag IN ('CostOfGoodsAndServicesSold', 'CostOfRevenue') THEN n.value
            END
        ) AS cost_of_revenue,
        MAX(
            CASE
                WHEN n.tag IN (
                    'AccountsPayableCurrent',
                    'AccountsPayableTradeCurrent'
                )
                THEN n.value
            END
        ) AS ap
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'AssetsCurrent',
        'LiabilitiesCurrent',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',
        'InventoryNet',
        'Inventory',
        'AccountsReceivableNetCurrent',
        'AccountsReceivableTradeCurrent',
        'CostOfGoodsAndServicesSold',
        'CostOfRevenue',
        'AccountsPayableCurrent',
        'AccountsPayableTradeCurrent'
    )
    GROUP BY lf.cik, lf.fiscal_year
),
computed AS (
    SELECT
        v.cik,
        v.fiscal_year,
        (assets_current - liabilities_current) / NULLIF(revenue, 0) * 365 AS wc_days,
        inventory / NULLIF(cost_of_revenue, 0) * 365 AS dio,
        ar / NULLIF(revenue, 0) * 365 AS dso,
        ap / NULLIF(cost_of_revenue, 0) * 365 AS dpo
    FROM vals v
),
agg AS (
    SELECT
        sc.canonical_name,
        ANY_VALUE(sc.name) AS name,
        MAX(CASE WHEN fiscal_year = {start_year} THEN wc_days END) AS wc_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN wc_days END) AS wc_end,
        MAX(CASE WHEN fiscal_year = {start_year} THEN (dio + dso - dpo) END) AS ccc_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN (dio + dso - dpo) END) AS ccc_end
    FROM computed c
    JOIN sector_companies sc USING (cik)
    GROUP BY sc.canonical_name
    HAVING COUNT(
        DISTINCT CASE
            WHEN fiscal_year IN ({start_year}, {end_year}) THEN fiscal_year
        END
    ) = 2
)
SELECT
    name,
    ROUND(wc_start, 2) AS wc_{start_year}_days,
    ROUND(wc_end, 2) AS wc_{end_year}_days,
    ROUND(wc_end - wc_start, 2) AS wc_change_days,
    ROUND(ccc_start, 2) AS ccc_{start_year}_days,
    ROUND(ccc_end, 2) AS ccc_{end_year}_days,
    ROUND(ccc_end - ccc_start, 2) AS ccc_change_days
FROM agg
WHERE wc_start IS NOT NULL
  AND wc_end IS NOT NULL
ORDER BY wc_change_days
LIMIT {limit};
