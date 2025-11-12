WITH provided_companies AS (
    SELECT *
    FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT c.cik, pc.company_name AS display_name
    FROM companies c
    JOIN provided_companies pc
      ON UPPER(c.name) = UPPER(pc.company_name)
),
ranked_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag IN (
            'LongTermDebt',
            'LongTermDebtNoncurrent',
            'LongTermDebtAndCapitalLeaseObligations'
        ) THEN n.value END) AS long_term_debt,
        MAX(CASE WHEN n.tag IN (
            'DebtCurrent',
            'ShortTermBorrowings',
            'ShortTermDebtAndCurrentPortionOfLongTermDebt',
            'CurrentPortionOfLongTermDebt'
        ) THEN n.value END) AS short_term_debt,
        MAX(CASE WHEN n.tag IN (
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsAndShortTermInvestments'
        ) THEN n.value END) AS cash,
        MAX(CASE WHEN n.tag IN (
            'OperatingIncomeLoss',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest'
        ) THEN n.value END) AS operating_income,
        MAX(CASE WHEN n.tag IN (
            'DepreciationDepletionAndAmortization',
            'DepreciationAndAmortization',
            'DepreciationAmortizationAndAccretionNet'
        ) THEN n.value END) AS depreciation
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'LongTermDebt','LongTermDebtNoncurrent','LongTermDebtAndCapitalLeaseObligations',
        'DebtCurrent','ShortTermBorrowings','ShortTermDebtAndCurrentPortionOfLongTermDebt','CurrentPortionOfLongTermDebt',
        'CashAndCashEquivalentsAtCarryingValue','CashCashEquivalentsAndShortTermInvestments',
        'OperatingIncomeLoss','IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        'DepreciationDepletionAndAmortization','DepreciationAndAmortization','DepreciationAmortizationAndAccretionNet'
    )
      AND COALESCE(TRIM(n.segments),'') = ''
      AND COALESCE(TRIM(n.coreg),'') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
metrics AS (
    SELECT
        cd.display_name AS company,
        av.fiscal_year,
        (COALESCE(long_term_debt, 0) + COALESCE(short_term_debt, 0)) AS gross_debt,
        COALESCE(cash, 0) AS cash,
        (COALESCE(long_term_debt, 0) + COALESCE(short_term_debt, 0) - COALESCE(cash, 0)) AS net_debt,
        operating_income,
        depreciation,
        operating_income + COALESCE(depreciation, 0) AS ebitda,
        CASE
            WHEN operating_income IS NULL OR depreciation IS NULL THEN NULL
            WHEN (operating_income + COALESCE(depreciation, 0)) <= 0 THEN NULL
            WHEN ABS(operating_income + COALESCE(depreciation, 0)) < 100000000 THEN NULL
            ELSE (COALESCE(long_term_debt, 0) + COALESCE(short_term_debt, 0) - COALESCE(cash, 0)) /
                 (operating_income + COALESCE(depreciation, 0))
        END AS net_debt_to_ebitda
    FROM annual_values av
    JOIN company_dim cd USING (cik)
)
SELECT
    company,
    fiscal_year,
    ROUND(net_debt / 1000000000.0, 2) AS net_debt_billions,
    ROUND(ebitda / 1000000000.0, 2) AS ebitda_billions,
    ROUND(net_debt_to_ebitda, 2) AS net_debt_to_ebitda
FROM metrics
ORDER BY company, fiscal_year;
