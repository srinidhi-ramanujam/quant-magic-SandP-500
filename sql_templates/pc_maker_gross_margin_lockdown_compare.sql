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
        s.period,
        s.filed,
        s.form,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.period ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_dim cd USING (cik)
    WHERE s.form IN ('10-Q','10-Q/A')
      AND s.period BETWEEN '{pre_start_period}' AND '{lockdown_end_period}'
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
quarterly_values AS (
    SELECT
        lf.cik,
        lf.period,
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
    GROUP BY lf.cik, lf.period
),
with_margin AS (
    SELECT
        cd.display_name AS name,
        qv.period,
        CASE
            WHEN qv.revenue IS NULL OR qv.revenue = 0 THEN NULL
            WHEN qv.cogs IS NULL THEN NULL
            ELSE (qv.revenue - qv.cogs) / qv.revenue
        END AS gross_margin
    FROM quarterly_values qv
    JOIN company_dim cd USING (cik)
),
bucketed AS (
    SELECT
        name,
        period,
        gross_margin,
        CASE
            WHEN period BETWEEN '{pre_start_period}' AND '{pre_end_period}' THEN 'pre'
            WHEN period BETWEEN '{lockdown_start_period}' AND '{lockdown_end_period}' THEN 'lockdown'
            ELSE 'other'
        END AS bucket
    FROM with_margin
    WHERE gross_margin IS NOT NULL
),
aggregated AS (
    SELECT
        name,
        bucket,
        AVG(gross_margin) AS avg_margin,
        COUNT(*) AS quarter_count
    FROM bucketed
    WHERE bucket IN ('pre','lockdown')
    GROUP BY name, bucket
),
pivoted AS (
    SELECT
        name,
        MAX(CASE WHEN bucket = 'pre' THEN avg_margin END) AS pre_margin,
        MAX(CASE WHEN bucket = 'pre' THEN quarter_count END) AS pre_quarters,
        MAX(CASE WHEN bucket = 'lockdown' THEN avg_margin END) AS lockdown_margin,
        MAX(CASE WHEN bucket = 'lockdown' THEN quarter_count END) AS lockdown_quarters
    FROM aggregated
    GROUP BY name
)
SELECT
    name,
    ROUND(pre_margin * 100, 2) AS pre_margin_pct,
    ROUND(lockdown_margin * 100, 2) AS lockdown_margin_pct,
    ROUND((lockdown_margin - pre_margin) * 100, 2) AS margin_delta_pp,
    pre_quarters,
    lockdown_quarters
FROM pivoted
WHERE pre_quarters >= {min_quarters} AND lockdown_quarters >= {min_quarters}
ORDER BY margin_delta_pp DESC, name
LIMIT {limit};
