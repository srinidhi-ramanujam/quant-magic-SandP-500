WITH sector_companies AS (
    SELECT cik,
           name AS display_name,
           REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name,
           ROW_NUMBER() OVER (PARTITION BY cik ORDER BY name) AS rn
    FROM companies
    WHERE ('{sector}' = 'ALL' OR UPPER(gics_sector) = UPPER('{sector}'))
),
company_seed AS (
    SELECT cik, display_name, canonical_name
    FROM sector_companies
    WHERE rn = 1
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
    JOIN company_seed sc USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        sc.display_name AS company,
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag IN (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
            'NetCashProvidedByUsedInOperatingActivitiesExcludingDiscontinuedOperations'
        ) THEN n.value END) AS cfo,
        MAX(CASE WHEN n.tag IN (
            'NetIncomeLoss',
            'NetIncomeLossAvailableToCommonStockholdersBasic',
            'NetIncomeLossAvailableToCommonStockholdersDiluted'
        ) THEN n.value END) AS net_income
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    JOIN company_seed sc USING (cik)
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        'NetCashProvidedByUsedInOperatingActivitiesExcludingDiscontinuedOperations',
        'NetIncomeLoss',
        'NetIncomeLossAvailableToCommonStockholdersBasic',
        'NetIncomeLossAvailableToCommonStockholdersDiluted'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY sc.display_name, lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        company,
        fiscal_year,
        cfo,
        net_income,
        CASE
            WHEN net_income IS NULL OR cfo IS NULL THEN NULL
            WHEN net_income <= {min_net_income} OR cfo <= 0 THEN NULL
            ELSE LEAST(cfo / net_income, {max_ratio})
        END AS cfo_to_ni
    FROM annual_values
),
company_quality AS (
    SELECT
        company,
        REGEXP_REPLACE(UPPER(TRIM(company)), '[^A-Z0-9]', '', 'g') AS canonical_name,
        COUNT(DISTINCT fiscal_year) AS years_available,
        ROUND(AVG(cfo_to_ni), 2) AS avg_ratio,
        ROUND(MAX(CASE WHEN fiscal_year = {start_year} THEN cfo_to_ni END), 2) AS ratio_{start_year},
        ROUND(MAX(CASE WHEN fiscal_year = {end_year} THEN cfo_to_ni END), 2) AS ratio_{end_year},
        ROUND(
            MAX(CASE WHEN fiscal_year = {end_year} THEN cfo_to_ni END)
            - MIN(CASE WHEN fiscal_year = {start_year} THEN cfo_to_ni END),
            2
        ) AS change_since_start,
        ROUND(MAX(CASE WHEN fiscal_year = {year_2} THEN cfo_to_ni END), 2) AS ratio_{year_2},
        ROUND(MAX(CASE WHEN fiscal_year = {year_3} THEN cfo_to_ni END), 2) AS ratio_{year_3}
    FROM ratios
    GROUP BY company
    HAVING COUNT(DISTINCT fiscal_year) >= {min_years}
       AND MIN(CASE WHEN fiscal_year = {start_year} THEN cfo_to_ni END) IS NOT NULL
       AND MIN(CASE WHEN fiscal_year = {year_3} THEN cfo_to_ni END) IS NOT NULL
)
SELECT
    name,
    years_available,
    avg_ratio,
    change_since_start,
    ratio_{start_year} AS ratio_{start_year},
    ratio_{year_2} AS ratio_{year_2},
    ratio_{year_3} AS ratio_{year_3},
    ratio_{end_year} AS ratio_{end_year}
FROM (
    SELECT
        company AS name,
        canonical_name,
        years_available,
        avg_ratio,
        change_since_start,
        ratio_{start_year},
        ratio_{year_2},
        ratio_{year_3},
        ratio_{end_year},
        ROW_NUMBER() OVER (
            PARTITION BY canonical_name
            ORDER BY avg_ratio DESC NULLS LAST, company
        ) AS name_rank
    FROM company_quality
    WHERE avg_ratio IS NOT NULL
) ranked
WHERE name_rank = 1
ORDER BY avg_ratio DESC NULLS LAST, name
LIMIT {limit};
