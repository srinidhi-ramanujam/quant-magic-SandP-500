WITH sector_companies AS (
    SELECT cik, name AS display_name
    FROM companies
    WHERE UPPER(gics_sector) = UPPER('{sector}')
),
ranking_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (
            PARTITION BY s.cik, s.fy
            ORDER BY s.filed DESC
        ) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy = {ranking_year}
),
latest_ranking AS (
    SELECT * FROM ranking_filings WHERE rn = 1
),
revenue_ranking AS (
    SELECT
        lr.cik,
        sc.display_name AS name,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                )
                THEN n.value
            END
        ) AS revenue
    FROM latest_ranking lr
    JOIN num n ON n.adsh = lr.adsh AND n.ddate = lr.period
    JOIN sector_companies sc USING (cik)
    WHERE n.tag IN (
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lr.cik, sc.display_name
),
top_companies AS (
    SELECT
        cik,
        name,
        revenue
    FROM revenue_ranking
    WHERE revenue IS NOT NULL
      AND revenue >= {min_revenue}
    ORDER BY revenue DESC
    LIMIT {top_n}
),
quarterly_filings AS (
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
    JOIN top_companies tc USING (cik)
    WHERE s.form IN ('10-Q', '10-Q/A')
      AND s.period BETWEEN COALESCE(TRY_CAST('{start_period}' AS DATE), DATE '{ranking_year}-01-01')
                      AND COALESCE(TRY_CAST('{end_period}' AS DATE), DATE '{ranking_year}-12-31')
),
latest_quarters AS (
    SELECT * FROM quarterly_filings WHERE period_rank = 1
),
quarterly_cfo AS (
    SELECT
        lq.cik,
        tc.name,
        lq.period_end,
        lq.fiscal_year,
        lq.fp,
        MAX(
            CASE
                WHEN n.tag IN (
                    'NetCashProvidedByUsedInOperatingActivities',
                    'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
                )
                AND COALESCE(n.qtrs, 0) = 1
                THEN n.value
            END
        ) AS operating_cfo
    FROM latest_quarters lq
    JOIN num n ON n.adsh = lq.adsh AND n.ddate = lq.period_end
    JOIN top_companies tc USING (cik)
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
    )
      AND COALESCE(TRIM(n.coreg), '') = ''
      AND COALESCE(n.qtrs, 0) = 1
    GROUP BY lq.cik, tc.name, lq.period_end, lq.fiscal_year, lq.fp
),
filtered_cfo AS (
    SELECT
        name,
        period_end,
        fiscal_year,
        fp,
        operating_cfo
    FROM quarterly_cfo
    WHERE operating_cfo IS NOT NULL
      AND ABS(operating_cfo) <= {max_abs_cfo}
),
ranked_cfo AS (
    SELECT
        name,
        period_end,
        fiscal_year,
        fp,
        operating_cfo,
        ROW_NUMBER() OVER (
            PARTITION BY name
            ORDER BY period_end DESC
        ) AS seq
    FROM filtered_cfo
)
SELECT
    name,
    period_end,
    fiscal_year,
    fp AS fiscal_period,
    ROUND(operating_cfo / {value_scale}, 2) AS operating_cfo_scaled
FROM ranked_cfo
WHERE seq <= {min_quarters}
ORDER BY name, period_end DESC
LIMIT {result_limit};

