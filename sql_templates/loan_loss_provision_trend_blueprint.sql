WITH quarterly_provision AS (
    SELECT
        s.cik,
        s.period,
        s.fy AS fiscal_year,
        s.fp AS fiscal_period,
        n.value AS loan_loss_provision
    FROM sub s
    JOIN num n ON n.adsh = s.adsh AND n.ddate = s.period
    WHERE s.form IN ('10-Q','10-Q/A')
      AND s.period BETWEEN DATE '{start_date}' AND DATE '{end_date}'
      AND n.tag IN (
          'ProvisionForLoanAndLeaseLosses',
          'ProvisionForLoanLossesExpensed',
          'ProvisionForLoanAndLeaseLossesNonAcquisition'
      )
      AND COALESCE(n.qtrs, 0) = 1
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
      -- Optional company filter list: s.cik IN ({company_list})
)
SELECT
    qp.cik,
    qp.period,
    qp.fiscal_year,
    qp.fiscal_period,
    qp.loan_loss_provision
FROM quarterly_provision qp
ORDER BY qp.cik, qp.period;

