WITH quarterly_cfo AS (
    SELECT
        s.cik,
        s.period,
        s.fy AS fiscal_year,
        s.fp AS fiscal_period,
        n.value AS operating_cash_flow
    FROM sub s
    JOIN num n ON n.adsh = s.adsh AND n.ddate = s.period
    WHERE s.form IN ('10-Q','10-Q/A')
      AND s.period BETWEEN DATE '{start_date}' AND DATE '{end_date}'
      AND n.tag = 'NetCashProvidedByUsedInOperatingActivities'
      AND COALESCE(n.qtrs, 0) = 1
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
      -- Optional sector filter
      -- AND s.cik IN (SELECT cik FROM companies WHERE gics_sector = '{sector_filter}')
),
company_stats AS (
    SELECT
        qc.cik,
        STDDEV_POP(qc.operating_cash_flow) AS cfo_stddev,
        AVG(qc.operating_cash_flow) AS cfo_avg,
        COUNT(*) AS observation_count
    FROM quarterly_cfo qc
    GROUP BY qc.cik
)
SELECT
    qc.cik,
    qc.period,
    qc.fiscal_year,
    qc.fiscal_period,
    qc.operating_cash_flow,
    cs.cfo_stddev,
    cs.cfo_avg,
    CASE
        WHEN cs.cfo_avg <> 0 THEN cs.cfo_stddev / cs.cfo_avg
        ELSE NULL
    END AS coefficient_of_variation
FROM quarterly_cfo qc
JOIN company_stats cs USING (cik)
ORDER BY qc.cik, qc.period;

