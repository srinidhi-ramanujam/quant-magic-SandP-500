WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
sector_a_companies AS (
    SELECT cik, name, gics_sector FROM companies WHERE LOWER(gics_sector) LIKE LOWER('%{sector_a}%')
),
sector_b_companies AS (
    SELECT cik, name, gics_sector FROM companies WHERE LOWER(gics_sector) LIKE LOWER('%{sector_b}%')
),
list_companies AS (
    SELECT
        c.cik,
        c.name,
        c.gics_sector
    FROM companies c
    JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') = pc.canonical_name
),
company_dim AS (
    SELECT * FROM list_companies
    UNION ALL
    SELECT * FROM sector_a_companies
    UNION ALL
    SELECT * FROM sector_b_companies
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
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
        MAX(CASE WHEN n.tag = 'AssetsCurrent' THEN n.value END) AS assets_current,
        MAX(CASE WHEN n.tag = 'LiabilitiesCurrent' THEN n.value END) AS liabilities_current,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue,
        MAX(CASE WHEN n.tag IN ('InventoryNet', 'Inventory') THEN n.value END) AS inventory,
        MAX(
            CASE
                WHEN n.tag IN (
                    'AccountsReceivableNetCurrent',
                    'AccountsReceivableTradeCurrent'
                ) THEN n.value
            END
        ) AS ar,
        MAX(
            CASE
                WHEN n.tag IN ('CostOfGoodsAndServicesSold', 'CostOfRevenue') THEN n.value
            END
        ) AS cogs,
        MAX(
            CASE
                WHEN n.tag IN (
                    'AccountsPayableCurrent',
                    'AccountsPayableTradeCurrent'
                ) THEN n.value
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
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
metrics AS (
    SELECT
        av.fiscal_year,
        CASE WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL ELSE av.ar / av.revenue * 365 END AS dso,
        CASE WHEN av.cogs IS NULL OR av.cogs = 0 THEN NULL ELSE av.inventory / av.cogs * 365 END AS dio,
        CASE WHEN av.cogs IS NULL OR av.cogs = 0 THEN NULL ELSE av.ap / av.cogs * 365 END AS dpo,
        CASE WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL ELSE (av.assets_current - av.liabilities_current) / av.revenue * 365 END AS wc_days,
        CASE
            WHEN cd.gics_sector IS NOT NULL AND LOWER(cd.gics_sector) LIKE LOWER('%{sector_a}%') THEN 'A'
            WHEN cd.gics_sector IS NOT NULL AND LOWER(cd.gics_sector) LIKE LOWER('%{sector_b}%') THEN 'B'
            ELSE 'Provided'
        END AS sector_group
    FROM annual_values av
    JOIN company_dim cd USING (cik)
)
SELECT
    sector_group,
    ROUND(AVG(dso), 2) AS avg_dso_days,
    ROUND(AVG(dio), 2) AS avg_dio_days,
    ROUND(AVG(dpo), 2) AS avg_dpo_days,
    ROUND(AVG(wc_days), 2) AS avg_wc_days
FROM metrics
WHERE sector_group IN ('A', 'B')
  AND metrics.fiscal_year BETWEEN {start_year} AND {end_year}
GROUP BY sector_group
ORDER BY sector_group;
