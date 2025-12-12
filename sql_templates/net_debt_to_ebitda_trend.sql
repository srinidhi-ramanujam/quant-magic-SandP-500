WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT
        c.cik,
        pc.provided_name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies c
    JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') = pc.canonical_name
      OR UPPER(c.name) LIKE '%' || UPPER(pc.provided_name) || '%'
),
sector_companies AS (
    SELECT
        c.cik,
        c.name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies c
    WHERE {use_sector_filter} = 1
      AND (UPPER('{sector}') = 'ALL' OR LOWER(c.gics_sector) LIKE LOWER('%{sector}%'))
),
cohort AS (
    SELECT DISTINCT cik, display_name, canonical_name FROM company_dim
    UNION
    SELECT DISTINCT cik, display_name, canonical_name FROM sector_companies
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
    JOIN cohort cd USING (cik)
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
            WHEN (operating_income + COALESCE(depreciation, 0)) < {min_ebitda} THEN NULL
            ELSE (COALESCE(long_term_debt, 0) + COALESCE(short_term_debt, 0) - COALESCE(cash, 0)) /
                 (operating_income + COALESCE(depreciation, 0))
        END AS net_debt_to_ebitda
    FROM annual_values av
    JOIN cohort cd USING (cik)
)
SELECT
    company,
    fiscal_year,
    ROUND(net_debt / 1000000000.0, 2) AS net_debt_billions,
    ROUND(ebitda / 1000000000.0, 2) AS ebitda_billions,
    ROUND(net_debt_to_ebitda, 2) AS net_debt_to_ebitda
FROM metrics
WHERE net_debt_to_ebitda IS NOT NULL
ORDER BY net_debt_to_ebitda ASC, company, fiscal_year
LIMIT {limit};
