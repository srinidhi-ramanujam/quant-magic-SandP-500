WITH sector_companies AS (
    SELECT
        cik,
        name AS display_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
ranked_filings AS (
    SELECT
        s.adsh,
        s.cik,
        s.period,
        s.fy AS fiscal_year,
        s.fp AS fiscal_period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.period ORDER BY s.filed DESC) AS period_rank
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-Q','10-Q/A')
      AND s.period BETWEEN DATE '{start_date}' AND DATE '{end_date}'
),
latest_quarterlies AS (
    SELECT * FROM ranked_filings WHERE period_rank = 1
),
quarterly_cfo AS (
    SELECT
        lq.cik,
        lq.period,
        lq.fiscal_year,
        lq.fiscal_period,
        MAX(
            CASE
                WHEN n.tag IN (
                    'NetCashProvidedByUsedInOperatingActivities',
                    'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
                )
                AND COALESCE(n.qtrs, 0) = 1
                THEN n.value
            END
        ) AS operating_cash_flow
    FROM latest_quarterlies lq
    JOIN num n ON n.adsh = lq.adsh AND n.ddate = lq.period
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
      AND COALESCE(n.qtrs, 0) = 1
    GROUP BY lq.cik, lq.period, lq.fiscal_year, lq.fiscal_period
),
stats AS (
    SELECT
        sc.display_name AS name,
        qc.cik,
        COUNT(*) AS observations,
        AVG(qc.operating_cash_flow) AS cfo_avg,
        STDDEV_POP(qc.operating_cash_flow) AS cfo_stddev
    FROM quarterly_cfo qc
    JOIN sector_companies sc USING (cik)
    WHERE qc.operating_cash_flow IS NOT NULL
    GROUP BY sc.display_name, qc.cik
)
SELECT
    name,
    observations,
    ROUND(cfo_avg / 1000000.0, 2) AS cfo_avg_millions,
    ROUND(cfo_stddev / 1000000.0, 2) AS cfo_stddev_millions,
    CASE
        WHEN cfo_avg IS NULL OR cfo_avg = 0 THEN NULL
        ELSE ROUND(cfo_stddev / cfo_avg, 3)
    END AS coefficient_of_variation
FROM stats
WHERE observations >= {min_observations}
  AND cfo_avg IS NOT NULL
  AND ABS(cfo_avg) >= {min_avg_abs}
ORDER BY coefficient_of_variation ASC NULLS LAST, observations DESC, name
LIMIT {limit};
