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
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) AS net_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                ) THEN n.value
            END
        ) AS equity,
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
        'NetIncomeLoss',
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
    GROUP BY lf.cik, lf.fiscal_year
),
agg AS (
    SELECT
        sc.canonical_name,
        ANY_VALUE(sc.name) AS display_name,
        MAX(CASE WHEN v.fiscal_year = {start_year} THEN v.net_income / NULLIF(v.equity, 0) END) AS roe_start,
        MAX(CASE WHEN v.fiscal_year = {end_year} THEN v.net_income / NULLIF(v.equity, 0) END) AS roe_end,
        MAX(CASE WHEN v.fiscal_year = {start_year} THEN v.revenue END) AS revenue_start,
        MAX(CASE WHEN v.fiscal_year = {end_year} THEN v.revenue END) AS revenue_end
    FROM values v
    JOIN sector_companies sc USING (cik)
    GROUP BY sc.canonical_name
    HAVING COUNT(DISTINCT CASE WHEN v.fiscal_year IN ({start_year}, {end_year}) THEN v.fiscal_year END) = 2
)
SELECT
    display_name AS name,
    ROUND(roe_start * 100, 2) AS roe_{start_year}_pct,
    ROUND(roe_end * 100, 2) AS roe_{end_year}_pct,
    ROUND((roe_end - roe_start) * 100, 2) AS roe_change_pp,
    ROUND(((revenue_end - revenue_start) / NULLIF(revenue_start, 0)) * 100, 2) AS revenue_growth_pct
FROM agg
WHERE revenue_end > revenue_start
  AND roe_end < roe_start
  AND ((revenue_end - revenue_start) / NULLIF(revenue_start, 0)) * 100 >= {min_growth_pct}
ORDER BY roe_change_pp ASC
LIMIT {limit};
