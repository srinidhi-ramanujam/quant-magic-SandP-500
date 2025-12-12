WITH target_company AS (
    SELECT cik, name AS company_name
    FROM companies
    WHERE UPPER(name) LIKE UPPER('%{company}%')
    ORDER BY LENGTH(name)
    LIMIT 1
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
    JOIN target_company tc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
segment_revenue AS (
    SELECT
        tc.company_name AS company,
        lf.fiscal_year,
        COALESCE(NULLIF(TRIM(n.segments), ''), 'Unspecified') AS segment_label,
        SUM(
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
    JOIN target_company tc USING (cik)
    WHERE n.tag IN (
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY tc.company_name, lf.fiscal_year, segment_label
),
pivoted AS (
    SELECT
        company,
        segment_label,
        MAX(CASE WHEN fiscal_year = {start_year} THEN revenue END) AS revenue_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue END) AS revenue_end,
        COUNT(DISTINCT fiscal_year) AS year_count
    FROM segment_revenue
    GROUP BY company, segment_label
    HAVING revenue_start IS NOT NULL AND revenue_end IS NOT NULL
),
scored AS (
    SELECT
        company,
        segment_label,
        revenue_start,
        revenue_end,
        CASE
            WHEN {end_year} = {start_year} THEN NULL
            ELSE POWER(
                revenue_end / NULLIF(revenue_start, 0),
                1.0 / NULLIF({end_year} - {start_year}, 0)
            ) - 1
        END AS revenue_cagr
    FROM pivoted
    WHERE revenue_start > 0 AND revenue_end > 0
)
SELECT
    company,
    segment_label AS segment,
    ROUND(revenue_start / 1000000000.0, 2) AS revenue_{start_year}_billions,
    ROUND(revenue_end / 1000000000.0, 2) AS revenue_{end_year}_billions,
    ROUND(revenue_cagr * 100, 2) AS revenue_cagr_pct
FROM scored
WHERE revenue_cagr IS NOT NULL
ORDER BY revenue_cagr DESC, revenue_end DESC
LIMIT {limit};

