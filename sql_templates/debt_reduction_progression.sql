WITH company_dim AS (
    SELECT
        cik,
        name,
        gics_sector,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE ('{sector}' = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
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
      AND s.fy BETWEEN {start_year} AND {end_year}
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
                    'DebtAndCapitalLeaseObligations'
                ) THEN n.value
            END
        ) AS long_term_debt,
        MAX(
            CASE
                WHEN n.tag IN (
                    'DebtCurrent',
                    'ShortTermBorrowings',
                    'ShortTermDebtAndCurrentPortionOfLongTermDebt'
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
        'DebtAndCapitalLeaseObligations',
        'DebtCurrent',
        'ShortTermBorrowings',
        'ShortTermDebtAndCurrentPortionOfLongTermDebt'
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
agg AS (
    SELECT
        td.cik,
        MAX(CASE WHEN fiscal_year = {start_year} THEN total_debt END) AS debt_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN total_debt END) AS debt_end
    FROM total_debt td
    GROUP BY td.cik
    HAVING debt_start IS NOT NULL AND debt_end IS NOT NULL
),
joined AS (
    SELECT
        ANY_VALUE(cd.name) AS display_name,
        ANY_VALUE(cd.gics_sector) AS gics_sector,
        MIN(a.debt_start) AS debt_start,
        MIN(a.debt_end) AS debt_end,
        MIN(a.debt_start - a.debt_end) AS debt_reduction
    FROM agg a
    JOIN company_dim cd USING (cik)
    GROUP BY cd.cik
)
SELECT
    display_name AS name,
    gics_sector,
    ROUND(debt_start / 1000000000, 2) AS debt_{start_year}_billions,
    ROUND(debt_end / 1000000000, 2) AS debt_{end_year}_billions,
    ROUND(debt_reduction / 1000000000, 2) AS debt_reduction_billions
FROM joined
WHERE debt_reduction >= {min_reduction}
ORDER BY debt_reduction DESC, name
LIMIT {limit};
