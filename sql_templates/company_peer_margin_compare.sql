WITH target_company AS (
    SELECT cik, name AS company_name, gics_sector
    FROM companies
    WHERE UPPER(name) LIKE UPPER('%{company}%')
    ORDER BY LENGTH(name)
    LIMIT 1
),
peer_companies AS (
    SELECT cik, name AS company
    FROM companies
    WHERE gics_sector = (SELECT gics_sector FROM target_company)
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
    JOIN peer_companies pc USING (cik)
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
        pc.company,
        av.fiscal_year,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            ELSE av.operating_income / av.revenue
        END AS operating_margin
    FROM annual_values av
    JOIN peer_companies pc USING (cik)
    WHERE av.revenue IS NOT NULL
),
peer_aggregate AS (
    SELECT
        fiscal_year,
        MEDIAN(operating_margin) AS peer_median_margin
    FROM margin_series
    GROUP BY fiscal_year
),
company_trend AS (
    SELECT
        ms.fiscal_year,
        ms.operating_margin
    FROM margin_series ms
    JOIN target_company tc ON ms.company = tc.company_name
),
comparison AS (
    SELECT
        ct.fiscal_year,
        ct.operating_margin AS company_margin,
        pa.peer_median_margin
    FROM company_trend ct
    JOIN peer_aggregate pa USING (fiscal_year)
    WHERE ct.operating_margin IS NOT NULL
      AND pa.peer_median_margin IS NOT NULL
),
summary AS (
    SELECT
        AVG(company_margin) AS avg_company_margin,
        AVG(peer_median_margin) AS avg_peer_margin
    FROM comparison
)
SELECT
    tc.company_name AS company,
    tc.gics_sector AS sector,
    ROUND(s.avg_company_margin * 100, 2) AS company_margin_pct,
    ROUND(s.avg_peer_margin * 100, 2) AS peer_median_margin_pct,
    ROUND((s.avg_company_margin - s.avg_peer_margin) * 100, 2) AS margin_delta_pp
FROM summary s
CROSS JOIN target_company tc;

