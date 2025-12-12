WITH provided_companies AS (
    SELECT
        TRIM(company_name) AS provided_name,
        REGEXP_REPLACE(UPPER(TRIM(company_name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM (VALUES {company_values}) AS t(company_name)
),
sector_companies AS (
    SELECT
        cik,
        name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE ('{sector}' = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
list_companies AS (
    SELECT
        c.cik,
        c.name,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies c
    JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') = pc.canonical_name
),
combined_companies AS (
    SELECT * FROM list_companies
    UNION ALL
    SELECT * FROM sector_companies
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN combined_companies sc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest AS (
    SELECT *
    FROM annual_filings
    WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'NetCashProvidedByUsedInOperatingActivities' THEN n.value END) AS cfo,
        MAX(CASE WHEN n.tag IN ('NetIncomeLoss', 'ProfitLoss') THEN n.value END) AS net_income
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'NetIncomeLoss',
        'ProfitLoss'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        sc.canonical_name,
        sc.name AS company,
        av.fiscal_year,
        av.cfo,
        av.net_income,
        CASE
            WHEN av.net_income IS NULL OR av.net_income = 0 THEN NULL
            ELSE av.cfo / av.net_income
        END AS cfo_to_net_income
    FROM annual_values av
    JOIN combined_companies sc USING (cik)
),
aggregated AS (
    SELECT
        company,
        canonical_name,
        COUNT(DISTINCT CASE WHEN cfo_to_net_income IS NOT NULL THEN fiscal_year END) AS ratio_years,
        AVG(cfo_to_net_income) AS avg_ratio,
        MIN(cfo_to_net_income) AS min_ratio,
        MAX(cfo_to_net_income) AS max_ratio,
        SUM(COALESCE(cfo, 0)) AS total_cfo,
        SUM(COALESCE(net_income, 0)) AS total_net_income
    FROM ratios
    GROUP BY company, canonical_name
)
SELECT
    company AS name,
    ROUND(avg_ratio, 2) AS avg_cfo_to_net_income,
    ROUND(min_ratio, 2) AS min_ratio,
    ROUND(max_ratio, 2) AS max_ratio,
    ROUND(total_cfo / 1000000000.0, 2) AS total_cfo_billions,
    ROUND(total_net_income / 1000000000.0, 2) AS total_net_income_billions
FROM aggregated
WHERE ratio_years >= {min_years}
  AND total_net_income IS NOT NULL
  AND ABS(total_net_income) >= {min_net_income}
  AND total_cfo IS NOT NULL
  AND ABS(total_cfo) >= {min_cfo}
  AND avg_ratio IS NOT NULL
  AND avg_ratio BETWEEN -{max_ratio} AND {max_ratio}
ORDER BY avg_ratio DESC, total_cfo DESC
LIMIT {limit};
