WITH sector_companies AS (
    SELECT cik, name AS company
    FROM companies
    WHERE '{sector}' = 'ALL' OR UPPER(gics_sector) LIKE UPPER('%{sector}%')
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
annual_revenue AS (
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
        ) AS revenue
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
company_revenue AS (
    SELECT
        sc.company,
        ar.fiscal_year,
        ar.revenue
    FROM annual_revenue ar
    JOIN sector_companies sc USING (cik)
    WHERE ar.revenue IS NOT NULL
),
sector_totals AS (
    SELECT
        fiscal_year,
        SUM(revenue) AS sector_revenue
    FROM company_revenue
    GROUP BY fiscal_year
),
with_share AS (
    SELECT
        cr.company,
        cr.fiscal_year,
        cr.revenue,
        st.sector_revenue,
        CASE
            WHEN st.sector_revenue = 0 THEN NULL
            ELSE cr.revenue / st.sector_revenue
        END AS revenue_share
    FROM company_revenue cr
    JOIN sector_totals st USING (fiscal_year)
),
paired AS (
    SELECT
        company,
        COUNT(*) AS year_count,
        MAX(CASE WHEN fiscal_year = {start_year} THEN revenue_share END) AS share_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue_share END) AS share_end,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue END) AS revenue_end
    FROM with_share
    GROUP BY company
    HAVING share_start IS NOT NULL
       AND share_end IS NOT NULL
       AND revenue_end >= {min_revenue}
),
scored AS (
    SELECT
        company,
        year_count,
        share_start,
        share_end,
        (share_end - share_start) AS share_gain
    FROM paired
)
SELECT
    company,
    ROUND(share_start * 100, 2) AS share_start_pct,
    ROUND(share_end * 100, 2) AS share_end_pct,
    ROUND(share_gain * 100, 2) AS share_gain_pp
FROM scored
ORDER BY share_gain DESC, share_end DESC
LIMIT {limit};

