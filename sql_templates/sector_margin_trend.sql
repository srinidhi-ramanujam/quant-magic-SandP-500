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
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'OperatingIncomeLoss',
                    'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments'
                ) THEN n.value
            END
        ) AS operating_income,
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
        'OperatingIncomeLoss',
        'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
margin_series AS (
    SELECT
        sc.company,
        av.fiscal_year,
        av.operating_income,
        av.revenue,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            ELSE av.operating_income / av.revenue
        END AS operating_margin
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
    WHERE av.revenue IS NOT NULL
      AND av.revenue >= {min_revenue}
),
aggregated AS (
    SELECT
        company,
        COUNT(*) AS year_count,
        MAX(CASE WHEN fiscal_year = {end_year} THEN operating_margin END) AS margin_latest,
        MAX(CASE WHEN fiscal_year = {end_year} - 1 THEN operating_margin END) AS margin_prev1,
        MAX(CASE WHEN fiscal_year = {end_year} - 2 THEN operating_margin END) AS margin_prev2,
        MAX(CASE WHEN fiscal_year = {end_year} - 3 THEN operating_margin END) AS margin_prev3,
        AVG(operating_margin) AS avg_margin
    FROM margin_series
    WHERE operating_margin IS NOT NULL
    GROUP BY company
    HAVING year_count >= {min_years}
       AND margin_latest IS NOT NULL
)
SELECT
    company,
    ROUND(margin_prev3 * 100, 2) AS margin_start_pct,
    ROUND(margin_prev2 * 100, 2) AS margin_mid_pct,
    ROUND(margin_prev1 * 100, 2) AS margin_prev_pct,
    ROUND(margin_latest * 100, 2) AS margin_latest_pct,
    ROUND(avg_margin * 100, 2) AS avg_margin_pct
FROM aggregated
ORDER BY margin_latest DESC, avg_margin DESC
LIMIT {limit};

