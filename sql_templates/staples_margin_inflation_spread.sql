WITH sector_companies AS (
    SELECT
        cik,
        name AS display_name
    FROM companies
    WHERE '{sector}' = 'ALL'
       OR LOWER(gics_sector) LIKE LOWER('%{sector}%')
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
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {pre_start_year} AND {inflation_end_year}
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
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue,
        MAX(
            CASE
                WHEN n.tag IN (
                    'CostOfRevenue',
                    'CostOfGoodsSold',
                    'CostOfGoodsAndServicesSold'
                ) THEN n.value
            END
        ) AS cogs
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet',
        'CostOfRevenue','CostOfGoodsSold','CostOfGoodsAndServicesSold'
    )
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
margins AS (
    SELECT
        sc.display_name AS name,
        av.fiscal_year,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            WHEN av.cogs IS NULL THEN NULL
            ELSE (av.revenue - av.cogs) / av.revenue
        END AS gross_margin
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
),
bucketed AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {pre_start_year} AND {pre_end_year} THEN 'pre'
            WHEN fiscal_year BETWEEN {inflation_start_year} AND {inflation_end_year} THEN 'inflation'
            ELSE 'other'
        END AS bucket,
        gross_margin
    FROM margins
    WHERE gross_margin IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(gross_margin) AS avg_margin,
        COUNT(*) AS year_count
    FROM bucketed
    WHERE bucket IN ('pre','inflation')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'pre' THEN avg_margin END) AS pre_margin,
        MAX(CASE WHEN bucket = 'pre' THEN year_count END) AS pre_years,
        MAX(CASE WHEN bucket = 'inflation' THEN avg_margin END) AS inflation_margin,
        MAX(CASE WHEN bucket = 'inflation' THEN year_count END) AS inflation_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(pre_margin * 100, 2) AS pre_margin_pct,
    ROUND(inflation_margin * 100, 2) AS inflation_margin_pct,
    ROUND((inflation_margin - pre_margin) * 100, 2) AS change_pp,
    pre_years,
    inflation_years
FROM pivoted
WHERE pre_years IS NOT NULL AND inflation_years IS NOT NULL
ORDER BY change_pp ASC, name
LIMIT {limit};
