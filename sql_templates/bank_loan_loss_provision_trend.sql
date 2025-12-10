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
        s.period,
        s.filed,
        s.form,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.period ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-Q','10-Q/A')
      AND s.period BETWEEN '{start_period}' AND '{end_period}'
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
quarterly_values AS (
    SELECT
        lf.cik,
        lf.period,
        MAX(
            CASE
                WHEN n.tag IN (
                    'ProvisionForLoanLeaseAndLosses',
                    'ProvisionForLoanLosses'
                ) THEN n.value
            END
        ) AS loan_loss_provision
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'ProvisionForLoanLeaseAndLosses',
        'ProvisionForLoanLosses'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.period
),
ordered AS (
    SELECT
        cd.display_name AS name,
        qv.period,
        qv.loan_loss_provision
    FROM quarterly_values qv
    JOIN company_dim cd USING (cik)
    WHERE qv.loan_loss_provision IS NOT NULL
)
SELECT
    name,
    period,
    ROUND(loan_loss_provision / 1000000000.0, 3) AS loan_loss_provision_billions
FROM ordered
ORDER BY name, period
LIMIT {limit};
