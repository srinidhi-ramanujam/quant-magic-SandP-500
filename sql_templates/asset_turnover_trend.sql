WITH sector_companies AS (
    SELECT DISTINCT cik, name AS display_name
    FROM companies
    WHERE ('{sector}' = 'ALL' OR UPPER(gics_sector) = UPPER('{sector}'))
      AND (
        {sic_filter_enabled} = 0
        OR (
            sic IS NOT NULL
            AND CAST(sic AS INTEGER) BETWEEN {sic_min} AND {sic_max}
        )
      )
),
company_dim AS (
    SELECT DISTINCT c.cik, sc.display_name
    FROM companies c
    JOIN sector_companies sc ON c.cik = sc.cik
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
        cd.display_name AS company,
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE WHEN n.tag IN (
                'Revenues',
                'RevenueFromContractWithCustomerExcludingAssessedTax',
                'SalesRevenueNet'
            ) THEN n.value END
        ) AS revenue,
        MAX(CASE WHEN n.tag = 'Assets' THEN n.value END) AS assets
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    JOIN company_dim cd USING (cik)
    WHERE n.tag IN (
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',
        'Assets'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY cd.display_name, lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        company,
        fiscal_year,
        revenue,
        assets,
        CASE
            WHEN revenue IS NULL OR assets IS NULL OR assets = 0 THEN NULL
            ELSE revenue / assets
        END AS asset_turnover
    FROM annual_values
),
company_turnover AS (
    SELECT
        company,
        COUNT(DISTINCT fiscal_year) AS years_available,
        ROUND(MAX(CASE WHEN fiscal_year = {start_year} THEN asset_turnover END), 2) AS turnover_{start_year},
        ROUND(MAX(CASE WHEN fiscal_year = {year_2} THEN asset_turnover END), 2) AS turnover_{year_2},
        ROUND(MAX(CASE WHEN fiscal_year = {year_3} THEN asset_turnover END), 2) AS turnover_{year_3},
        ROUND(MAX(CASE WHEN fiscal_year = {end_year} THEN asset_turnover END), 2) AS turnover_{end_year},
        ROUND(MAX(CASE WHEN fiscal_year = {start_year} THEN asset_turnover END), 2) AS turnover_start,
        ROUND(MAX(CASE WHEN fiscal_year = {end_year} THEN asset_turnover END), 2) AS turnover_end,
        ROUND(
            MAX(CASE WHEN fiscal_year = {end_year} THEN asset_turnover END)
            - MIN(CASE WHEN fiscal_year = {start_year} THEN asset_turnover END),
            2
        ) AS change_since_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN revenue END) AS latest_revenue
    FROM ratios
    GROUP BY company
    HAVING COUNT(DISTINCT fiscal_year) >= {min_years}
)
SELECT
    name,
    years_available,
    turnover_start,
    turnover_end,
    change_since_start,
    turnover_{start_year} AS turnover_{start_year},
    turnover_{year_2} AS turnover_{year_2},
    turnover_{year_3} AS turnover_{year_3},
    turnover_{end_year} AS turnover_{end_year}
FROM (
    SELECT
        company AS name,
        years_available,
        turnover_start,
        turnover_end,
        change_since_start,
        turnover_{start_year},
        turnover_{year_2},
        turnover_{year_3},
        turnover_{end_year},
        ROW_NUMBER() OVER (
            ORDER BY change_since_start DESC NULLS LAST, company
        ) AS rn
    FROM company_turnover
    WHERE latest_revenue IS NOT NULL AND latest_revenue >= {min_revenue}
) ranked
WHERE rn <= {limit}
ORDER BY change_since_start DESC NULLS LAST, name;
