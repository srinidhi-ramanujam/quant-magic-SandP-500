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
cohort AS (
    SELECT
        sc.company,
        ar.fiscal_year,
        ar.revenue
    FROM annual_revenue ar
    JOIN sector_companies sc USING (cik)
),
paired AS (
    SELECT
        company,
        MAX(CASE WHEN fiscal_year = {start_year} THEN revenue END) AS revenue_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue END) AS revenue_end,
        COUNT(DISTINCT fiscal_year) AS year_count
    FROM cohort
    GROUP BY company
    HAVING revenue_start IS NOT NULL
       AND revenue_end IS NOT NULL
       AND revenue_start >= {min_revenue}
       AND year_count >= {min_years}
),
ranked AS (
    SELECT
        company,
        revenue_start,
        revenue_end,
        CASE
            WHEN {end_year} = {start_year} THEN NULL
            ELSE POWER(
                revenue_end / NULLIF(revenue_start, 0),
                1.0 / NULLIF({end_year} - {start_year}, 0)
            ) - 1
        END AS revenue_cagr
    FROM paired
    WHERE revenue_start > 0 AND revenue_end > 0
)
SELECT
    company,
    ROUND(revenue_start / 1000000000.0, 2) AS revenue_{start_year}_billions,
    ROUND(revenue_end / 1000000000.0, 2) AS revenue_{end_year}_billions,
    ROUND(revenue_cagr * 100, 2) AS revenue_cagr_pct
FROM ranked
WHERE revenue_cagr IS NOT NULL
ORDER BY revenue_cagr DESC, revenue_end DESC
LIMIT {limit};

