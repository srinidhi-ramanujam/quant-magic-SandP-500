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
      AND s.fy BETWEEN {baseline_start_year} AND {revert_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) AS net_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                ) THEN n.value
            END
        ) AS equity
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetIncomeLoss',
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
roe_series AS (
    SELECT
        cd.display_name AS name,
        av.fiscal_year,
        CASE
            WHEN av.equity IS NULL OR av.equity = 0 THEN NULL
            WHEN av.net_income IS NULL THEN NULL
            ELSE av.net_income / av.equity
        END AS roe
    FROM annual_values av
    JOIN company_dim cd USING (cik)
),
baseline AS (
    SELECT
        name,
        AVG(roe) AS baseline_roe
    FROM roe_series
    WHERE fiscal_year BETWEEN {baseline_start_year} AND {baseline_end_year}
      AND roe IS NOT NULL
    GROUP BY name
),
band_eval AS (
    SELECT
        rs.name,
        rs.fiscal_year,
        rs.roe,
        b.baseline_roe,
        CASE
            WHEN rs.roe IS NULL OR b.baseline_roe IS NULL THEN NULL
            WHEN ABS((rs.roe - b.baseline_roe) * 100) <= {band_bps} / 100.0 THEN 1
            ELSE 0
        END AS within_band
    FROM roe_series rs
    JOIN baseline b USING (name)
    WHERE rs.fiscal_year BETWEEN {band_start_year} AND {band_end_year}
),
revert AS (
    SELECT
        rs.name,
        rs.roe AS roe_revert,
        b.baseline_roe
    FROM roe_series rs
    JOIN baseline b USING (name)
    WHERE rs.fiscal_year = {revert_year}
)
SELECT
    b.name,
    ROUND(b.baseline_roe * 100, 2) AS baseline_roe_pct,
    SUM(be.within_band) AS years_within_band,
    COUNT(be.within_band) AS band_years_checked,
    ROUND(AVG(be.roe) * 100, 2) AS avg_roe_band_years_pct,
    ROUND(r.roe_revert * 100, 2) AS roe_{revert_year}_pct,
    ROUND((r.roe_revert - b.baseline_roe) * 100, 2) AS revert_delta_pp
FROM baseline b
LEFT JOIN band_eval be ON be.name = b.name
LEFT JOIN revert r ON r.name = b.name
GROUP BY b.name, b.baseline_roe, r.roe_revert
HAVING band_years_checked > 0 AND r.roe_revert IS NOT NULL
ORDER BY years_within_band DESC, revert_delta_pp ASC, b.name
LIMIT {limit};
