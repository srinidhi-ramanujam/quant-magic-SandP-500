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
                    'LongTermDebt',
                    'LongTermDebtNoncurrent',
                    'LongTermDebtAndCapitalLeaseObligations'
                ) THEN n.value
            END
        ) AS long_term_debt,
        MAX(
            CASE
                WHEN n.tag IN (
                    'DebtCurrent',
                    'ShortTermBorrowings',
                    'ShortTermDebtAndCurrentPortionOfLongTermDebt',
                    'CurrentPortionOfLongTermDebt'
                ) THEN n.value
            END
        ) AS short_term_debt,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
                    'StockholdersEquityAttributableToParent'
                ) THEN n.value
            END
        ) AS equity,
        MAX(
            CASE
                WHEN n.tag IN (
                    'CashAndCashEquivalentsAtCarryingValue',
                    'CashCashEquivalentsAndShortTermInvestments'
                ) THEN n.value
            END
        ) AS cash,
        MAX(
            CASE
                WHEN n.tag IN (
                    'OperatingIncomeLoss',
                    'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest'
                ) THEN n.value
            END
        ) AS operating_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'DepreciationDepletionAndAmortization',
                    'DepreciationAndAmortization',
                    'DepreciationAmortizationAndAccretionNet'
                ) THEN n.value
            END
        ) AS depreciation
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'LongTermDebt',
        'LongTermDebtNoncurrent',
        'LongTermDebtAndCapitalLeaseObligations',
        'DebtCurrent',
        'ShortTermBorrowings',
        'ShortTermDebtAndCurrentPortionOfLongTermDebt',
        'CurrentPortionOfLongTermDebt',
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        'StockholdersEquityAttributableToParent',
        'CashAndCashEquivalentsAtCarryingValue',
        'CashCashEquivalentsAndShortTermInvestments',
        'OperatingIncomeLoss',
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        'DepreciationDepletionAndAmortization',
        'DepreciationAndAmortization',
        'DepreciationAmortizationAndAccretionNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
metrics AS (
    SELECT
        tc.company_name AS company,
        av.fiscal_year,
        COALESCE(av.long_term_debt, 0) + COALESCE(av.short_term_debt, 0) AS gross_debt,
        COALESCE(av.cash, 0) AS cash_balance,
        COALESCE(av.long_term_debt, 0) + COALESCE(av.short_term_debt, 0) - COALESCE(av.cash, 0) AS net_debt,
        av.equity,
        CASE
            WHEN av.equity IS NULL OR av.equity = 0 THEN NULL
            ELSE (COALESCE(av.long_term_debt, 0) + COALESCE(av.short_term_debt, 0)) / av.equity
        END AS debt_to_equity,
        av.operating_income,
        av.depreciation,
        av.operating_income + COALESCE(av.depreciation, 0) AS ebitda,
        CASE
            WHEN (av.operating_income + COALESCE(av.depreciation, 0)) <= 0 THEN NULL
            ELSE (COALESCE(av.long_term_debt, 0) + COALESCE(av.short_term_debt, 0) - COALESCE(av.cash, 0)) /
                 NULLIF(av.operating_income + COALESCE(av.depreciation, 0), 0)
        END AS net_debt_to_ebitda
    FROM annual_values av
    JOIN target_company tc USING (cik)
)
SELECT
    company,
    fiscal_year,
    ROUND(gross_debt / 1000000000.0, 2) AS gross_debt_billions,
    ROUND(net_debt / 1000000000.0, 2) AS net_debt_billions,
    ROUND(cash_balance / 1000000000.0, 2) AS cash_billions,
    ROUND(debt_to_equity, 2) AS debt_to_equity,
    ROUND(net_debt_to_ebitda, 2) AS net_debt_to_ebitda
FROM metrics
ORDER BY fiscal_year DESC;

