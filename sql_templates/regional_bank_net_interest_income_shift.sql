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
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {pre_start_year} AND {hike_end_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'NetInterestIncome',
                    'InterestAndDividendIncomeOperating'
                ) THEN n.value
            END
        ) AS net_interest_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'InterestExpense',
                    'InterestAndDebtExpense'
                ) THEN n.value
            END
        ) AS interest_expense
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetInterestIncome',
        'InterestAndDividendIncomeOperating',
        'InterestExpense',
        'InterestAndDebtExpense'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        av.net_interest_income,
        av.interest_expense,
        CASE
            WHEN av.net_interest_income IS NULL THEN NULL
            ELSE av.net_interest_income - COALESCE(av.interest_expense, 0)
        END AS nii_minus_expense
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
bucketed AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'zerorate'
            WHEN fiscal_year BETWEEN {hike_start_year} AND {hike_end_year} THEN 'hike'
            ELSE 'other'
        END AS bucket,
        nii_minus_expense
    FROM ratios
    WHERE nii_minus_expense IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(nii_minus_expense) AS avg_spread,
        COUNT(*) AS year_count
    FROM bucketed
    WHERE bucket IN ('zerorate','hike')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'zerorate' THEN avg_spread END) AS zerorate_spread,
        MAX(CASE WHEN bucket = 'zerorate' THEN year_count END) AS zerorate_years,
        MAX(CASE WHEN bucket = 'hike' THEN avg_spread END) AS hike_spread,
        MAX(CASE WHEN bucket = 'hike' THEN year_count END) AS hike_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(zerorate_spread / 1000000000.0, 2) AS zerorate_spread_billions,
    ROUND(hike_spread / 1000000000.0, 2) AS hike_spread_billions,
    ROUND((hike_spread - zerorate_spread) / 1000000000.0, 2) AS spread_delta_billions,
    zerorate_years,
    hike_years
FROM pivoted
WHERE zerorate_years IS NOT NULL AND hike_years IS NOT NULL
ORDER BY spread_delta_billions DESC, name
LIMIT {limit};
