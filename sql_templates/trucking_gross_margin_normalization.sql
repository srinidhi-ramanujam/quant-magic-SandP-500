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
      AND s.fy BETWEEN {spike_start_year} AND {normalization_end_year}
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
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
margins AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            WHEN av.cogs IS NULL THEN NULL
            ELSE (av.revenue - av.cogs) / av.revenue
        END AS gross_margin
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
bucketed AS (
    SELECT
        name,
        CASE
            WHEN fiscal_year BETWEEN {spike_start_year} AND {spike_end_year} THEN 'spike'
            WHEN fiscal_year BETWEEN {normalization_start_year} AND {normalization_end_year} THEN 'normalization'
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
    WHERE bucket IN ('spike','normalization')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'spike' THEN avg_margin END) AS spike_margin,
        MAX(CASE WHEN bucket = 'spike' THEN year_count END) AS spike_years,
        MAX(CASE WHEN bucket = 'normalization' THEN avg_margin END) AS normalization_margin,
        MAX(CASE WHEN bucket = 'normalization' THEN year_count END) AS normalization_years
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(spike_margin * 100, 2) AS spike_margin_pct,
    ROUND(normalization_margin * 100, 2) AS normalization_margin_pct,
    ROUND((normalization_margin - spike_margin) * 100, 2) AS change_pp,
    spike_years,
    normalization_years
FROM pivoted
WHERE spike_years IS NOT NULL AND normalization_years IS NOT NULL
ORDER BY change_pp ASC, name
LIMIT {limit};
