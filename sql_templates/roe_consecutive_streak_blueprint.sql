WITH annual_roes AS (
    SELECT
        s.cik,
        s.fy AS fiscal_year,
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
    FROM sub s
    JOIN num n ON n.adsh = s.adsh AND n.ddate = s.period
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
      -- Optional sector filter
      -- AND s.cik IN (
      --     SELECT cik FROM companies WHERE gics_sector = '{sector_filter}'
      -- )
    GROUP BY s.cik, s.fy
),
roe_series AS (
    SELECT
        r.cik,
        r.fiscal_year,
        r.net_income,
        r.equity,
        CASE WHEN r.equity <> 0 THEN r.net_income / r.equity ELSE NULL END AS roe
    FROM annual_roes r
),
roe_flag AS (
    SELECT
        rs.cik,
        rs.fiscal_year,
        rs.roe,
        CASE
            WHEN rs.roe IS NOT NULL AND rs.roe >= ({roe_threshold} / 100.0)
            THEN 1
            ELSE 0
        END AS above_threshold
    FROM roe_series rs
)
SELECT
    rf.cik,
    rf.fiscal_year,
    rf.roe,
    rf.above_threshold
FROM roe_flag rf
JOIN companies c ON c.cik = rf.cik
WHERE 1 = 1
  -- Optional jurisdiction filter
  -- AND c.countryinc = '{jurisdiction_filter}'
ORDER BY rf.cik, rf.fiscal_year;
-- Use window functions to ensure a streak of at least {min_consecutive_years} consecutive years above the threshold.

