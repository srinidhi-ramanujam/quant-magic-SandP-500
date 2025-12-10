WITH sector_companies AS (
    SELECT
        cik,
        name,
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
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'PaymentsOfDividends' THEN ABS(n.value) END) AS dividends_all,
        MAX(CASE WHEN n.tag = 'PaymentsOfDividendsCommonStock' THEN ABS(n.value) END) AS dividends_common,
        MAX(CASE WHEN n.tag = 'PaymentsForRepurchaseOfCommonStock' THEN ABS(n.value) END) AS buybacks,
        MAX(CASE WHEN n.tag = 'NetCashProvidedByUsedInOperatingActivities' THEN n.value END) AS cfo
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'PaymentsOfDividends',
        'PaymentsOfDividendsCommonStock',
        'PaymentsForRepurchaseOfCommonStock',
        'NetCashProvidedByUsedInOperatingActivities'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
aggregated AS (
    SELECT
        sc.canonical_name,
        ANY_VALUE(sc.name) AS company,
        SUM(COALESCE(av.cfo, 0)) AS total_cfo,
        SUM(
            COALESCE(av.dividends_common, COALESCE(av.dividends_all, 0))
            + COALESCE(av.buybacks, 0)
        ) AS total_payouts,
        COUNT(DISTINCT av.fiscal_year) AS covered_years
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
    GROUP BY sc.canonical_name
)
SELECT
    company AS name,
    ROUND(total_payouts / 1000000000.0, 2) AS payouts_billions,
    ROUND(total_cfo / 1000000000.0, 2) AS cfo_billions,
    ROUND(total_payouts / NULLIF(total_cfo, 0), 2) AS payout_ratio
FROM aggregated
WHERE covered_years >= 1
  AND total_cfo IS NOT NULL
  AND total_cfo > 0
  AND total_payouts IS NOT NULL
  AND total_cfo >= {min_cfo}
  AND (total_payouts / total_cfo) <= {max_payout_ratio}
ORDER BY payout_ratio DESC, payouts_billions DESC
LIMIT {limit};
