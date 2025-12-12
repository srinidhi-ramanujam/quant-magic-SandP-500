WITH provided_companies AS (
    SELECT * FROM (VALUES {company_values}) AS t(company_name)
),
company_dim AS (
    SELECT DISTINCT c.cik, pc.company_name AS display_name
    FROM companies c
    JOIN provided_companies pc ON UPPER(c.name) = UPPER(pc.company_name)
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
                    'InterestExpense',
                    'InterestAndDebtExpense'
                ) THEN n.value
            END
        ) AS interest_expense
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'OperatingIncomeLoss',
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        'InterestExpense',
        'InterestAndDebtExpense'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
metrics AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.operating_income,
        av.interest_expense,
        CASE
            WHEN av.interest_expense IS NULL OR av.interest_expense = 0 THEN NULL
            WHEN av.operating_income IS NULL THEN NULL
            ELSE av.operating_income / av.interest_expense
        END AS interest_coverage
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
summary AS (
    SELECT
        name,
        fiscal_year,
        ROUND(interest_coverage, 2) AS interest_coverage,
        CASE
            WHEN fiscal_year BETWEEN {baseline_start_year} AND {baseline_end_year} THEN 'baseline'
            WHEN fiscal_year BETWEEN {rebuild_start_year} AND {rebuild_end_year} THEN 'rebuild'
            ELSE 'other'
        END AS bucket
    FROM metrics
    WHERE interest_coverage IS NOT NULL
)
SELECT
    name,
    fiscal_year,
    interest_coverage,
    bucket
FROM summary
WHERE bucket <> 'other'
ORDER BY name, fiscal_year
LIMIT {limit};
