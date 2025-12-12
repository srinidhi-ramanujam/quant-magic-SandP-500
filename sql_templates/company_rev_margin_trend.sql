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
                    'OperatingIncomeLoss',
                    'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments'
                ) THEN n.value
            END
        ) AS operating_income
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',
        'OperatingIncomeLoss',
        'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
metrics AS (
    SELECT
        tc.company_name AS company,
        av.fiscal_year,
        av.revenue,
        av.operating_income,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            ELSE av.operating_income / av.revenue
        END AS operating_margin
    FROM annual_values av
    JOIN target_company tc USING (cik)
)
SELECT
    company,
    fiscal_year,
    ROUND(revenue / 1000000000.0, 2) AS revenue_billions,
    ROUND(operating_margin * 100, 2) AS operating_margin_pct
FROM metrics
WHERE revenue IS NOT NULL
ORDER BY fiscal_year DESC;

