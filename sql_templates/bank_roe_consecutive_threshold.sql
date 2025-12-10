WITH provided_companies AS (
    -- Optional explicit bank cohort; expects canonicalized names uppercased without punctuation
    -- Example: ('JPMORGANCHASECO'),('BANKOFAMERICA'),('CITIGROUPINC'),('WELLSFARGO&CO')
    SELECT * FROM (VALUES {company_values}) AS t(canonical_name)
),
sector_companies AS (
    SELECT
        cik,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name,
        name AS display_name
    FROM companies
    WHERE {use_sector_filter} = 1
      AND (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
cohort AS (
    SELECT DISTINCT c.cik, c.display_name, c.canonical_name
    FROM sector_companies c
    UNION
    SELECT DISTINCT c.cik, c.name AS display_name, pc.canonical_name
    FROM companies c
    JOIN provided_companies pc
      ON REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') = pc.canonical_name
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
    JOIN cohort c USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
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
                )
                THEN n.value
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
        c.display_name,
        c.canonical_name,
        av.fiscal_year,
        CASE
            WHEN av.equity IS NULL OR av.equity = 0 THEN NULL
            WHEN av.net_income IS NULL THEN NULL
            ELSE av.net_income / av.equity
        END AS roe_ratio
    FROM annual_values av
    JOIN cohort c USING (cik)
    WHERE av.equity IS NULL OR ABS(av.equity) >= {min_equity}
),
roe_filtered AS (
    SELECT
        rs.*,
        CASE
            WHEN rs.roe_ratio IS NULL THEN NULL
            WHEN ABS(rs.roe_ratio * 100) > {max_roe_pct} THEN NULL
            ELSE rs.roe_ratio
        END AS capped_roe
    FROM roe_series rs
),
flags AS (
    SELECT
        rf.*,
        CASE
            WHEN rf.capped_roe IS NOT NULL AND rf.capped_roe * 100 >= {roe_threshold} THEN 1
            ELSE 0
        END AS above_threshold
    FROM roe_filtered rf
),
streaks AS (
    SELECT
        f.display_name AS name,
        f.canonical_name,
        f.fiscal_year,
        f.capped_roe,
        f.above_threshold,
        fiscal_year - ROW_NUMBER() OVER (PARTITION BY f.canonical_name ORDER BY fiscal_year) AS streak_key
    FROM flags f
),
agg AS (
    SELECT
        name,
        canonical_name,
        COUNT(*) AS total_years,
        SUM(above_threshold) AS years_above_threshold,
        MAX(
            CASE WHEN above_threshold = 1 THEN streak_length ELSE 0 END
        ) AS max_streak,
        MIN(CASE WHEN above_threshold = 1 THEN fiscal_year END) AS first_roeyear,
        MAX(CASE WHEN above_threshold = 1 THEN fiscal_year END) AS last_roeyear,
        AVG(CASE WHEN above_threshold = 1 THEN capped_roe END) AS avg_roe_above,
        AVG(capped_roe) AS avg_roe_all
    FROM (
        SELECT
            name,
            canonical_name,
            fiscal_year,
            capped_roe,
            above_threshold,
            streak_key,
            COUNT(*) OVER (PARTITION BY canonical_name, streak_key, above_threshold) AS streak_length
        FROM streaks
    ) s
    GROUP BY name, canonical_name
    HAVING total_years >= {min_years_reported}
)
SELECT
    name,
    max_streak,
    years_above_threshold,
    total_years,
    ROUND(avg_roe_above * 100, 2) AS avg_roe_above_pct,
    ROUND(avg_roe_all * 100, 2) AS avg_roe_all_pct,
    first_roeyear AS first_year_above_threshold,
    last_roeyear AS last_year_above_threshold
FROM agg
WHERE max_streak >= {min_consecutive_years}
ORDER BY max_streak DESC, avg_roe_above_pct DESC, name
LIMIT {limit};
