WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
cohort_companies AS (
    SELECT
        cik,
        name,
        gics_sector,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (
        LOWER(gics_sector) LIKE LOWER('%{sector_a}%')
        OR LOWER(gics_sector) LIKE LOWER('%{sector_b}%')
    )
    OR REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') IN (SELECT canonical_name FROM provided_companies)
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN cohort_companies cc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy = {fiscal_year}
),
latest AS (
    SELECT *
    FROM annual_filings
    WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        MAX(CASE WHEN n.tag = 'Liabilities' THEN n.value END) AS liabilities,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                ) THEN n.value
            END
        ) AS equity,
        MAX(CASE WHEN n.tag = 'OperatingIncomeLoss' THEN n.value END) AS operating_income,
        MAX(
            CASE
                WHEN n.tag IN ('InterestExpense', 'InterestExpenseDebt', 'InterestAndDebtExpense') THEN n.value
            END
        ) AS interest_expense,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Liabilities',
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        'OperatingIncomeLoss',
        'InterestExpense',
        'InterestExpenseDebt',
        'InterestAndDebtExpense',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik
),
scored AS (
    SELECT
        cc.canonical_name,
        cc.name AS company,
        cc.gics_sector AS sector,
        CASE
            WHEN av.equity IS NULL OR av.equity = 0 THEN NULL
            ELSE av.liabilities / av.equity
        END AS debt_to_equity,
        CASE
            WHEN av.interest_expense IS NULL OR av.interest_expense = 0 THEN NULL
            ELSE av.operating_income / av.interest_expense
        END AS interest_coverage,
        av.revenue
    FROM annual_values av
    JOIN cohort_companies cc USING (cik)
)
SELECT
    company AS name,
    sector,
    ROUND(debt_to_equity, 2) AS debt_to_equity,
    ROUND(interest_coverage, 2) AS interest_coverage,
    ROUND(revenue / 1000000000.0, 2) AS revenue_billions
FROM scored
WHERE revenue IS NOT NULL
  AND revenue >= {min_revenue}
  AND debt_to_equity IS NOT NULL
  AND interest_coverage IS NOT NULL
  AND interest_coverage >= {min_interest_coverage}
  AND debt_to_equity <= {max_debt_to_equity}
ORDER BY interest_coverage DESC, debt_to_equity ASC, revenue DESC
LIMIT {limit};
