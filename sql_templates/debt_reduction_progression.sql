WITH company_dim AS (
    SELECT
        cik,
        name,
        gics_sector,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN 2021 AND 2023
),
latest AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
debt_inputs AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN ('DebtAndCapitalLeaseObligations', 'TotalDebtRecordedUponConsolidation') THEN n.value
            END
        ) AS total_debt_tag,
        MAX(
            CASE
                WHEN n.tag IN (
                    'LongTermDebt',
                    'LongTermDebtNoncurrent',
                    'LongTermDebtAndCapitalLeaseObligations',
                    'LongTermDebtAndCapitalLeaseObligationsNoncurrent',
                    'UnsecuredLongTermDebt',
                    'LongTermDebtOfConsolidatedInvestmentProducts'
                ) THEN n.value
            END
        ) AS long_term_debt,
        MAX(
            CASE
                WHEN n.tag IN (
                    'DebtCurrent',
                    'ShortTermBorrowings',
                    'ShortTermBorrowingsIncludingLongTermDebtCurrent',
                    'ShortTermDebtAndCurrentPortionOfLongTermDebt',
                    'DebtAndCapitalLeaseObligationsCurrent'
                ) THEN n.value
            END
        ) AS short_term_debt
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'DebtAndCapitalLeaseObligations',
        'TotalDebtRecordedUponConsolidation',
        'LongTermDebt',
        'LongTermDebtNoncurrent',
        'LongTermDebtAndCapitalLeaseObligations',
        'LongTermDebtAndCapitalLeaseObligationsNoncurrent',
        'UnsecuredLongTermDebt',
        'LongTermDebtOfConsolidatedInvestmentProducts',
        'DebtCurrent',
        'ShortTermBorrowings',
        'ShortTermBorrowingsIncludingLongTermDebtCurrent',
        'ShortTermDebtAndCurrentPortionOfLongTermDebt',
        'DebtAndCapitalLeaseObligationsCurrent'
    )
    GROUP BY lf.cik, lf.fiscal_year
),
total_debt AS (
    SELECT
        cik,
        fiscal_year,
        COALESCE(total_debt_tag, long_term_debt + COALESCE(short_term_debt, 0), long_term_debt, short_term_debt) AS total_debt
    FROM debt_inputs
),
ranked AS (
    SELECT
        cik,
        MIN(CASE WHEN fiscal_year = 2021 THEN total_debt END) AS debt_2021,
        MIN(CASE WHEN fiscal_year = 2022 THEN total_debt END) AS debt_2022,
        MIN(CASE WHEN fiscal_year = 2023 THEN total_debt END) AS debt_2023
    FROM total_debt
    GROUP BY cik
    HAVING COUNT(DISTINCT fiscal_year) = 3
),
joined AS (
    SELECT
        cd.canonical_name,
        ANY_VALUE(cd.name) AS display_name,
        ANY_VALUE(cd.gics_sector) AS gics_sector,
        debt_2021,
        debt_2022,
        debt_2023,
        debt_2021 - debt_2023 AS debt_reduction
    FROM ranked r
    JOIN company_dim cd USING (cik)
)
SELECT
    display_name AS name,
    gics_sector,
    ROUND(debt_2021 / 1000000000, 2) AS debt_2021_billions,
    ROUND(debt_2022 / 1000000000, 2) AS debt_2022_billions,
    ROUND(debt_2023 / 1000000000, 2) AS debt_2023_billions,
    ROUND(debt_reduction / 1000000000, 2) AS debt_reduction_billions
FROM joined
WHERE debt_reduction > 0
ORDER BY debt_reduction DESC
LIMIT 5;
